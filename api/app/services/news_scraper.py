"""News scraping, parsing, and normalization helpers.

Extracted from ``routers/news_articles.py`` so the router can stay thin
(HTTP shape only). Everything here is either pure (prompt building, LLM
response parsing, union-find clustering core) or contained I/O around a
single URL (article fetching). The pure functions are unit-tested in
``tests/test_news_scraper.py``; the I/O ones are smoke-tested via the
research-story endpoint integration path.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any, Iterable

import httpx
import trafilatura
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models.news_article import NewsArticle

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt construction (pure)
# ---------------------------------------------------------------------------


def build_research_prompt(word_count: int, instructions: str | None) -> str:
    """Build the system prompt for Sarvam article generation.

    The word-count anchor is repeated in the closing reminder on purpose —
    without it Sarvam consistently truncates at ~150 words even when the
    LENGTH directive says otherwise. Editor instructions are appended under
    a clearly labelled section so the LLM doesn't fold them into the rules.
    """
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


# Stop-words that get stripped from search-term expansion. Short common
# English words that produce noisy trigram matches against article titles.
_SEARCH_STOP_WORDS = {
    'with', 'from', 'that', 'this', 'have', 'been', 'were', 'they', 'their',
    'about', 'after', 'into', 'also', 'than', 'over', 'will', 'would', 'could',
    'should', 'being', 'does', 'more', 'most', 'some', 'such', 'what', 'when',
    'where', 'which', 'while',
}

_SEARCH_TERM_CAP = 6


def expand_search_terms(seed_terms: list[str]) -> list[str]:
    """Expand seed phrases with their significant individual words.

    Keeps the original phrases first (best signal), then appends each word
    of length >= 4 that isn't a stop-word and isn't already in the list.
    Capped at ``_SEARCH_TERM_CAP`` so the generated SQL doesn't explode
    into 20+ ``OR`` branches when a translation is long.
    """
    terms = list(seed_terms)
    for term in list(terms):
        for w in term.split():
            if len(w) >= 4 and w.lower() not in _SEARCH_STOP_WORDS and w not in terms:
                terms.append(w)
    return terms[:_SEARCH_TERM_CAP]


def build_title_search_sql(
    terms: list[str],
    *,
    threshold: float,
    limit: int,
) -> tuple[str, dict[str, object]]:
    """Build the parameterised pg_trgm title-search SQL.

    Returns ``(sql, params)`` where ``params`` holds one entry per term
    (``q0``, ``q1``, ...) plus ``threshold`` and ``lim``. Each term is
    matched with both ``similarity()`` (full-string) and ``word_similarity()``
    (substring) so single-word queries still hit longer titles.
    """
    sim_parts: list[str] = []
    where_parts: list[str] = []
    params: dict[str, object] = {"threshold": threshold, "lim": limit}
    for i, term in enumerate(terms):
        key = f"q{i}"
        params[key] = term
        sim_parts.append(f"similarity(title, :{key})")
        sim_parts.append(f"word_similarity(:{key}, title)")
        where_parts.append(
            f"(similarity(title, :{key}) > :threshold "
            f"OR word_similarity(:{key}, title) > :threshold)"
        )

    sim_expr = f"GREATEST({', '.join(sim_parts)})"
    where_expr = " OR ".join(where_parts)
    sql = f"""
        SELECT id, title, description, url, source, author, image_url,
               category, language, country, published_at, fetched_at,
               {sim_expr} AS sim
        FROM news_articles
        WHERE {where_expr}
        ORDER BY sim DESC
        LIMIT :lim
    """
    return sql, params


def build_research_user_prompt(
    sources: list[tuple[str, str | None, str | None, object, str]],
    *,
    word_count: int,
) -> str:
    """Build the user-message prompt for Sarvam research-story.

    ``sources`` is a list of ``(title, source_name, category, published_at,
    content_text)`` tuples — first one is the primary article, the rest are
    additional context. Returns the assembled prompt with the Odia-script
    reminder appended (Sarvam will lapse back to English without it).
    """
    blocks: list[str] = []
    for i, (title, src_name, category, published_at, content_text) in enumerate(sources, 1):
        label = "Primary" if i == 1 else f"{i}"
        blocks.append(
            f"--- SOURCE {i} ({label}) ---\n"
            f"Title: {title}\n"
            f"Source: {src_name or 'Unknown'}\n"
            f"Category: {category or 'general'}\n"
            f"Published: {published_at or 'Unknown'}\n\n"
            f"Full Article Content:\n{content_text}"
        )
    prompt = "\n\n".join(blocks)
    if len(blocks) > 1:
        prompt += (
            f"\n\nCombine information from all {len(blocks)} sources above "
            f"into a single comprehensive article."
        )
    prompt += (
        f"\n\nRemember: Write the entire article in Odia (ଓଡ଼ିଆ) script. "
        f"Target length: {word_count} words."
    )
    return prompt


# ---------------------------------------------------------------------------
# Sarvam response cleaning + parsing (pure)
# ---------------------------------------------------------------------------


def strip_think_tags(raw: str) -> str:
    """Remove ``<think>``/``<thinking>`` reasoning blocks from an LLM response.

    Sarvam's reasoning model sometimes wraps its scratchpad in ``<think>``
    tags before emitting the JSON answer. Closed blocks are stripped wholesale.
    Unclosed ``<think>`` followed by JSON keeps the JSON portion (we rely on
    the first ``{`` to mark the answer); unclosed without JSON strips
    everything from the tag onwards.
    """
    raw = re.sub(r'<think(?:ing)?>[\s\S]*?</think(?:ing)?>', '', raw)
    if '<think' in raw and '{' in raw:
        think_end = raw.rfind('</think')
        if think_end >= 0:
            close_bracket = raw.find('>', think_end)
            raw = raw[close_bracket + 1:] if close_bracket >= 0 else raw
        else:
            json_start = raw.find('{')
            if json_start >= 0:
                raw = raw[json_start:]
    elif '<think' in raw:
        # Unclosed think with no JSON to recover — strip from the tag onwards.
        raw = re.sub(r'<think(?:ing)?>[\s\S]*', '', raw)
    return raw.strip()


def parse_sarvam_response(raw: str) -> dict[str, Any] | None:
    """Parse a Sarvam research-story response into a dict.

    Tries three strategies in order, returning the first that yields a dict:

    1. Direct ``json.loads`` after stripping markdown fences and slicing to
       the outermost ``{...}``.
    2. Fix unescaped newlines inside JSON string values, then ``json.loads``.
    3. Regex-extract ``headline``/``body``/``category``/``location`` fields
       individually — last-ditch fallback for malformed LLM output.

    Returns ``None`` if all three strategies fail (caller should fall back
    to the source article's own title/description).
    """
    cleaned = raw
    if "```" in cleaned:
        cleaned = re.sub(r'```(?:json)?\s*', '', cleaned).strip()

    json_match = re.search(r'\{[\s\S]*\}', cleaned)
    if json_match:
        cleaned = json_match.group(0)

    # Strategy 1: direct parse
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Strategy 2: fix unescaped newlines inside JSON string values
    try:
        fixed = re.sub(
            r'(?<=: ")([\s\S]*?)(?="(?:,|\s*\}))',
            lambda m: m.group(1).replace('\n', '\\n').replace('\r', ''),
            cleaned,
        )
        parsed = json.loads(fixed)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, Exception):
        pass

    # Strategy 3: regex-extract individual fields
    try:
        h_match = re.search(r'"headline"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
        b_match = re.search(r'"body"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
        c_match = re.search(r'"category"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
        l_match = re.search(r'"location"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
        if h_match or b_match:
            return {
                "headline": h_match.group(1) if h_match else "",
                "body": b_match.group(1) if b_match else "",
                "category": c_match.group(1) if c_match else "general",
                "location": l_match.group(1) if l_match else "",
            }
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Union-find clustering core (pure)
# ---------------------------------------------------------------------------


def cluster_by_pairs(
    article_ids: list[str],
    pairs: Iterable[tuple[str, str]],
) -> list[list[str]]:
    """Group ids into clusters given a set of similarity pairs.

    Uses union-find (path compression). Returned clusters preserve the
    order of ``article_ids`` — each cluster appears in the position of its
    earliest-listed member. Members within a cluster are kept in their
    original input order; the caller re-sorts by published_at to pick a
    lead article.
    """
    parent = {aid: aid for aid in article_ids}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: str, y: str) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for a, b in pairs:
        if a in parent and b in parent:
            union(a, b)

    grouped: dict[str, list[str]] = {}
    for aid in article_ids:
        grouped.setdefault(find(aid), []).append(aid)

    seen: set[str] = set()
    result: list[list[str]] = []
    for aid in article_ids:
        root = find(aid)
        if root in seen:
            continue
        seen.add(root)
        result.append(grouped[root])
    return result


# ---------------------------------------------------------------------------
# Title-similarity clustering (DB-backed, normalization)
# ---------------------------------------------------------------------------


def fetch_similarity_pairs(
    db: Session,
    article_ids: list[str],
    *,
    threshold: float = 0.4,
) -> list[tuple[str, str]]:
    """Find cross-source title-similarity pairs among ``article_ids``.

    Uses pg_trgm ``similarity()``. Same-source duplicates are excluded (rare
    and usually genuine). Returns an empty list (with a warning) if pg_trgm
    isn't enabled on the news_articles table — clustering then degrades
    gracefully to singletons.
    """
    if not article_ids:
        return []
    try:
        rows = db.execute(
            text("""
                SELECT a.id AS id_a, b.id AS id_b, similarity(a.title, b.title) AS sim
                FROM news_articles a
                JOIN news_articles b ON a.id < b.id
                    AND a.source IS DISTINCT FROM b.source
                WHERE a.id = ANY(:ids) AND b.id = ANY(:ids)
                    AND similarity(a.title, b.title) > :threshold
                ORDER BY sim DESC
            """),
            {"ids": article_ids, "threshold": threshold},
        ).fetchall()
    except Exception as exc:
        logger.warning("Clustering failed (pg_trgm may not be on news_articles): %s", exc)
        return []
    return [(r[0], r[1]) for r in rows]


# ---------------------------------------------------------------------------
# Article scraping (I/O)
# ---------------------------------------------------------------------------


def _scrape_sync(url: str) -> str | None:
    """Scrape an article using scrapling (anti-bot bypass) + trafilatura."""
    try:
        from scrapling import Fetcher
        fetcher = Fetcher()
        resp = fetcher.get(url, timeout=15)
        if resp.status != 200:
            logger.warning("Scrapling %s returned status %d", url, resp.status)
            return None
        html = resp.response.text if hasattr(resp, 'response') else str(resp)
        extracted = trafilatura.extract(html, include_comments=False, include_tables=False)
        if extracted and len(extracted.strip()) > 150:
            return extracted.strip()
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


async def fetch_article_content(url: str) -> str | None:
    """Scrape article content — tries scrapling first, then plain httpx+trafilatura."""
    loop = asyncio.get_event_loop()

    # Try scrapling (handles anti-bot)
    content = await loop.run_in_executor(None, _scrape_sync, url)
    if content:
        return content

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


# ---------------------------------------------------------------------------
# High-level clustering helper (composes pure + DB layers)
# ---------------------------------------------------------------------------


def cluster_articles_by_title(
    articles: list[NewsArticle],
    db: Session,
) -> list[tuple[NewsArticle, list[NewsArticle]]]:
    """Cluster ``articles`` by title similarity.

    Returns a list of ``(lead_article, related_articles)`` tuples, one per
    cluster, in the order of ``articles``. The lead is the most recently
    published member of its cluster; ``related`` is the rest, also sorted
    by ``published_at`` desc.

    The router converts this to ``ClusteredArticleResponse`` — keeping the
    NewsArticle types here means the response-shape concern stays in the
    router and this helper remains testable without the response model.
    """
    if not articles:
        return []

    article_ids = [a.id for a in articles]
    article_map = {a.id: a for a in articles}

    pairs = fetch_similarity_pairs(db, article_ids)
    clusters = cluster_by_pairs(article_ids, pairs)

    result: list[tuple[NewsArticle, list[NewsArticle]]] = []
    for cluster_ids in clusters:
        cluster_articles = sorted(
            [article_map[cid] for cid in cluster_ids],
            key=lambda a: a.published_at or datetime.min,
            reverse=True,
        )
        lead = cluster_articles[0]
        related = cluster_articles[1:]
        result.append((lead, related))
    return result
