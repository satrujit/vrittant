"""Admin story endpoints: list, get, update, status, delete, image upload."""
import os
import uuid as uuid_mod
from datetime import datetime
from typing import Optional

from fastapi import BackgroundTasks, Depends, File as FastAPIFile, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from ...database import get_db
from ...deps import get_current_org_id, require_org_admin, require_reviewer
from ...models.edition import Edition, EditionPage, EditionPageStory
from ...models.story import Story
from ...models.story_revision import StoryRevision
from ...models.user import User
from ...services.categorizer import categorize_story_in_background
from ...utils.tz import now_ist
from . import router
from ._shared import (
    AdminStoryListItem,
    AdminStoryListResponse,
    AdminStoryResponse,
    AdminStoryUpdate,
    AdminStoryWithRevisionResponse,
    AssignmentLogEntry,
    StatusUpdate,
    _build_story_query,
    _get_edition_info,
)


# Maximum length when we synthesise a headline from body text.
# Sized so it fits a single line in the list view without truncation.
_DERIVED_HEADLINE_MAX_LEN = 120


def _derive_headline_from_paragraphs(paragraphs) -> str:
    """Return a non-empty headline derived from the first body paragraph.

    Strategy: take the first non-empty paragraph's text, take its first
    line (split on newline), strip, truncate to _DERIVED_HEADLINE_MAX_LEN
    with an ellipsis if it overflows. Returns "" if no usable text exists.

    Stories saved without a headline used to surface as blank rows in the
    list view; this guarantees something readable is always present.
    """
    if not paragraphs:
        return ""
    for para in paragraphs:
        text = (para or {}).get("text") or ""
        # Strip HTML-ish tags conservatively — paragraph text is plain in
        # our schema, but defensive split on '<' avoids leaking markup if
        # any sneaks in from a paste.
        first_line = text.split("\n", 1)[0].strip()
        if not first_line:
            continue
        if len(first_line) > _DERIVED_HEADLINE_MAX_LEN:
            return first_line[: _DERIVED_HEADLINE_MAX_LEN - 1].rstrip() + "…"
        return first_line
    return ""


def _check_headline_duplicate_today(
    db: Session,
    *,
    org_id: str,
    headline: Optional[str],
    submitted_at: Optional[datetime],
    exclude_story_id: Optional[str] = None,
) -> None:
    """Raise HTTP 409 if another story in the same org has the same headline
    submitted on the same calendar day.

    Editorial rule: a single org should never publish two stories with
    identical headlines on the same day — it's almost always either an
    accidental double-save or two reporters racing on the same press
    release. The check is wired into editor-create / editor-update only;
    WhatsApp-forwarded items skip this entirely (they often share the
    same first line because reporters forward the same press release,
    and the per-org display_id distinguishes them in the queue).

    `exclude_story_id` is required during PUT updates so the story being
    re-saved doesn't false-positive against itself.
    """
    cleaned = (headline or "").strip()
    if not cleaned or submitted_at is None:
        return
    target_date = submitted_at.date()
    q = db.query(Story.id).filter(
        Story.organization_id == org_id,
        Story.deleted_at.is_(None),
        Story.headline == cleaned,
        func.date(Story.submitted_at) == target_date,
    )
    if exclude_story_id:
        q = q.filter(Story.id != exclude_story_id)
    if q.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Another story with the headline “{cleaned}” was already "
                f"saved today. Please use a different headline."
            ),
        )


def _resolve_headline(submitted: Optional[str], paragraphs, fallback: Optional[str]) -> Optional[str]:
    """Pick the headline to persist, given user input + body + existing value.

    - If `submitted` has non-whitespace content, use it (trimmed).
    - Else derive from `paragraphs`.
    - Else keep `fallback` (existing headline).
    - Returns None only if everything is empty (caller decides what to do).
    """
    if submitted is not None and submitted.strip():
        return submitted.strip()
    derived = _derive_headline_from_paragraphs(paragraphs)
    if derived:
        return derived
    return fallback


