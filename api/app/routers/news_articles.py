"""News articles — list, detail, Sarvam AI research + confirm-story endpoints."""

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Optional

import httpx
import trafilatura
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user, get_current_org_id
from ..models.news_article import NewsArticle
from ..models.story import Story
from ..models.user import User
from ..utils.tz import now_ist

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/news-articles", tags=["news-articles"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class NewsArticleResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    url: str
    source: Optional[str] = None
    author: Optional[str] = None
    image_url: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = None
    country: Optional[str] = None
    published_at: Optional[datetime] = None
    fetched_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ClusterArticle(BaseModel):
    """A related article within a cluster."""
    id: str
    title: str
    source: Optional[str] = None
    url: str
    published_at: Optional[datetime] = None


class ClusteredArticleResponse(BaseModel):
    """Lead article + related articles from other sources."""
    id: str
    title: str
    description: Optional[str] = None
    url: str
    source: Optional[str] = None
    author: Optional[str] = None
    image_url: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = None
    country: Optional[str] = None
    published_at: Optional[datetime] = None
    fetched_at: Optional[datetime] = None
    related: list[ClusterArticle] = []

    model_config = {"from_attributes": True}


class NewsArticleListResponse(BaseModel):
    articles: list[ClusteredArticleResponse]
    total: int
    sources: list[str] = []


class ResearchStoryRequest(BaseModel):
    instructions: Optional[str] = Field(None, max_length=500)
    word_count: int = Field(400, ge=100, le=2000)
    additional_article_ids: list[str] = Field(default_factory=list, max_length=2)  # max 2 extra = 3 total with primary


class ResearchStoryResponse(BaseModel):
    headline: str
    body: str
    category: Optional[str] = None
    location: Optional[str] = None
    source_url: str
    image_url: Optional[str] = None


class ConfirmStoryRequest(BaseModel):
    headline: str
    paragraphs: list[dict]
    category: Optional[str] = None
    location: Optional[str] = None


class ConfirmStoryResponse(BaseModel):
    story_id: str
    headline: str
    message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------





