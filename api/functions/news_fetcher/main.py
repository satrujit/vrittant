"""Cloud Function: fetch news from RSS feeds and store in Cloud SQL.

Replaces the previous Mediastack-based fetcher with free RSS feeds from
Google News, NDTV, Times of India, Indian Express, and other Indian
news sources. Covers Odisha (regional), sports, entertainment, business,
technology, and general India news.
"""

import os
import re
import uuid
import traceback
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape

import feedparser
import functions_framework
import httpx
import sqlalchemy
from google.cloud.sql.connector import Connector, IPTypes

# -- Config from env ---------------------------------------------------------
INSTANCE_CONNECTION_NAME = os.environ.get("INSTANCE_CONNECTION_NAME", "")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASS = os.environ.get("DB_PASS", "")
DB_NAME = os.environ.get("DB_NAME", "vrittant")

# -- Lazy DB setup -----------------------------------------------------------
_connector = None
_engine = None


def get_engine():
    global _connector, _engine
    if _engine is None:
        _connector = Connector()

        def _get_conn():
            return _connector.connect(
                INSTANCE_CONNECTION_NAME,
                "pg8000",
                user=DB_USER,
                password=DB_PASS,
                db=DB_NAME,
                ip_type=IPTypes.PUBLIC,
            )

        _engine = sqlalchemy.create_engine(
            "postgresql+pg8000://",
            creator=_get_conn,
            pool_size=1,
            max_overflow=0,
            pool_pre_ping=True,
        )
    return _engine


# -- SQL ---------------------------------------------------------------------
INSERT_SQL = sqlalchemy.text("""
    INSERT INTO news_articles
        (id, title, description, url, source, author, image_url,
         category, language, country, published_at, fetched_at)
    VALUES
        (:id, :title, :description, :url, :source, :author, :image_url,
         :category, :language, :country, :published_at, :fetched_at)
    ON CONFLICT (url) DO NOTHING
""")


# -- RSS Feed Configuration --------------------------------------------------
# Each feed has: url, category, source label, and tier.
#   tier="breaking"  → fetched every 15 minutes (top stories, Odisha, sports)
#   tier="regular"   → fetched every 2 hours (deeper / niche categories)

