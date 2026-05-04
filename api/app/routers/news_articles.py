"""News articles — list, detail, Sarvam AI research + confirm-story endpoints.

Thin HTTP layer over ``services/news_scraper``. Scraping, parsing, prompt
construction, and clustering all live in the service module so they can be
unit-tested in isolation; this router only handles request/response shape,
DB I/O, and the Sarvam HTTP call (which is endpoint-specific glue).
"""

import asyncio
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user, get_current_org_id
from ..models.news_article import NewsArticle
from ..models.story import Story
from ..models.user import User
from ..services import sarvam_client
from ..services.news_scraper import (
    build_research_prompt,
    build_research_user_prompt,
    build_title_search_sql,
    cluster_articles_by_title,
    expand_search_terms,
    fetch_article_content,
    parse_sarvam_response,
    strip_think_tags,
)
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
    # Legacy field — kept for backward compat. Frontend should prefer
    # `source_article_ids` which lets the user explicitly pick any subset
    # of source articles (including deselecting the route's primary).
    additional_article_ids: list[str] = Field(default_factory=list, max_length=3)
    # Explicit list of source articles to feed the LLM. Takes precedence
    # over the legacy primary+additionals composition when provided.
    source_article_ids: Optional[list[str]] = Field(None, max_length=4)


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