# ---------------------------------------------------------------------------
# GET /admin/stories
# ---------------------------------------------------------------------------

@router.get("/stories", response_model=AdminStoryListResponse)
def admin_list_stories(
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
    status_filter: Optional[str] = Query(None, alias="status"),
    exclude_status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    reporter_id: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    recent: bool = Query(False),
    available_for_edition: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None, description="Filter by assignee user_id, or 'me'"),
    updated_since: Optional[str] = Query(None, description="ISO timestamp — return only stories updated after this time"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
):
    resolved_assigned = user.id if assigned_to == "me" else assigned_to
    # --- Delta mode: return stories changed or soft-deleted since timestamp ---
    if updated_since:
        try:
            dt = datetime.fromisoformat(updated_since)
        except (ValueError, TypeError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid updated_since timestamp")

        delta_query = (
            db.query(Story)
            .options(joinedload(Story.reporter), joinedload(Story.revision), joinedload(Story.reviewer), joinedload(Story.assignee))
            .filter(
                Story.organization_id == org_id,
                Story.status != "draft",
                or_(Story.updated_at >= dt, Story.deleted_at >= dt),
            )
        )
        if reporter_id:
            delta_query = delta_query.filter(Story.reporter_id == reporter_id)
        if resolved_assigned:
            delta_query = delta_query.filter(Story.assigned_to == resolved_assigned)

        # total = count of ALL non-deleted stories (so frontend can detect deletions)
        total = (
            db.query(Story)
            .filter(Story.organization_id == org_id, Story.deleted_at.is_(None), Story.status != "draft")
            .count()
        )

        stories = (
            delta_query.order_by(Story.updated_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        items = [
            AdminStoryListItem(
                id=s.id,
                seq_no=s.seq_no,
                display_id=s.display_id,
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
                is_deleted=s.deleted_at is not None,
                reviewed_by=s.reviewed_by,
                reviewer_name=s.reviewer.name if s.reviewer else None,
                reviewed_at=s.reviewed_at,
                assigned_to=s.assigned_to,
                assignee_name=s.assignee.name if s.assignee else None,
                assigned_match_reason=s.assigned_match_reason,
            )
            for s in stories
        ]

        return AdminStoryListResponse(stories=items, total=total)

    # --- Normal mode (no updated_since) ---
    query = _build_story_query(
        db,
        org_id=org_id,
        reporter_id=reporter_id,
        status_filter=status_filter,
        exclude_status=exclude_status,
        category=category,
        search=search,
        location=location,
        date_from=date_from,
        date_to=date_to,
        recent=recent,
        available_for_edition=available_for_edition,
        assigned_to=resolved_assigned,
    )

    total = query.count()
    stories = (
        query.options(joinedload(Story.revision), joinedload(Story.reviewer), joinedload(Story.assignee))
        # #50 — Order by reporter-supplied submission time, not created_at.
        # `submitted_at` is when the reporter actually filed the story (it
        # may differ from created_at for offline-collected drafts that get
        # uploaded later). Coalesce to created_at so legacy rows that
        # never set submitted_at still sort correctly. Sorting by
        # updated_at would re-shuffle every time someone re-saved.
        .order_by(func.coalesce(Story.submitted_at, Story.created_at).desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = [
        AdminStoryListItem(
            id=s.id,
            seq_no=s.seq_no,
            display_id=s.display_id,
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
        for s in stories
    ]

    return AdminStoryListResponse(stories=items, total=total)


# ---------------------------------------------------------------------------
# POST /admin/stories  (editor saves a brand-new story for the first time)
# ---------------------------------------------------------------------------
#
# Deliberately *no* "create blank" endpoint. The "+" button in the panel
# opens an in-memory editor at /review/new. A row is only inserted once
# the user actually saves real content. This keeps the stories table from
# accumulating empty editor-clicked-then-abandoned drafts.

def _has_real_content(headline: Optional[str], paragraphs: Optional[list]) -> bool:
    if (headline or "").strip():
        return True
    for p in paragraphs or []:
        item = p if isinstance(p, dict) else (p.model_dump() if hasattr(p, "model_dump") else {})
        if (item.get("text") or "").strip():
            return True
        if item.get("media_path") or item.get("photo_path"):
            return True
    return False


@router.post("/stories", response_model=AdminStoryWithRevisionResponse)
def create_editor_story(
    body: AdminStoryUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    """Create a story authored from the editor.

    Refuses empty payloads (HTTP 400). The frontend disables the Save
    button until there's a headline or body, so this is mostly a
    backstop — a clean error beats inserting another phantom row.
    """
    paragraphs = (
        [p.model_dump() for p in body.paragraphs] if body.paragraphs is not None else []
    )
    if not _has_real_content(body.headline, paragraphs):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Story must have a headline or body content before saving.",
        )

    headline = _resolve_headline(body.headline, paragraphs, "") or ""

    now = now_ist()
    # Reject same-org/same-day headline collisions before we hit the DB.
    # See _check_headline_duplicate_today for the editorial rationale.
    _check_headline_duplicate_today(
        db, org_id=org_id, headline=headline, submitted_at=now,
    )

    from ...services.story_seq import assign_next_seq
    story = Story(
        id=str(uuid_mod.uuid4()),
        reporter_id=current_user.id,
        organization_id=org_id,
        seq_no=assign_next_seq(db, org_id),
        headline=headline,
        paragraphs=paragraphs,
        category=body.category,
        priority=body.priority or "normal",
        status="submitted",
        submitted_at=now,
        source="Editor Created",
        assigned_to=current_user.id,
        assigned_match_reason="manual",
        created_at=now,
        updated_at=now,
    )
    story.refresh_search_text()
    db.add(story)

    # Mirror translation/social_posts onto a revision row if provided. The
    # Story row itself carries headline/paragraphs for editor-created
    # stories (matches the convention used in admin_update_story).
    if body.english_translation is not None or body.social_posts is not None:
        rev = StoryRevision(
            story_id=story.id,
            editor_id=current_user.id,
            headline=headline,
            paragraphs=paragraphs,
            english_translation=body.english_translation,
            social_posts=body.social_posts,
        )
        db.add(rev)

    db.commit()
    db.refresh(story)

    # Best-effort auto-categorisation: fire after the response is sent so
    # the editor doesn't wait on Sarvam. Skips itself if the editor already
    # picked a category. The cron sweep mops up any failures.
    if not (story.category or "").strip():
        background_tasks.add_task(categorize_story_in_background, story.id)

    resp = AdminStoryWithRevisionResponse.model_validate(story)
    resp.edition_info = _get_edition_info(db, story.id)
    resp.reviewer_name = story.reviewer.name if story.reviewer else None
    resp.assignee_name = story.assignee.name if story.assignee else None
    return resp


# ---------------------------------------------------------------------------
# GET /admin/stories/{story_id}
# ---------------------------------------------------------------------------

@router.get("/stories/{story_id}", response_model=AdminStoryWithRevisionResponse)
def admin_get_story(story_id: str, db: Session = Depends(get_db), user: User = Depends(require_reviewer), org_id: str = Depends(get_current_org_id)):
    story = (
        db.query(Story)
        .options(joinedload(Story.reporter), joinedload(Story.revision), joinedload(Story.reviewer), joinedload(Story.assignee))
        .filter(Story.id == story_id, Story.organization_id == org_id, Story.deleted_at.is_(None))
        .first()
    )
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Story not found"
        )
    # Build response with edition info
    resp = AdminStoryWithRevisionResponse.model_validate(story)
    resp.edition_info = _get_edition_info(db, story_id)
    resp.reviewer_name = story.reviewer.name if story.reviewer else None
    resp.assignee_name = story.assignee.name if story.assignee else None
    return resp


# ---------------------------------------------------------------------------
# PUT /admin/stories/{story_id}/status
# ---------------------------------------------------------------------------

TERMINAL_STATUSES = {"approved", "rejected", "published", "layout_completed", "flagged"}

# Transitions that require a specific source state. All other moves between
# allowed statuses are unrestricted. Keep this map small and obvious — the
# moment it gets clever it stops being readable.
STATUS_PREDECESSORS = {
    "layout_completed": {"approved"},
}


def _cleanup_transcription_audio(story: Story) -> None:
    """Delete non-attachment audio files referenced by ``transcription_audio_path``.

    Called when a story transitions to ``published``. The "silent backup"
    audio (uploaded by the always-upload pipeline so we can re-transcribe
    if the live WS produced nothing) has done its job once a published
    transcript exists. Audio that the reporter explicitly attached
    (long-press, where ``media_path == transcription_audio_path``) is
    preserved — it's part of the published story.

    Mutates ``story.paragraphs`` in place; caller is responsible for
    committing. Best-effort: a failed delete is logged but doesn't block
    publish.
    """
    import logging
    from sqlalchemy.orm.attributes import flag_modified
    from ...services.storage import delete_file

    log = logging.getLogger(__name__)
    paragraphs = list(story.paragraphs or [])
    changed = False
    for i, p in enumerate(paragraphs):
        if not isinstance(p, dict):
            continue
        audio_path = p.get("transcription_audio_path")
        if not audio_path:
            continue
        # Keep when the audio is also the visible attachment.
        if audio_path == p.get("media_path"):
            continue
        delete_file(audio_path)
        new_p = dict(p)
        new_p.pop("transcription_audio_path", None)
        # Keep status/attempts as historical record — only the file is gone.
        paragraphs[i] = new_p
        changed = True
        log.info("publish-cleanup: dropped backup audio for story=%s para=%s", story.id, p.get("id"))
    if changed:
        story.paragraphs = paragraphs
        flag_modified(story, "paragraphs")


@router.put("/stories/{story_id}/status", response_model=AdminStoryResponse)
def admin_update_story_status(
    story_id: str,
    body: StatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    # `submitted` is in here so reviewers can "send back" a story they
    # approved by mistake — clears the attribution and puts the story
    # back on the Reported queue. It's the only non-terminal target.
    allowed = {"submitted", "approved", "rejected", "published", "flagged", "layout_completed"}
    if body.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {', '.join(sorted(allowed))}",
        )

    story = (
        db.query(Story)
        .options(joinedload(Story.reporter), joinedload(Story.reviewer), joinedload(Story.assignee))
        .filter(Story.id == story_id, Story.organization_id == org_id, Story.deleted_at.is_(None))
        .first()
    )
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Story not found"
        )

    # Enforce the few transitions that have a strict predecessor (e.g. only
    # an Approved story can move to Layout Completed — that's the whole
    # point of the layout step).
    required_from = STATUS_PREDECESSORS.get(body.status)
    if required_from is not None and story.status not in required_from:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot move to '{body.status}' from '{story.status}'. "
                f"Allowed source statuses: {', '.join(sorted(required_from))}."
            ),
        )

    # Edition assignment is optional — approval no longer requires it
    story.status = body.status
    if body.status in TERMINAL_STATUSES:
        story.reviewed_by = user.id
        story.reviewed_at = now_ist()
    else:
        story.reviewed_by = None
        story.reviewed_at = None
    story.updated_at = now_ist()

    # Publish-time cleanup: drop the silent backup audio (always-upload
    # pipeline) once the story is published. Audio explicitly attached by
    # the reporter (long-press → media_path == transcription_audio_path)
    # is left alone because it's part of the published story.
    if body.status == "published":
        _cleanup_transcription_audio(story)

    db.commit()
    db.refresh(story)
    resp = AdminStoryResponse.model_validate(story)
    resp.reviewer_name = story.reviewer.name if story.reviewer else None
    resp.assignee_name = story.assignee.name if story.assignee else None
    return resp


# ---------------------------------------------------------------------------
# PUT /admin/stories/{story_id}  (editor content update)
# ---------------------------------------------------------------------------

@router.put("/stories/{story_id}", response_model=AdminStoryWithRevisionResponse)
def admin_update_story(
    story_id: str,
    body: AdminStoryUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    story = (
        db.query(Story)
        .options(joinedload(Story.reporter), joinedload(Story.revision), joinedload(Story.reviewer), joinedload(Story.assignee))
        .filter(Story.id == story_id, Story.organization_id == org_id, Story.deleted_at.is_(None))
        .first()
    )
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Story not found"
        )

    # Build revision data from request body
    rev_paragraphs = (
        [p.model_dump() for p in body.paragraphs]
        if body.paragraphs is not None
        else None
    )

    # Editor-created stories have no upstream reporter original to preserve,
    # so the Story row itself is the canonical content. Mirror headline/
    # paragraphs onto the Story directly so the list view (which reads
    # Story.headline / Story.paragraphs) reflects saved edits. Ancillary
    # fields (english_translation, social_posts) still live on the revision.
    is_editor_created = (story.source == "Editor Created")

    # Resolve the effective headline once, against the paragraphs that
    # will actually be persisted. We never want to write back an empty
    # headline — fall back to the first body line, then to the existing
    # headline. See _resolve_headline.
    effective_paragraphs = rev_paragraphs if rev_paragraphs is not None else story.paragraphs
    if body.headline is not None:
        resolved_headline = _resolve_headline(body.headline, effective_paragraphs, story.headline)
    else:
        # Headline not in payload — keep what's there, but if it's empty
        # take the chance to backfill from current paragraphs.
        existing_clean = (story.headline or "").strip()
        if existing_clean:
            resolved_headline = existing_clean
        else:
            resolved_headline = _resolve_headline(None, effective_paragraphs, story.headline)

    # Block same-org/same-day headline collisions on update too. We compare
    # against the *resolved* headline (the value that's about to land on
    # either Story or its revision) and exclude this story from the search
    # so re-saves of an unchanged headline don't false-positive. The check
    # is keyed on the original Story.submitted_at — that's the day this
    # story belongs to editorially, regardless of when the edit happens.
    if resolved_headline:
        _check_headline_duplicate_today(
            db,
            org_id=org_id,
            headline=resolved_headline,
            submitted_at=story.submitted_at or story.created_at,
            exclude_story_id=story.id,
        )

    if is_editor_created:
        if resolved_headline is not None:
            story.headline = resolved_headline
        if rev_paragraphs is not None:
            story.paragraphs = rev_paragraphs

    # Upsert: update existing revision or create new one.
    # For editor-created stories, only touch the revision for fields that
    # don't have a corresponding Story column (translation, social_posts);
    # headline/paragraphs are already on Story above.
    existing_rev = story.revision
    if existing_rev:
        if not is_editor_created:
            if resolved_headline is not None:
                existing_rev.headline = resolved_headline
            if rev_paragraphs is not None:
                existing_rev.paragraphs = rev_paragraphs
        if body.english_translation is not None:
            existing_rev.english_translation = body.english_translation
        if body.social_posts is not None:
            existing_rev.social_posts = body.social_posts
        existing_rev.updated_at = now_ist()
    else:
        needs_revision_row = (
            (not is_editor_created)
            or body.english_translation is not None
            or body.social_posts is not None
        )
        if needs_revision_row:
            new_rev = StoryRevision(
                story_id=story.id,
                editor_id=current_user.id,
                headline=resolved_headline or story.headline,
                paragraphs=rev_paragraphs or story.paragraphs,
                english_translation=body.english_translation,
                social_posts=body.social_posts,
            )
            db.add(new_rev)

    # Update category on the story if provided (category is story-level, not content)
    if body.category is not None:
        story.category = body.category
    if body.priority is not None:
        story.priority = body.priority

    story.updated_at = now_ist()
    story.refresh_search_text()
    db.commit()
    db.refresh(story)

    # Best-effort auto-categorisation: only fire if the story still has no
    # category after this save. Same fire-and-forget pattern as the create
    # path; the cron sweep retries on failure.
    if not (story.category or "").strip():
        background_tasks.add_task(categorize_story_in_background, story.id)

    resp = AdminStoryWithRevisionResponse.model_validate(story)
    resp.edition_info = _get_edition_info(db, story.id)
    resp.reviewer_name = story.reviewer.name if story.reviewer else None
    resp.assignee_name = story.assignee.name if story.assignee else None
    return resp


# ---------------------------------------------------------------------------
# DELETE /admin/stories/{story_id}  (org_admin only)
# ---------------------------------------------------------------------------

@router.delete("/stories/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_story(
    story_id: str,
    db: Session = Depends(get_db), admin: User = Depends(require_org_admin),
    org_id: str = Depends(get_current_org_id),
):
    story = db.query(Story).filter(Story.id == story_id, Story.organization_id == org_id, Story.deleted_at.is_(None)).first()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")
    story.deleted_at = now_ist()
    db.commit()


# ---------------------------------------------------------------------------
# POST /admin/stories/{story_id}/upload-image
# ---------------------------------------------------------------------------

# Allowed extensions per attachment kind. Driven off file extension because
# UploadFile.content_type is set by the client and unreliable (browsers send
# application/octet-stream for unknown types, mobile uploaders sometimes
# omit the field entirely).
#
# Issue #44 — was image-only; we now accept the document formats that
# reporters routinely forward over WhatsApp (PDF / Word / spreadsheets /
# plain text). Audio + video stay rejected here because they have separate
# upload paths and different storage/quota tradeoffs.
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_DOC_EXTS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv", ".rtf"}
_ALLOWED_EXTS = _IMAGE_EXTS | _DOC_EXTS

# 10 MB worked fine when this only handled phone photos, but PDFs from a
# reporter's scan/print workflow routinely run larger. Bump to 25 MB which
# still fits comfortably in a single Cloud Run request and one GCS PUT.
_MAX_UPLOAD_BYTES = 25 * 1024 * 1024


@router.post("/stories/{story_id}/upload-image")
async def upload_story_image(
    story_id: str,
    file: UploadFile = FastAPIFile(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    """Attach a file to a story.

    Route name is ``upload-image`` for backwards compatibility with older
    panel/mobile builds, but the endpoint accepts both images *and*
    documents — see _ALLOWED_EXTS above. The stored ``media_type``
    discriminates ("photo" vs "document") so the rendering UI can pick
    the right thumbnail/icon.
    """
    from ...services.storage import save_file

    story = db.query(Story).filter(Story.id == story_id, Story.organization_id == org_id, Story.deleted_at.is_(None)).first()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail=f"File type {ext or '(none)'} not allowed")

    contents = await file.read()
    if len(contents) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large (max {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB)",
        )

    is_image = ext in _IMAGE_EXTS
    media_type = "photo" if is_image else "document"
    subfolder = "story-images" if is_image else "story-documents"
    fallback_name = "image.jpg" if is_image else f"document{ext or '.bin'}"

    media_url = save_file(contents, file.filename or fallback_name, subfolder=subfolder)

    # Append as a new paragraph with media_path. Generate an `id` so the
    # reviewer-panel attachment-delete UI can target this paragraph
    # (otherwise the X button is suppressed for lack of an identifier).
    paragraphs = list(story.paragraphs or [])
    paragraphs.append({
        "id": str(uuid_mod.uuid4()),
        "text": "",
        "type": "media",
        "media_path": media_url,
        "media_type": media_type,
        "media_name": file.filename or fallback_name,
    })
    story.paragraphs = paragraphs
    story.updated_at = now_ist()
    story.refresh_search_text()
    db.commit()
    db.refresh(story)

    return {"media_url": media_url, "message": "Attachment uploaded", "media_type": media_type}


# ---------------------------------------------------------------------------
# GET /admin/stories/{story_id}/assignment-log
# ---------------------------------------------------------------------------

@router.get("/stories/{story_id}/assignment-log", response_model=list[AssignmentLogEntry])
def admin_get_assignment_log(
    story_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    from ...models.story_assignment_log import StoryAssignmentLog

    story = (
        db.query(Story)
        .filter(Story.id == story_id, Story.organization_id == org_id, Story.deleted_at.is_(None))
        .first()
    )
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

    rows = (
        db.query(StoryAssignmentLog)
        .filter(StoryAssignmentLog.story_id == story_id)
        .order_by(StoryAssignmentLog.created_at.desc())
        .all()
    )

    # Bulk-hydrate user names with a single query
    user_ids: set[str] = set()
    for r in rows:
        if r.from_user_id:
            user_ids.add(r.from_user_id)
        if r.to_user_id:
            user_ids.add(r.to_user_id)
        if r.assigned_by:
            user_ids.add(r.assigned_by)

    name_by_id: dict[str, str] = {}
    if user_ids:
        for u in db.query(User.id, User.name).filter(User.id.in_(user_ids)).all():
            name_by_id[u.id] = u.name

    return [
        AssignmentLogEntry(
            id=r.id,
            from_user_id=r.from_user_id,
            from_user_name=name_by_id.get(r.from_user_id) if r.from_user_id else None,
            to_user_id=r.to_user_id,
            to_user_name=name_by_id.get(r.to_user_id, ""),
            assigned_by=r.assigned_by,
            assigned_by_name=name_by_id.get(r.assigned_by) if r.assigned_by else None,
            reason=r.reason,
            created_at=r.created_at,
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# PATCH /admin/stories/{story_id}/assignee  (any reviewer or admin)
# ---------------------------------------------------------------------------

class ReassignRequest(BaseModel):
    assignee_id: str


@router.patch("/stories/{story_id}/assignee", response_model=AdminStoryResponse)
def admin_reassign_story(
    story_id: str,
    body: ReassignRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    from ...models.story_assignment_log import StoryAssignmentLog

    story = (
        db.query(Story).options(joinedload(Story.reporter), joinedload(Story.reviewer), joinedload(Story.assignee))
        .filter(Story.id == story_id, Story.organization_id == org_id, Story.deleted_at.is_(None))
        .first()
    )
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

    new_assignee = (
        db.query(User)
        .filter(User.id == body.assignee_id, User.organization_id == org_id,
                User.user_type == "reviewer", User.is_active.is_(True), User.deleted_at.is_(None))
        .first()
    )
    if not new_assignee:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Assignee must be an active reviewer in this organization")

    previous = story.assigned_to
    story.assigned_to = new_assignee.id
    story.assigned_match_reason = "manual"
    story.updated_at = now_ist()
    db.add(StoryAssignmentLog(
        story_id=story.id, from_user_id=previous, to_user_id=new_assignee.id,
        assigned_by=user.id, reason="manual",
    ))
    db.commit()
    db.refresh(story)
    resp = AdminStoryResponse.model_validate(story)
    resp.reviewer_name = story.reviewer.name if story.reviewer else None
    resp.assignee_name = new_assignee.name
    return resp


# ---------------------------------------------------------------------------
# Comments — GET / POST /admin/stories/{story_id}/comments
# Flat editorial thread visible to all reviewers/admins in the org.
# ---------------------------------------------------------------------------

class CommentResponse(BaseModel):
    id: str
    author_id: str
    author_name: str
    body: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CommentCreate(BaseModel):
    body: str


@router.get("/stories/{story_id}/comments", response_model=list[CommentResponse])
def admin_list_story_comments(
    story_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    from ...models.story_comment import StoryComment

    story = (
        db.query(Story)
        .filter(Story.id == story_id, Story.organization_id == org_id, Story.deleted_at.is_(None))
        .first()
    )
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

    rows = (
        db.query(StoryComment)
        .filter(StoryComment.story_id == story_id)
        .order_by(StoryComment.created_at.asc())
        .all()
    )

    author_ids = {r.author_id for r in rows}
    name_by_id: dict[str, str] = {}
    if author_ids:
        for u in db.query(User.id, User.name).filter(User.id.in_(author_ids)).all():
            name_by_id[u.id] = u.name

    return [
        CommentResponse(
            id=r.id,
            author_id=r.author_id,
            author_name=name_by_id.get(r.author_id, ""),
            body=r.body,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post("/stories/{story_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def admin_create_story_comment(
    story_id: str,
    body: CommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    from ...models.story_comment import StoryComment

    text = (body.body or "").strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comment body required")

    story = (
        db.query(Story)
        .filter(Story.id == story_id, Story.organization_id == org_id, Story.deleted_at.is_(None))
        .first()
    )
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

    comment = StoryComment(story_id=story_id, author_id=user.id, body=text)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return CommentResponse(
        id=comment.id,
        author_id=comment.author_id,
        author_name=user.name,
        body=comment.body,
        created_at=comment.created_at,
    )


# ---------------------------------------------------------------------------
# GET / PUT /admin/stories/{story_id}/placements
#
# Bulk read/replace edition-page placements for a single story. Used by the
# matrix UI on the review page to set "this story goes on these pages of
# these editions" in one call. Diff-based: server inserts missing rows,
# deletes ones not in the new set, all in one transaction.
#
# Note: a story can sit on multiple pages by design — the join table has
# no unique constraint on story_id.
# ---------------------------------------------------------------------------


class _Placement(BaseModel):
    edition_id: str
    page_id: str


class _BulkPlacementRequest(BaseModel):
    placements: list[_Placement]


def _serialize_placements(db: Session, story_id: str, org_id: str) -> list[dict]:
    rows = (
        db.query(EditionPageStory, EditionPage, Edition)
        .join(EditionPage, EditionPage.id == EditionPageStory.edition_page_id)
        .join(Edition, Edition.id == EditionPage.edition_id)
        .filter(
            EditionPageStory.story_id == story_id,
            Edition.organization_id == org_id,
        )
        .all()
    )
    return [
        {
            "edition_id": ed.id,
            "edition_title": ed.title,
            "page_id": ep.id,
            "page_name": ep.page_name,
        }
        for _row, ep, ed in rows
    ]


def _load_owned_story_or_404(db: Session, story_id: str, org_id: str) -> Story:
    story = (
        db.query(Story)
        .filter(Story.id == story_id, Story.deleted_at.is_(None))
        .first()
    )
    # Use 404 for both "missing" and "wrong org" so we don't leak existence
    # of stories from other orgs. Mirrors get_owned_or_404.
    if not story or story.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")
    return story


@router.get("/stories/{story_id}/placements")
def get_story_placements(
    story_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    _load_owned_story_or_404(db, story_id, org_id)
    return _serialize_placements(db, story_id, org_id)


@router.put("/stories/{story_id}/placements")
def bulk_set_story_placements(
    story_id: str,
    body: _BulkPlacementRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    _load_owned_story_or_404(db, story_id, org_id)

    # Validate every (edition_id, page_id) pair belongs to caller's org.
    # Reject the whole request on the first bad pair — partial application
    # would leave a confusing half-state on a UI that thinks it's atomic.
    desired: set[tuple[str, str]] = set()
    for p in body.placements:
        ep = (
            db.query(EditionPage)
            .join(Edition, Edition.id == EditionPage.edition_id)
            .filter(
                EditionPage.id == p.page_id,
                Edition.id == p.edition_id,
                Edition.organization_id == org_id,
            )
            .first()
        )
        if not ep:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid edition/page: {p.edition_id}/{p.page_id}",
            )
        desired.add((p.edition_id, p.page_id))

    current_rows = (
        db.query(EditionPageStory, EditionPage, Edition)
        .join(EditionPage, EditionPage.id == EditionPageStory.edition_page_id)
        .join(Edition, Edition.id == EditionPage.edition_id)
        .filter(
            EditionPageStory.story_id == story_id,
            Edition.organization_id == org_id,
        )
        .all()
    )
    current = {(ed.id, ep.id) for _row, ep, ed in current_rows}

    for row, ep, ed in current_rows:
        if (ed.id, ep.id) not in desired:
            db.delete(row)

    for ed_id, page_id in desired - current:
        db.add(EditionPageStory(
            edition_page_id=page_id,
            story_id=story_id,
            sort_order=0,
        ))

    db.commit()

    return _serialize_placements(db, story_id, org_id)