RSS_FEEDS = [
    # ══════════════════════════════════════════════════════════════════════════
    # BREAKING TIER — every 15 min (fast-rotating headline feeds)
    # ══════════════════════════════════════════════════════════════════════════

    # ── Top Stories (India) ────────────────────────────────────────────────
    {
        "url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFZxYUdjU0FtVnVHZ0pKVGlnQVAB?hl=en-IN&gl=IN&ceid=IN:en",
        "category": "general",
        "source": "Google News",
        "tier": "breaking",
    },
    {
        "url": "https://feeds.feedburner.com/ndtvnews-top-stories",
        "category": "general",
        "source": "NDTV",
        "tier": "breaking",
    },
    {
        "url": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
        "category": "general",
        "source": "Times of India",
        "tier": "breaking",
    },

    # ── Odisha / Regional (breaking) ──────────────────────────────────────
    {
        "url": "https://news.google.com/rss/search?q=Odisha&hl=en-IN&gl=IN&ceid=IN:en",
        "category": "regional",
        "source": "Google News",
        "tier": "breaking",
    },
    {
        "url": "https://news.google.com/rss/search?q=Bhubaneswar+OR+Cuttack+OR+Puri+OR+Rourkela&hl=en-IN&gl=IN&ceid=IN:en",
        "category": "regional",
        "source": "Google News",
        "tier": "breaking",
    },
    {
        "url": "https://timesofindia.indiatimes.com/rssfeeds/4118235.cms",
        "category": "regional",
        "source": "Times of India",
        "tier": "breaking",
    },

    # ── Sports (breaking — live scores, match results) ────────────────────
    {
        "url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp1ZEdvU0FtVnVHZ0pKVGlnQVAB?hl=en-IN&gl=IN&ceid=IN:en",
        "category": "sports",
        "source": "Google News",
        "tier": "breaking",
    },
    {
        "url": "https://feeds.feedburner.com/ndtvsports-latest",
        "category": "sports",
        "source": "NDTV Sports",
        "tier": "breaking",
    },

    # ── Politics (breaking) ───────────────────────────────────────────────
    {
        "url": "https://news.google.com/rss/search?q=Odisha+government+OR+Odisha+politics&hl=en-IN&gl=IN&ceid=IN:en",
        "category": "politics",
        "source": "Google News",
        "tier": "breaking",
    },

    # ── Crime (breaking) ──────────────────────────────────────────────────
    {
        "url": "https://news.google.com/rss/search?q=crime+India+police&hl=en-IN&gl=IN&ceid=IN:en",
        "category": "crime",
        "source": "Google News",
        "tier": "breaking",
    },

    # ══════════════════════════════════════════════════════════════════════════
    # REGULAR TIER — every 2 hours (deeper coverage)
    # ══════════════════════════════════════════════════════════════════════════

    # ── General (deeper sources) ──────────────────────────────────────────
    {
        "url": "https://indianexpress.com/section/india/feed/",
        "category": "general",
        "source": "Indian Express",
        "tier": "regular",
    },
    {
        "url": "https://www.thehindu.com/news/national/feeder/default.rss",
        "category": "general",
        "source": "The Hindu",
        "tier": "regular",
    },

    # ── Sports (deeper) ──────────────────────────────────────────────────
    {
        "url": "https://timesofindia.indiatimes.com/rssfeeds/4719148.cms",
        "category": "sports",
        "source": "Times of India",
        "tier": "regular",
    },
    {
        "url": "https://indianexpress.com/section/sports/feed/",
        "category": "sports",
        "source": "Indian Express",
        "tier": "regular",
    },

    # ── Entertainment ─────────────────────────────────────────────────────
    {
        "url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNREpxYW5RU0FtVnVHZ0pKVGlnQVAB?hl=en-IN&gl=IN&ceid=IN:en",
        "category": "entertainment",
        "source": "Google News",
        "tier": "regular",
    },
    {
        "url": "https://timesofindia.indiatimes.com/rssfeeds/1081479906.cms",
        "category": "entertainment",
        "source": "Times of India",
        "tier": "regular",
    },
    {
        "url": "https://indianexpress.com/section/entertainment/feed/",
        "category": "entertainment",
        "source": "Indian Express",
        "tier": "regular",
    },

    # ── Business / Economy ────────────────────────────────────────────────
    {
        "url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pKVGlnQVAB?hl=en-IN&gl=IN&ceid=IN:en",
        "category": "business",
        "source": "Google News",
        "tier": "regular",
    },
    {
        "url": "https://feeds.feedburner.com/ndtvprofit-latest",
        "category": "business",
        "source": "NDTV Profit",
        "tier": "regular",
    },
    {
        "url": "https://indianexpress.com/section/business/feed/",
        "category": "business",
        "source": "Indian Express",
        "tier": "regular",
    },

    # ── Technology ────────────────────────────────────────────────────────
    {
        "url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtVnVHZ0pKVGlnQVAB?hl=en-IN&gl=IN&ceid=IN:en",
        "category": "technology",
        "source": "Google News",
        "tier": "regular",
    },
    {
        "url": "https://feeds.feedburner.com/gadgets360-latest",
        "category": "technology",
        "source": "NDTV Gadgets",
        "tier": "regular",
    },

    # ── Health ────────────────────────────────────────────────────────────
    {
        "url": "https://news.google.com/rss/search?q=health+India&hl=en-IN&gl=IN&ceid=IN:en",
        "category": "health",
        "source": "Google News",
        "tier": "regular",
    },

    # ── Education ─────────────────────────────────────────────────────────
    {
        "url": "https://news.google.com/rss/search?q=education+India+exam+university&hl=en-IN&gl=IN&ceid=IN:en",
        "category": "education",
        "source": "Google News",
        "tier": "regular",
    },
]


# -- Helpers -----------------------------------------------------------------

def _strip_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    return unescape(text).strip()


def _extract_image(entry) -> str | None:
    """Try to extract an image URL from an RSS entry."""
    # Check media:content
    media = entry.get("media_content", [])
    if media:
        for m in media:
            url = m.get("url", "")
            if url and ("image" in m.get("type", "image") or url.endswith((".jpg", ".jpeg", ".png", ".webp"))):
                return url

    # Check media:thumbnail
    thumb = entry.get("media_thumbnail", [])
    if thumb and thumb[0].get("url"):
        return thumb[0]["url"]

    # Check enclosures
    for enc in entry.get("enclosures", []):
        if enc.get("type", "").startswith("image") or enc.get("href", "").endswith(
            (".jpg", ".jpeg", ".png", ".webp")
        ):
            return enc.get("href") or enc.get("url")

    # Try to extract from description/summary HTML
    summary = entry.get("summary", "") or entry.get("description", "")
    if summary:
        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary)
        if img_match:
            return img_match.group(1)

    return None


def _parse_date(entry) -> datetime | None:
    """Parse published date from RSS entry."""
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                from calendar import timegm
                return datetime.fromtimestamp(timegm(parsed), tz=timezone.utc)
            except Exception:
                pass

    for field in ("published", "updated"):
        raw = entry.get(field)
        if raw:
            try:
                return parsedate_to_datetime(raw)
            except Exception:
                pass
            try:
                return datetime.fromisoformat(raw)
            except Exception:
                pass

    return None


