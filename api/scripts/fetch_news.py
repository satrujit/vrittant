"""Standalone RSS news fetcher — runs inside the API container.

Usage:
    python scripts/fetch_news.py [breaking|regular|all]

Matches the original Cloud Function logic: fetches RSS feeds, deduplicates
by URL, and inserts into news_articles with ON CONFLICT DO NOTHING.
"""

import os
import re
import sys
import uuid
from calendar import timegm
from datetime import datetime, timezone
from html import unescape

import feedparser
import httpx
from sqlalchemy import text

# Re-use the API's DB session
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import SessionLocal

# ── Feed configuration ───────────────────────────────────────────────────────
RSS_FEEDS = [
    # BREAKING TIER — every 15 min
    {"url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFZxYUdjU0FtVnVHZ0pKVGlnQVAB?hl=en-IN&gl=IN&ceid=IN:en", "category": "general", "source": "Google News", "tier": "breaking"},
    {"url": "https://feeds.feedburner.com/ndtvnews-top-stories", "category": "general", "source": "NDTV", "tier": "breaking"},
    {"url": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms", "category": "general", "source": "Times of India", "tier": "breaking"},
    {"url": "https://news.google.com/rss/search?q=Odisha&hl=en-IN&gl=IN&ceid=IN:en", "category": "regional", "source": "Google News", "tier": "breaking"},
    {"url": "https://news.google.com/rss/search?q=Bhubaneswar+OR+Cuttack+OR+Puri+OR+Rourkela&hl=en-IN&gl=IN&ceid=IN:en", "category": "regional", "source": "Google News", "tier": "breaking"},
    {"url": "https://timesofindia.indiatimes.com/rssfeeds/4118235.cms", "category": "regional", "source": "Times of India", "tier": "breaking"},
    {"url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp1ZEdvU0FtVnVHZ0pKVGlnQVAB?hl=en-IN&gl=IN&ceid=IN:en", "category": "sports", "source": "Google News", "tier": "breaking"},
    {"url": "https://feeds.feedburner.com/ndtvsports-latest", "category": "sports", "source": "NDTV Sports", "tier": "breaking"},
    {"url": "https://news.google.com/rss/search?q=Odisha+government+OR+Odisha+politics&hl=en-IN&gl=IN&ceid=IN:en", "category": "politics", "source": "Google News", "tier": "breaking"},
    {"url": "https://news.google.com/rss/search?q=crime+India+police&hl=en-IN&gl=IN&ceid=IN:en", "category": "crime", "source": "Google News", "tier": "breaking"},
    # REGULAR TIER — every 2 hours
    {"url": "https://indianexpress.com/section/india/feed/", "category": "general", "source": "Indian Express", "tier": "regular"},
    {"url": "https://www.thehindu.com/news/national/feeder/default.rss", "category": "general", "source": "The Hindu", "tier": "regular"},
    {"url": "https://timesofindia.indiatimes.com/rssfeeds/4719148.cms", "category": "sports", "source": "Times of India", "tier": "regular"},
    {"url": "https://indianexpress.com/section/sports/feed/", "category": "sports", "source": "Indian Express", "tier": "regular"},
    {"url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNREpxYW5RU0FtVnVHZ0pKVGlnQVAB?hl=en-IN&gl=IN&ceid=IN:en", "category": "entertainment", "source": "Google News", "tier": "regular"},
    {"url": "https://timesofindia.indiatimes.com/rssfeeds/1081479906.cms", "category": "entertainment", "source": "Times of India", "tier": "regular"},
    {"url": "https://indianexpress.com/section/entertainment/feed/", "category": "entertainment", "source": "Indian Express", "tier": "regular"},
    {"url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pKVGlnQVAB?hl=en-IN&gl=IN&ceid=IN:en", "category": "business", "source": "Google News", "tier": "regular"},
    {"url": "https://feeds.feedburner.com/ndtvprofit-latest", "category": "business", "source": "NDTV Profit", "tier": "regular"},
    {"url": "https://indianexpress.com/section/business/feed/", "category": "business", "source": "Indian Express", "tier": "regular"},
    {"url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtVnVHZ0pKVGlnQVAB?hl=en-IN&gl=IN&ceid=IN:en", "category": "technology", "source": "Google News", "tier": "regular"},
    {"url": "https://feeds.feedburner.com/gadgets360-latest", "category": "technology", "source": "NDTV Gadgets", "tier": "regular"},
    {"url": "https://news.google.com/rss/search?q=health+India&hl=en-IN&gl=IN&ceid=IN:en", "category": "health", "source": "Google News", "tier": "regular"},
    {"url": "https://news.google.com/rss/search?q=education+India+exam+university&hl=en-IN&gl=IN&ceid=IN:en", "category": "education", "source": "Google News", "tier": "regular"},
]

INSERT_SQL = text(
    "INSERT INTO news_articles "
    "(id, title, description, url, source, author, image_url, "
    " category, language, country, published_at, fetched_at) "
    "VALUES "
    "(:id, :title, :description, :url, :source, :author, :image_url, "
    " :category, :language, :country, :published_at, :fetched_at) "
    "ON CONFLICT (url) DO NOTHING"
)


def strip_html(t: str) -> str:
    if not t:
        return ""
    return unescape(re.sub(r"<[^>]+>", "", t)).strip()


def extract_image(entry) -> str | None:
    for m in entry.get("media_content", []):
        url = m.get("url", "")
        if url:
            return url
    for t in entry.get("media_thumbnail", []):
        if t.get("url"):
            return t["url"]
    summary = entry.get("summary", "") or ""
    match = re.search(r'<img[^>]+src=["\']([^"\' ]+)', summary)
    return match.group(1) if match else None


def parse_date(entry) -> datetime | None:
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                return datetime.fromtimestamp(timegm(parsed), tz=timezone.utc)
            except Exception:
                pass
    return None


def main(tier: str = "all") -> None:
    feeds = RSS_FEEDS if tier == "all" else [f for f in RSS_FEEDS if f["tier"] == tier]
    now = datetime.now(timezone.utc)
    seen: set[str] = set()
    rows: list[dict] = []

    for fc in feeds:
        try:
            resp = httpx.get(
                fc["url"],
                timeout=20,
                follow_redirects=True,
                headers={"User-Agent": "VrittantBot/1.0"},
            )
            feed = feedparser.parse(resp.text)
            for entry in feed.entries[:30]:
                link = entry.get("link", "")
                title = strip_html(entry.get("title", ""))
                if not link or not title or link in seen:
                    continue
                seen.add(link)

                source = fc["source"]
                if "news.google.com" in fc["url"] and " - " in title:
                    title, source = title.rsplit(" - ", 1)

                desc = strip_html(
                    entry.get("summary", "") or entry.get("description", "")
                )[:1000]

                rows.append(
                    {
                        "id": uuid.uuid4().hex,
                        "title": title.strip(),
                        "description": desc or None,
                        "url": link,
                        "source": source.strip(),
                        "author": entry.get("author"),
                        "image_url": extract_image(entry),
                        "category": fc["category"],
                        "language": "en",
                        "country": "in",
                        "published_at": parse_date(entry),
                        "fetched_at": now,
                    }
                )
        except Exception as ex:
            print(f"Feed error {fc['source']}/{fc['category']}: {ex}")

    inserted = 0
    if rows:
        db = SessionLocal()
        try:
            for row in rows:
                inserted += db.execute(INSERT_SQL, row).rowcount
            db.commit()
        finally:
            db.close()

    print(f"News fetcher: tier={tier}, fetched={len(rows)}, inserted={inserted}")


if __name__ == "__main__":
    tier_arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    if tier_arg not in ("breaking", "regular", "all"):
        print(f"Usage: {sys.argv[0]} [breaking|regular|all]")
        sys.exit(1)
    main(tier_arg)