def _get_article_or_404(db: Session, article_id: str) -> NewsArticle:
    """Lookup helper. NewsArticle is NOT org-scoped (global news pool), so
    ``get_owned_or_404`` doesn't apply here — every org browses the same
    fetched articles. We still want a single canonical 404 string."""
    article = db.query(NewsArticle).filter(NewsArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    return article


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
    # Default rolling window: only the last 7 days of articles. The full
    # corpus is ~30k rows and the row-level fuzzy clustering downstream
    # is O(n²) in the page result set, so widening the date filter has a
    # real cost. Reviewers almost never look past the trailing week (the
    # whole point of the feed is to surface stories worth covering NOW).
    # Reviewers who DO want the full archive pass days_back=0.
    days_back: int = Query(7, ge=0, le=365),
    offset: int = Query(0, ge=0),
    limit: int = Query(12, ge=1, le=100),
):
    q = db.query(NewsArticle)

    # Apply the rolling window before any other filter so PostgreSQL
    # can use the (published_at) index to short-circuit the scan. With
    # default days_back=7 this typically reduces the working set ~10x.
    if days_back > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        q = q.filter(NewsArticle.published_at >= cutoff)
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

    # Cluster similar articles (service handles pg_trgm + union-find)
    clustered = [
        ClusteredArticleResponse(
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
            related=[
                ClusterArticle(
                    id=a.id,
                    title=a.title,
                    source=a.source,
                    url=a.url,
                    published_at=a.published_at,
                )
                for a in related
            ],
        )
        for lead, related in cluster_articles_by_title(articles, db)
    ]

    # Only fetch distinct sources on unfiltered first-page load
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
            from ..services import gemini_client
            with sarvam_client.cost_context(bucket="search"):
                translated = (await gemini_client.translate(
                    text=q, source_lang="Odia", target_lang="English", timeout=15.0,
                )).strip()
            if translated and translated != q:
                search_terms.append(translated)
                logger.info("search-by-title: translated %r -> %r", q, translated)
        except Exception as exc:
            logger.warning("search-by-title: translate failed: %s", exc)

    # Expand to significant words + cap, then build one OR'd SQL query
    search_terms = expand_search_terms(search_terms)
    logger.info("search-by-title: searching with %d terms: %s", len(search_terms), search_terms)
    sql, params = build_title_search_sql(search_terms, threshold=threshold, limit=limit)
    rows = db.execute(text(sql), params).fetchall()

    return [
        NewsArticleResponse(
            id=r.id, title=r.title, description=r.description, url=r.url,
            source=r.source, author=r.author, image_url=r.image_url,
            category=r.category, language=r.language, country=r.country,
            published_at=r.published_at, fetched_at=r.fetched_at,
        )
        for r in rows
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
    return _get_article_or_404(db, article_id)


# ---------------------------------------------------------------------------
# GET /admin/news-articles/{article_id}/related
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
    article = _get_article_or_404(db, article_id)

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
# ---------------------------------------------------------------------------

@router.post("/{article_id}/research-story", response_model=ResearchStoryResponse)
async def research_story_from_article(
    article_id: str,
    body: ResearchStoryRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    article = _get_article_or_404(db, article_id)

    instructions = body.instructions if body else None
    word_count = body.word_count if body else 400
    explicit_source_ids = (body.source_article_ids if body else None)
    extra_ids = (body.additional_article_ids if body else [])[:3]

    system_prompt = build_research_prompt(word_count, instructions)

    # Pick the source-article list. New flow: frontend sends the full
    # `source_article_ids` (whatever the user selected, primary included or
    # not). Legacy flow: route's primary article + up to 3 additionals.
    if explicit_source_ids:
        # Preserve the user's selection order. Look up in one query, then
        # reorder to match the requested list.
        rows = db.query(NewsArticle).filter(NewsArticle.id.in_(explicit_source_ids)).all()
        by_id = {a.id: a for a in rows}
        all_articles = [by_id[sid] for sid in explicit_source_ids if sid in by_id]
        # If none of the requested sources resolved, fall back to the
        # route's primary so we never call the LLM with zero content.
        if not all_articles:
            all_articles = [article]
    else:
        all_articles = [article]
        if extra_ids:
            all_articles.extend(
                db.query(NewsArticle).filter(NewsArticle.id.in_(extra_ids)).all()
            )
    scraped_contents = await asyncio.gather(*(fetch_article_content(a.url) for a in all_articles))
    for i, (a, sc) in enumerate(zip(all_articles, scraped_contents)):
        logger.info("Source %d [%s]: scraped %d chars", i + 1, a.source or 'unknown', len(sc) if sc else 0)

    # Assemble user prompt (pure helper)
    sources = [
        (
            a.title,
            a.source,
            a.category,
            a.published_at,
            scraped or a.description or "No content available",
        )
        for a, scraped in zip(all_articles, scraped_contents)
    ]
    user_prompt = build_research_user_prompt(sources, word_count=word_count)

    # Defaults (fallback if Sarvam fails or returns garbage)
    headline = article.title
    gen_body = article.description or ""
    gen_category = article.category or "general"
    location = ""

    # Odia uses ~4-6 tokens per word + buffer for JSON wrapper + reasoning.
    # We set `reasoning_effort="high"` below — counter-intuitively, that's
    # the ONLY setting that produces a clean answer. With low/medium/null
    # the model rambles in `reasoning_content` until it hits max_tokens and
    # the actual `content` comes back empty. High effort budgets reasoning
    # efficiently and leaves room for the JSON answer. Sarvam pro tier caps
    # sarvam-30b output at 8192 tokens; we stay well below to avoid runaway.
    max_tokens = min(max(word_count * 8, 4000), 8192)

    try:
        from ..services import gemini_client
        full_system = system_prompt + "\n\nDo not output markdown formatting (no **, ##, -, etc). Return plain text only."

        # This is the "Research with AI" path — the user is creating a
        # story FROM a news article, so we attribute to the resulting story
        # via the route's outer cost_context (set in confirm_story).
        # If invoked outside that context, fall back to the news_fetcher
        # bucket so the cost still lands somewhere visible.
        ctx = sarvam_client.current_cost_context()
        if ctx.story_id is None and ctx.bucket is None:
            with sarvam_client.cost_context(bucket="news_fetcher"):
                raw = await gemini_client.chat(
                    prompt=user_prompt,
                    system=full_system,
                    model="gemini-2.5-flash",
                    max_tokens=max_tokens,
                    temperature=0.6,
                    timeout=180.0,
                )
        else:
            raw = await gemini_client.chat(
                prompt=user_prompt,
                system=full_system,
                model="gemini-2.5-flash",
                max_tokens=max_tokens,
                temperature=0.6,
                timeout=180.0,
            )

        logger.info("Gemini raw length: %d, first 300: %s", len(raw), raw[:300])

        parsed = parse_sarvam_response(raw)
        if parsed:
            headline = parsed.get("headline", headline)
            gen_body = parsed.get("body", gen_body)
            gen_category = parsed.get("category", gen_category)
            location = parsed.get("location", location)
            gen_body = gen_body.replace('\\n', '\n').strip()

            # Script sanity check — Sarvam occasionally ignores the
            # "Odia script only" rule and returns Romanised Odia
            # ("Nashik-ra bibadiya godman..."). Detect that by the
            # ratio of Odia-block (U+0B00–U+0B7F) characters to total
            # letters; retry once with a sharper instruction if low.
            def _odia_ratio(text: str) -> float:
                letters = [c for c in text if c.isalpha()]
                if not letters:
                    return 1.0
                odia = sum(1 for c in letters if "\u0b00" <= c <= "\u0b7f")
                return odia / len(letters)

            ratio = _odia_ratio(gen_body)
            if ratio < 0.6:
                logger.warning(
                    "Gemini returned non-Odia-script body for article %s (odia_ratio=%.2f); retrying with stricter prompt",
                    article_id,
                    ratio,
                )
                strict_system = (
                    full_system
                    + "\n\nYour previous attempt used Romanised Odia (Latin letters spelling Odia phonetically). That is INVALID."
                    + " Rewrite headline AND body using ONLY characters in the Odia Unicode block (U+0B00–U+0B7F)."
                    + " Every word — including names of people and places — must be in Odia script."
                )
                retry_raw = await gemini_client.chat(
                    prompt=user_prompt,
                    system=strict_system,
                    model="gemini-2.5-flash",
                    max_tokens=max_tokens,
                    temperature=0.4,
                    timeout=180.0,
                )
                retry_parsed = parse_sarvam_response(retry_raw)
                if retry_parsed:
                    retry_body = retry_parsed.get("body", "").replace('\\n', '\n').strip()
                    if _odia_ratio(retry_body) > ratio:
                        headline = retry_parsed.get("headline", headline)
                        gen_body = retry_body
                        gen_category = retry_parsed.get("category", gen_category)
                        location = retry_parsed.get("location", location)
                        logger.info("Gemini retry produced valid Odia script for article %s", article_id)

            logger.info("Gemini research completed for article %s (word_count=%d)", article_id, word_count)
        else:
            logger.warning("Gemini returned non-JSON for article %s, raw[:500]: %s", article_id, raw[:500])
            if raw.strip():
                gen_body = raw.strip()
    except Exception as exc:
        logger.error("Gemini research failed for article %s: %s", article_id, exc)
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
# ---------------------------------------------------------------------------

@router.post("/{article_id}/confirm-story", response_model=ConfirmStoryResponse)
async def confirm_story_from_article(
    article_id: str,
    body: ConfirmStoryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_id: str = Depends(get_current_org_id),
):
    article = _get_article_or_404(db, article_id)

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
    # Auto-assign to the user who researched/created the story so it lands
    # straight in their personal queue. They invoked the "generate from news"
    # flow, so they own follow-through. Reviewers can still reassign later.
    from ..services.story_seq import assign_next_seq
    story = Story(
        id=str(uuid.uuid4()),
        reporter_id=current_user.id,
        organization_id=org_id,
        seq_no=assign_next_seq(db, org_id),
        headline=body.headline,
        category=body.category or article.category or "general",
        location=body.location or "",
        paragraphs=paragraphs,
        status="submitted",
        source=article.url,
        submitted_at=now,
        created_at=now,
        updated_at=now,
        assigned_to=current_user.id,
        assigned_match_reason="creator",
    )
    story.refresh_search_text()
    db.add(story)
    db.commit()

    return ConfirmStoryResponse(
        story_id=story.id,
        headline=body.headline,
        message="Story created from news article",
    )
