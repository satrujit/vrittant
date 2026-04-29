"""Admin story search endpoints: cross-language semantic search and related-stories."""
from datetime import datetime

from fastapi import Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from ...database import get_db
from ...deps import get_current_org_id, require_reviewer
from ...models.story import Story
from ...models.user import User
from . import router
from ._shared import AdminStoryListItem, AdminStoryListResponse


# ---------------------------------------------------------------------------
# GET /admin/stories/semantic-search  (cross-language semantic search)
# ---------------------------------------------------------------------------

@router.get("/stories/semantic-search", response_model=AdminStoryListResponse)
async def semantic_search_stories(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Cross-language fuzzy search using pg_trgm trigram similarity.
    Translates query via Sarvam AI so English queries find Odia stories and vice versa.
    Typo-tolerant: "Yojaya" still matches "Yojana".
    """
    import re
    import httpx
    from sqlalchemy import func, desc
    from ...config import settings
    from ...services import sarvam_client

    import logging as _logging
    _log = _logging.getLogger(__name__)

    # --- Step 0: Display-id short-circuit -----------------------------------
    # When the user types a number ("433") or a full display id
    # ("PNS-26-433") we want the *exact* story, not a trigram-similar
    # neighbour. The natural-language path used to score "PNS-26-429"
    # high for the query "433" because both share the digit, which is
    # confusing. Try the direct lookup first; on hit, return just that
    # row and skip the semantic step entirely.
    q_stripped = q.strip()
    seq_no_match: int | None = None
    if re.fullmatch(r"\d+", q_stripped):
        seq_no_match = int(q_stripped)
    else:
        # Accept "PNS-26-433", "pns-26-433", "PNS 26 433"
        m = re.fullmatch(r"\s*[A-Za-z]+[-\s]\d{2}[-\s](\d+)\s*", q_stripped)
        if m:
            seq_no_match = int(m.group(1))
    if seq_no_match is not None:
        direct = (
            db.query(Story)
            .options(joinedload(Story.reporter), joinedload(Story.revision), joinedload(Story.reviewer))
            .filter(
                Story.organization_id == org_id,
                Story.seq_no == seq_no_match,
                Story.deleted_at.is_(None),
            )
            .first()
        )
        if direct is not None:
            return AdminStoryListResponse(stories=[_to_list_item(direct)], total=1)
        # No exact match → fall through to semantic search. The user
        # might have typed a digit that legitimately appears in a
        # headline ("ELNG ଅଗ୍ରିମ ଟଙ୍କା ବଣ୍ଟନରେ ୧୨.୫ ପ୍ରତିଶତ").

    # --- Step 1: Translate query for cross-language support ---
    has_odia = bool(re.search(r'[\u0B00-\u0B7F]', q))
    source_lang = "od-IN" if has_odia else "en-IN"
    target_lang = "en-IN" if has_odia else "od-IN"

    translated_text = ""
    try:
        payload = {
            "input": q,
            "source_language_code": source_lang,
            "target_language_code": target_lang,
            "model": "mayura:v1",
        }
        _log.info("Search: translating query=%r (%s -> %s)", q, source_lang, target_lang)
        with sarvam_client.cost_context(bucket="search"):
            data = await sarvam_client.translate(payload=payload, timeout=15.0)
        translated_text = data.get("translated_text", "")
        _log.info("Search: translated %r -> %r", q, translated_text)
    except Exception as exc:
        _log.warning("Sarvam translate failed (continuing with original query): %s", exc)

    # --- Step 2: Build search terms (original + translated + individual words) ---
    all_terms = [q]
    if translated_text and translated_text.strip() and translated_text != q:
        all_terms.append(translated_text.strip())

    # Also add individual words (>=3 chars) for partial matching
    for term in list(all_terms):
        words = term.split()
        for w in words:
            if len(w) >= 3 and w not in all_terms:
                all_terms.append(w)

    _log.info("Search: terms=%s", all_terms)

    # --- Step 3: Trigram similarity search on search_text column ---
    # Use word_similarity for better substring matching within long text
    # Also fall back to ILIKE for exact substring matches (trigrams can miss short words)
    conditions = []
    similarity_exprs = []

    for term in all_terms:
        # Trigram word similarity (finds best matching substring)
        sim_expr = func.word_similarity(term, Story.search_text)
        similarity_exprs.append(sim_expr)
        conditions.append(sim_expr > 0.25)
        # Also plain ILIKE as fallback for exact substring matches
        conditions.append(Story.search_text.ilike(f"%{term}%"))

    # Best similarity score across all terms for ranking
    best_similarity = func.greatest(*similarity_exprs) if len(similarity_exprs) > 1 else similarity_exprs[0]

    base_query = (
        db.query(Story, best_similarity.label("score"))
        .options(joinedload(Story.reporter), joinedload(Story.revision), joinedload(Story.reviewer))
        .filter(
            Story.organization_id == org_id,
            Story.status != "draft",
            Story.deleted_at.is_(None),
            or_(*conditions),
        )
    )

    total = base_query.count()
    results = (
        base_query
        .order_by(desc("score"), Story.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    _log.info("Search: found %d results for query=%r", total, q)

    items = [_to_list_item(s) for s, _score in results]
    return AdminStoryListResponse(stories=items, total=total)


def _to_list_item(s: Story) -> AdminStoryListItem:
    """Shared adapter so the display-id short-circuit and semantic path
    return identical row shapes (display_id, seq_no, wp_*, etc)."""
    return AdminStoryListItem(
        id=s.id,
        seq_no=s.seq_no,
        display_id=s.display_id,
        wp_post_id=s.wp_post_id,
        wp_url=s.wp_url,
        wp_pushed_at=s.wp_pushed_at,
        wp_push_status=s.wp_push_status,
        wp_push_error=s.wp_push_error,
        reporter_id=s.reporter_id,
        headline=s.headline,
        category=s.category,
        location=s.location,
        source=s.source,
        paragraphs=s.paragraphs,
        status=s.status,
        submitted_at=s.submitted_at,
        created_at=s.created_at,
        updated_at=s.updated_at,
        reporter=s.reporter,
        has_revision=s.revision is not None,
        reviewed_by=s.reviewed_by,
        reviewer_name=s.reviewer.name if s.reviewer else None,
        reviewed_at=s.reviewed_at,
        assigned_to=s.assigned_to,
        assignee_name=s.assignee.name if s.assignee else None,
        assigned_match_reason=s.assigned_match_reason,
    )


# ---------------------------------------------------------------------------
# GET /admin/stories/{story_id}/related  (trigram similarity on headline)
# ---------------------------------------------------------------------------

class RelatedStoryItem(BaseModel):
    id: str
    headline: str
    status: str | None = None
    location: str | None = None
    created_at: datetime | None = None
    image_url: str | None = None
    reporter_name: str | None = None

    model_config = {"from_attributes": True}


@router.get("/stories/{story_id}/related", response_model=list[RelatedStoryItem])
def get_related_stories(
    story_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    """Find stories related to a given story using pg_trgm trigram similarity on headline."""
    from sqlalchemy import text

    story = db.query(Story).filter(Story.id == story_id, Story.organization_id == org_id, Story.deleted_at.is_(None)).first()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

    if not story.headline:
        return []

    rows = db.execute(
        text("""
            SELECT s.id, s.headline, s.status, s.location, s.created_at,
                   s.paragraphs, u.name AS reporter_name,
                   similarity(s.search_text, :headline) AS sim
            FROM stories s
            LEFT JOIN users u ON s.reporter_id = u.id
            WHERE s.id != :story_id
              AND s.organization_id = :org_id
              AND s.deleted_at IS NULL
              AND similarity(s.search_text, :headline) > 0.15
            ORDER BY sim DESC
            LIMIT 10
        """),
        {"headline": story.headline, "story_id": story_id, "org_id": org_id},
    ).fetchall()

    results = []
    for r in rows:
        # Extract first image URL from paragraphs (media paragraphs have type="media")
        image_url = None
        paragraphs = r.paragraphs
        if paragraphs and isinstance(paragraphs, list):
            for p in paragraphs:
                if isinstance(p, dict) and p.get("type") == "media" and p.get("media_path"):
                    image_url = p["media_path"]
                    break

        results.append(RelatedStoryItem(
            id=r.id,
            headline=r.headline,
            status=r.status,
            location=r.location,
            created_at=r.created_at,
            image_url=image_url,
            reporter_name=r.reporter_name,
        ))

    return results