def _cluster_articles(articles: list[NewsArticle], db: Session) -> list[ClusteredArticleResponse]:
    """Group articles by title similarity using pg_trgm.

    For each batch of articles, find pairs with similarity > 0.4 on title,
    then merge them into clusters (lead = most recent, rest = related).
    """
    if not articles:
        return []

    article_ids = [a.id for a in articles]
    article_map = {a.id: a for a in articles}

    # Find similar pairs among the fetched articles using trigram similarity
    # Only cluster articles from different sources (same-source dupes are rare)
    try:
        pairs = db.execute(
            text("""
                SELECT a.id AS id_a, b.id AS id_b, similarity(a.title, b.title) AS sim
                FROM news_articles a
                JOIN news_articles b ON a.id < b.id
                    AND a.source IS DISTINCT FROM b.source
                WHERE a.id = ANY(:ids) AND b.id = ANY(:ids)
                    AND similarity(a.title, b.title) > 0.4
                ORDER BY sim DESC
            """),
            {"ids": article_ids},
        ).fetchall()
    except Exception as exc:
        logger.warning("Clustering failed (pg_trgm may not be on news_articles): %s", exc)
        pairs = []

    # Union-Find to merge clusters
    parent = {aid: aid for aid in article_ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for row in pairs:
        union(row[0], row[1])

    # Group by cluster root
    clusters: dict[str, list[str]] = {}
    for aid in article_ids:
        root = find(aid)
        clusters.setdefault(root, []).append(aid)

    # Build response: lead = most recent in cluster, rest = related
    seen = set()
    result = []
    for aid in article_ids:  # preserve original order
        root = find(aid)
        if root in seen:
            continue
        seen.add(root)

        cluster_ids = clusters[root]
        # Sort by published_at descending, lead is most recent
        cluster_articles = sorted(
            [article_map[cid] for cid in cluster_ids],
            key=lambda a: a.published_at or datetime.min,
            reverse=True,
        )
        lead = cluster_articles[0]
        related = [
            ClusterArticle(
                id=a.id,
                title=a.title,
                source=a.source,
                url=a.url,
                published_at=a.published_at,
            )
            for a in cluster_articles[1:]
        ]

        result.append(ClusteredArticleResponse(
            id=lead.id,
            title=lead.title,
            description=lead.description,
            url=lead.url,
            source=lead.source,
            author=lead.author,
            image_url=lead.image_url,
            category=lead.category,
            language=lead.language,
            country=lead.country,
            published_at=lead.published_at,
            fetched_at=lead.fetched_at,
            related=related,
        ))

    return result


# ---------------------------------------------------------------------------
# GET /admin/news-articles  — paginated list with clustering
# ---------------------------------------------------------------------------

@router.get("", response_model=NewsArticleListResponse)
def list_news_articles(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(12, ge=1, le=100),
):
    q = db.query(NewsArticle)

    if search:
        q = q.filter(NewsArticle.title.ilike(f"%{search}%"))
    if category:
        q = q.filter(NewsArticle.category == category)
    if source:
        q = q.filter(NewsArticle.source == source)
    if country:
        q = q.filter(NewsArticle.country == country)

    total = q.count()
    articles = (
        q.order_by(NewsArticle.published_at.desc().nullslast())
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Cluster similar articles
    clustered = _cluster_articles(articles, db)

    # Only fetch distinct sources on unfiltered first-page load (no filters applied)
    if not any([search, category, source, country]) and offset == 0:
        distinct_sources = (
            db.query(NewsArticle.source)
            .filter(NewsArticle.source.isnot(None))
            .distinct()
            .all()
        )
        source_list = sorted([s[0] for s in distinct_sources if s[0]])
    else:
        source_list = []

    return NewsArticleListResponse(articles=clustered, total=total, sources=source_list)


# ---------------------------------------------------------------------------
# GET /admin/news-articles/search-by-title  — trigram similarity on title
# ---------------------------------------------------------------------------

@router.get("/search-by-title", response_model=list[NewsArticleResponse])
async def search_news_articles_by_title(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=30),
    threshold: float = Query(0.12, ge=0.05, le=1.0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Search news articles by title using pg_trgm similarity.
    Auto-translates Odia queries to English for cross-language matching."""

    # Translate if query contains Odia script
    search_terms = [q]
    has_odia = bool(re.search(r'[\u0B00-\u0B7F]', q))
    if has_odia:
        try:
            translate_url = f"{settings.SARVAM_BASE_URL}/translate"
            headers = {
                "api-subscription-key": settings.SARVAM_API_KEY,
                "Content-Type": "application/json",
            }
            payload = {
                "input": q,
                "source_language_code": "od-IN",
                "target_language_code": "en-IN",
                "model": "mayura:v1",
            }
            async with httpx.AsyncClient() as client:
                resp = await client.post(translate_url, json=payload, headers=headers, timeout=15.0)
                resp.raise_for_status()
                translated = resp.json().get("translated_text", "")
                if translated and translated.strip() and translated != q:
                    search_terms.append(translated.strip())
                    logger.info("search-by-title: translated %r -> %r", q, translated)
        except Exception as exc:
            logger.warning("search-by-title: translate failed: %s", exc)

    # Also add individual significant words from translated text for partial matching
    for term in list(search_terms):
        words = term.split()
        for w in words:
            if len(w) >= 4 and w.lower() not in ('with', 'from', 'that', 'this', 'have', 'been', 'were', 'they', 'their', 'about', 'after', 'into', 'also', 'than', 'over') and w not in search_terms:
                search_terms.append(w)

    logger.info("search-by-title: searching with %d terms: %s", len(search_terms), search_terms[:5])

    # Search with all terms using word_similarity (better for substring matching), deduplicate by id
    seen = {}
    for term in search_terms:
        rows = db.execute(
            text("""
                SELECT id, title, description, url, source, author, image_url,
                       category, language, country, published_at, fetched_at,
                       GREATEST(
                           similarity(title, :q),
                           word_similarity(:q, title)
                       ) AS sim
                FROM news_articles
                WHERE similarity(title, :q) > :threshold
                   OR word_similarity(:q, title) > :threshold
                ORDER BY sim DESC
                LIMIT :lim
            """),
            {"q": term, "threshold": threshold, "lim": limit},
        ).fetchall()
        for r in rows:
            if r.id not in seen or r.sim > seen[r.id].sim:
                seen[r.id] = r

    # Sort by best similarity and limit
    results = sorted(seen.values(), key=lambda r: r.sim, reverse=True)[:limit]

    return [
        NewsArticleResponse(
            id=r.id, title=r.title, description=r.description, url=r.url,
            source=r.source, author=r.author, image_url=r.image_url,
            category=r.category, language=r.language, country=r.country,
            published_at=r.published_at, fetched_at=r.fetched_at,
        )
        for r in results
    ]


# ---------------------------------------------------------------------------
# GET /admin/news-articles/{article_id}
# ---------------------------------------------------------------------------

@router.get("/{article_id}", response_model=NewsArticleResponse)
def get_news_article(
    article_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    article = db.query(NewsArticle).filter(NewsArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    return article


# ---------------------------------------------------------------------------
# GET /admin/news-articles/{article_id}/related
# Find all articles about the same topic using trigram similarity
# ---------------------------------------------------------------------------

@router.get("/{article_id}/related", response_model=list[NewsArticleResponse])
def get_related_articles(
    article_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    threshold: float = Query(0.25, ge=0.1, le=1.0),
    limit: int = Query(10, ge=1, le=30),
):
    """Find articles covering the same story using pg_trgm title similarity."""
    article = db.query(NewsArticle).filter(NewsArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")

    try:
        rows = db.execute(
            text("""
                SELECT id, title, description, url, source, author, image_url,
                       category, language, country, published_at, fetched_at,
                       similarity(title, :title) AS sim
                FROM news_articles
                WHERE id != :article_id
                  AND similarity(title, :title) > :threshold
                ORDER BY sim DESC
                LIMIT :lim
            """),
            {"title": article.title, "article_id": article_id, "threshold": threshold, "lim": limit},
        ).fetchall()

        return [
            NewsArticleResponse(
                id=r.id, title=r.title, description=r.description, url=r.url,
                source=r.source, author=r.author, image_url=r.image_url,
                category=r.category, language=r.language, country=r.country,
                published_at=r.published_at, fetched_at=r.fetched_at,
            )
            for r in rows
        ]
    except Exception as exc:
        logger.warning("Related articles query failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# POST /admin/news-articles/{article_id}/research-story
# Sarvam AI generates the Odia article with user instructions + length control
# ---------------------------------------------------------------------------

def _scrape_sync(url: str) -> str | None:
    """Scrape article using scrapling (anti-bot bypass) + trafilatura."""
    try:
        from scrapling import Fetcher
        fetcher = Fetcher()
        resp = fetcher.get(url, timeout=15)
        if resp.status != 200:
            logger.warning("Scrapling %s returned status %d", url, resp.status)
            return None
        html = resp.response.text if hasattr(resp, 'response') else str(resp)
        text = trafilatura.extract(html, include_comments=False, include_tables=False)
        if text and len(text.strip()) > 150:
            return text.strip()
        # Fallback: CSS selectors
        for selector in ['[itemprop=articleBody]', 'article', '.post-content']:
            els = resp.css(selector)
            if els:
                el_text = els[0].get_all_text(ignore_tags=('script', 'style', 'nav', 'footer', 'header', 'aside'))
                if el_text and len(el_text.strip()) > 150:
                    return el_text.strip()
    except ImportError:
        logger.info("scrapling not available, skipping")
    except Exception as exc:
        logger.warning("Scrapling failed for %s: %s", url, exc)
    return None


async def _fetch_article_content(url: str) -> str | None:
    """Scrape article content — tries scrapling first, then plain httpx+trafilatura."""
    import asyncio
    loop = asyncio.get_event_loop()

    # Try scrapling (handles anti-bot)
    text = await loop.run_in_executor(None, _scrape_sync, url)
    if text:
        return text

    # Fallback: plain httpx + trafilatura
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                extracted = trafilatura.extract(resp.text, include_comments=False, include_tables=False)
                if extracted and len(extracted.strip()) > 150:
                    return extracted.strip()
    except Exception as exc:
        logger.warning("httpx fallback failed for %s: %s", url, exc)
    return None


def _build_research_prompt(word_count: int, instructions: str | None) -> str:
    """Build the system prompt for article generation."""
    prompt = f"""You are a senior Odia journalist working for a major Odisha newspaper.

Given one or more English news articles with their full content, write an Odia newspaper article suitable for print publication.

LENGTH: Write approximately {word_count} words. Match this word count closely.

Your output must be a valid JSON object with these keys:
- "headline": A concise, impactful Odia headline (10-20 words max)
- "body": The full Odia article following the length guidance above. Well-structured with proper paragraphs. Cover key facts, context, and quotes. Write in professional journalistic style.
- "category": One of: politics, sports, crime, business, entertainment, education, health, technology, urban_planning, sustainability, economics, lifestyle, finance, disaster, other
- "location": The primary location relevant to this news (city/state in India), or empty string if not applicable

CRITICAL RULES:
- You MUST write the headline and body entirely in Odia (ଓଡ଼ିଆ) script. Every single sentence must be in Odia. Do NOT write in English or Hindi.
- Do NOT include any markdown, code blocks, or explanation — just the raw JSON
- Make the article informative and comprehensive
- The body MUST be approximately {word_count} Odia words. Do not stop early. Keep writing until you reach the target length."""

    if instructions:
        prompt += f"\n\nADDITIONAL EDITOR INSTRUCTIONS: {instructions}"

    return prompt


@router.post("/{article_id}/research-story", response_model=ResearchStoryResponse)
async def research_story_from_article(
    article_id: str,
    body: ResearchStoryRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    article = db.query(NewsArticle).filter(NewsArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")

    # Parse request body (optional — backwards compatible with no body)
    instructions = body.instructions if body else None
    word_count = body.word_count if body else 400
    extra_ids = body.additional_article_ids if body else []
    extra_ids = extra_ids[:2]  # Hard cap: max 2 extra (3 total with primary)

    system_prompt = _build_research_prompt(word_count, instructions)

    # Gather all source articles (max 3)
    all_articles = [article]
    if extra_ids:
        extra_articles = db.query(NewsArticle).filter(NewsArticle.id.in_(extra_ids)).all()
        all_articles.extend(extra_articles)

    # Scrape full content from all article URLs concurrently
    import asyncio
    scrape_tasks = [_fetch_article_content(a.url) for a in all_articles]
    scraped_contents = await asyncio.gather(*scrape_tasks)

    for i, (a, sc) in enumerate(zip(all_articles, scraped_contents)):
        logger.info("Source %d [%s]: scraped %d chars", i + 1, a.source or 'unknown', len(sc) if sc else 0)

    # Build user prompt from primary + additional source articles
    source_blocks = []
    for i, (src_article, scraped) in enumerate(zip(all_articles, scraped_contents), 1):
        label = "Primary" if i == 1 else f"{i}"
        content_text = scraped or src_article.description or "No content available"
        source_blocks.append(f"""--- SOURCE {i} ({label}) ---
Title: {src_article.title}
Source: {src_article.source or 'Unknown'}
Category: {src_article.category or 'general'}
Published: {src_article.published_at or 'Unknown'}

Full Article Content:
{content_text}""")

    user_prompt = "\n\n".join(source_blocks)
    if len(source_blocks) > 1:
        user_prompt += f"\n\nCombine information from all {len(source_blocks)} sources above into a single comprehensive article."
    user_prompt += f"\n\nRemember: Write the entire article in Odia (ଓଡ଼ିଆ) script. Target length: {word_count} words."

    # Defaults (fallback)
    headline = article.title
    gen_body = article.description or ""
    gen_category = article.category or "general"
    location = ""

    # Odia uses ~4-6 tokens per word + buffer for JSON wrapper + thinking
    max_tokens = min(max(word_count * 7, 3072), 16384)

    try:
        # Use Sarvam AI (sarvam-30b) instead of OpenAI
        url = f"{settings.SARVAM_BASE_URL}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.SARVAM_API_KEY}",
            "Content-Type": "application/json",
        }

        # Inject no-markdown instruction
        messages = [
            {"role": "system", "content": system_prompt + "\n\nDo not output markdown formatting (no **, ##, -, etc). Return plain text only."},
            {"role": "user", "content": user_prompt},
        ]

        payload = {
            "model": "sarvam-30b",
            "messages": messages,
            "temperature": 0.6,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            raw = data["choices"][0]["message"]["content"] or ""

        logger.info("Sarvam raw (before strip) length: %d, first 300: %s", len(raw), raw[:300])

        # Strip <think>/<thinking> reasoning tags — keep everything outside them
        raw = re.sub(r'<think(?:ing)?>[\s\S]*?</think(?:ing)?>', '', raw)
        # If there's an unclosed <think> tag, strip from that tag onwards
        # But first check if the JSON is AFTER the thinking block
        if '<think' in raw and '{' in raw:
            # Keep everything after the last closing think tag, or after unclosed think content
            think_end = raw.rfind('</think')
            if think_end >= 0:
                close_bracket = raw.find('>', think_end)
                raw = raw[close_bracket + 1:] if close_bracket >= 0 else raw
            else:
                # Unclosed think — find the JSON part
                json_start = raw.find('{')
                if json_start >= 0:
                    raw = raw[json_start:]
        elif '<think' not in raw:
            pass  # No think tags, keep as-is
        else:
            # Has unclosed <think> but no JSON — strip it
            raw = re.sub(r'<think(?:ing)?>[\s\S]*', '', raw)
        raw = raw.strip()

        logger.info("Sarvam raw (after strip) length: %d, first 300: %s", len(raw), raw[:300])

        # Parse JSON from response — try multiple strategies
        cleaned = raw
        # Strip markdown code fences
        if "```" in cleaned:
            cleaned = re.sub(r'```(?:json)?\s*', '', cleaned).strip()

        # Try to extract JSON object if there's extra text around it
        json_match = re.search(r'\{[\s\S]*\}', cleaned)
        if json_match:
            cleaned = json_match.group(0)

        parsed = None
        # Strategy 1: direct parse
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Strategy 2: fix unescaped newlines inside JSON string values
        if not parsed:
            try:
                # Replace actual newlines inside strings with \n escape
                fixed = re.sub(r'(?<=: ")([\s\S]*?)(?="(?:,|\s*\}))',
                    lambda m: m.group(1).replace('\n', '\\n').replace('\r', ''),
                    cleaned)
                parsed = json.loads(fixed)
            except (json.JSONDecodeError, Exception):
                pass

        # Strategy 3: extract fields manually with regex
        if not parsed:
            try:
                h_match = re.search(r'"headline"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
                b_match = re.search(r'"body"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
                c_match = re.search(r'"category"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
                l_match = re.search(r'"location"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
                if h_match or b_match:
                    parsed = {
                        "headline": h_match.group(1) if h_match else "",
                        "body": b_match.group(1) if b_match else "",
                        "category": c_match.group(1) if c_match else "general",
                        "location": l_match.group(1) if l_match else "",
                    }
            except Exception:
                pass

        if parsed and isinstance(parsed, dict):
            headline = parsed.get("headline", headline)
            gen_body = parsed.get("body", gen_body)
            gen_category = parsed.get("category", gen_category)
            location = parsed.get("location", location)
            # Clean up escaped newlines for display
            gen_body = gen_body.replace('\\n', '\n').strip()
            logger.info("Sarvam research completed for article %s (word_count=%d)", article_id, word_count)
        else:
            logger.warning("Sarvam returned non-JSON for article %s, raw[:500]: %s", article_id, raw[:500])
            if raw.strip():
                gen_body = raw.strip()
    except Exception as exc:
        logger.error("Sarvam research failed for article %s: %s", article_id, exc)
        # Fall back to defaults

    return ResearchStoryResponse(
        headline=headline,
        body=gen_body,
        category=gen_category,
        location=location,
        source_url=article.url,
        image_url=article.image_url,
    )


# ---------------------------------------------------------------------------
# POST /admin/news-articles/{article_id}/confirm-story
# Saves the previewed story to the DB
# ---------------------------------------------------------------------------

@router.post("/{article_id}/confirm-story", response_model=ConfirmStoryResponse)
async def confirm_story_from_article(
    article_id: str,
    body: ConfirmStoryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_id: str = Depends(get_current_org_id),
):
    article = db.query(NewsArticle).filter(NewsArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")

    # Build paragraphs
    paragraphs = body.paragraphs if body.paragraphs else []

    # Ensure we include the article image if not already present
    has_image = any(p.get("type") == "media" for p in paragraphs)
    if article.image_url and not has_image:
        paragraphs.append({
            "text": "",
            "type": "media",
            "media_path": article.image_url,
            "media_type": "photo",
            "media_name": "news_image",
        })

    now = now_ist()
    story = Story(
        id=str(uuid.uuid4()),
        reporter_id=current_user.id,
        organization_id=org_id,
        headline=body.headline,
        category=body.category or article.category or "general",
        location=body.location or "",
        paragraphs=paragraphs,
        status="submitted",
        source=article.url,
        submitted_at=now,
        created_at=now,
        updated_at=now,
    )
    story.refresh_search_text()
    db.add(story)
    db.commit()

    return ConfirmStoryResponse(
        story_id=story.id,
        headline=body.headline,
        message="Story created from news article",
    )