def _resolve_google_news_url(url: str) -> str:
    """Google News RSS links are redirects. Try to extract the real URL."""
    # Google News URLs look like:
    # https://news.google.com/rss/articles/CBMi...
    # The actual URL is sometimes in the link after redirect
    # For now, return as-is — the frontend "View Original" will follow the redirect
    return url


def _extract_google_news_source(title: str) -> tuple[str, str]:
    """Google News titles often end with ' - Source Name'. Split them."""
    if " - " in title:
        parts = title.rsplit(" - ", 1)
        return parts[0].strip(), parts[1].strip()
    return title, "Google News"


def _fetch_feed(feed_config: dict) -> list[dict]:
    """Fetch and parse a single RSS feed, returning normalized article dicts."""
    url = feed_config["url"]
    default_category = feed_config.get("category", "general")
    default_source = feed_config.get("source", "Unknown")

    try:
        # Use httpx to fetch with timeout, then parse
        resp = httpx.get(url, timeout=20, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (compatible; VrittantBot/1.0)"
        })
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
    except Exception as e:
        print(f"Feed fetch failed ({default_source} / {default_category}): {e}")
        return []

    articles = []
    for entry in feed.entries[:30]:  # Cap per feed
        link = entry.get("link", "")
        title = _strip_html(entry.get("title", ""))
        if not link or not title:
            continue

        # For Google News, extract real source from title
        source = default_source
        if "news.google.com" in url:
            title, extracted_source = _extract_google_news_source(title)
            source = extracted_source

        description = _strip_html(
            entry.get("summary", "") or entry.get("description", "")
        )
        # Truncate very long descriptions
        if len(description) > 1000:
            description = description[:997] + "..."

        articles.append({
            "title": title,
            "description": description or None,
            "url": link,
            "source": source,
            "author": entry.get("author"),
            "image_url": _extract_image(entry),
            "category": default_category,
            "language": "en",
            "country": "in",
            "published_at": _parse_date(entry),
        })

    return articles


# -- Main Cloud Function entry point -----------------------------------------

@functions_framework.http
def fetch_news(request):
    """HTTP Cloud Function entry point.

    Supports a `tier` query parameter:
      - ?tier=breaking  → only breaking-tier feeds (called every 15 min)
      - ?tier=regular   → only regular-tier feeds (called every 2 hours)
      - (no tier / all) → all feeds
    """
    now = datetime.now(timezone.utc)

    # Determine which tier to fetch
    tier = (request.args.get("tier", "") or "").lower().strip()
    if tier in ("breaking", "regular"):
        feeds = [f for f in RSS_FEEDS if f.get("tier") == tier]
    else:
        feeds = RSS_FEEDS
        tier = "all"

    # Fetch feeds
    all_articles = []
    seen_urls = set()
    feed_stats = {}

    for feed_config in feeds:
        label = f"{feed_config['source']}/{feed_config['category']}"
        articles = _fetch_feed(feed_config)
        count = 0
        for a in articles:
            url = a["url"]
            if url not in seen_urls:
                seen_urls.add(url)
                all_articles.append(a)
                count += 1
        feed_stats[label] = count

    if not all_articles:
        return {
            "tier": tier,
            "inserted": 0,
            "total_fetched": 0,
            "feeds_checked": len(feeds),
            "message": "No articles returned from any feed",
        }

    # Prepare DB rows
    rows = []
    for a in all_articles:
        if not a["url"] or not a["title"]:
            continue
        rows.append({
            "id": uuid.uuid4().hex,
            "title": a["title"],
            "description": a["description"],
            "url": a["url"],
            "source": a["source"],
            "author": a.get("author"),
            "image_url": a.get("image_url"),
            "category": a["category"],
            "language": a.get("language", "en"),
            "country": a.get("country", "in"),
            "published_at": a.get("published_at"),
            "fetched_at": now,
        })

    if not rows:
        return {
            "tier": tier,
            "inserted": 0,
            "total_fetched": 0,
            "feeds_checked": len(feeds),
            "message": "No valid articles after filtering",
        }

    # Insert into DB
    inserted = 0
    try:
        engine = get_engine()
        with engine.connect() as conn:
            for row in rows:
                result = conn.execute(INSERT_SQL, row)
                inserted += result.rowcount
            conn.commit()
    except Exception as e:
        tb = traceback.format_exc()
        print(f"DB ERROR: {tb}")
        return ({"error": f"DB insert failed: {str(e)}"}, 500)

    return {
        "tier": tier,
        "inserted": inserted,
        "total_fetched": len(rows),
        "feeds_checked": len(feeds),
        "feed_stats": feed_stats,
    }
