"""Admin story endpoints: list, get, update, status, delete, image upload."""
import os
import uuid as uuid_mod
from datetime import datetime
from typing import Optional

from fastapi import Depends, File as FastAPIFile, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from ...database import get_db
from ...deps import get_current_org_id, require_org_admin, require_reviewer
from ...models.story import Story
from ...models.story_revision import StoryRevision
from ...models.user import User
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
        .order_by(Story.updated_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = [
        AdminStoryListItem(
            id=s.id,
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
# POST /admin/stories/create-blank  (editor creates new story from scratch)
# ---------------------------------------------------------------------------

class CreateBlankStoryResponse(BaseModel):
    story_id: str


@router.post("/stories/create-blank", response_model=CreateBlankStoryResponse)
def create_blank_story(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    now = now_ist()
    story = Story(
        id=str(uuid_mod.uuid4()),
        reporter_id=current_user.id,
        organization_id=org_id,
        headline="",
        paragraphs=[],
        # Editor-created stories start as "draft" — invisible to the rest
        # of the panel (the list endpoints filter `status != 'draft'`). The
        # row only graduates to "submitted" (rendered "Reported") on the
        # first save that contains real content; see admin_update_story.
        # This stops orphan rows from appearing on All Stories when an
        # editor clicks "+" but never types anything.
        status="draft",
        submitted_at=now,
        source="Editor Created",
        # Auto-assign to creator — they're the one writing it, so the story
        # shouldn't sit in an "Unassigned" state in the side panel.
        assigned_to=current_user.id,
        assigned_match_reason="manual",
        created_at=now,
        updated_at=now,
    )
    story.refresh_search_text()
    db.add(story)
    db.commit()
    return CreateBlankStoryResponse(story_id=story.id)


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

    # Promote a draft to "submitted" (rendered "Reported") the first time it
    # gains real content. Editor-created stories start as drafts so they
    # don't pollute All Stories with empty rows; once the editor types
    # anything we surface them in the normal pipeline.
    if story.status == "draft":
        has_headline = bool((story.headline or "").strip())
        has_body = any(
            (p or {}).get("text", "").strip()
            or (p or {}).get("media_path")
            or (p or {}).get("photo_path")
            for p in (story.paragraphs or [])
        )
        if has_headline or has_body:
            story.status = "submitted"
            if story.submitted_at is None:
                story.submitted_at = now_ist()

    story.updated_at = now_ist()
    story.refresh_search_text()
    db.commit()
    db.refresh(story)
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

@router.post("/stories/{story_id}/upload-image")
async def upload_story_image(
    story_id: str,
    file: UploadFile = FastAPIFile(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_reviewer),
    org_id: str = Depends(get_current_org_id),
):
    from ...services.storage import save_file

    story = db.query(Story).filter(Story.id == story_id, Story.organization_id == org_id, Story.deleted_at.is_(None)).first()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        raise HTTPException(status_code=400, detail=f"File type {ext} not allowed")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10 MB)")

    media_url = save_file(contents, file.filename or "image.jpg", subfolder="story-images")

    # Append as a new paragraph with media_path. Generate an `id` so the
    # reviewer-panel attachment-delete UI can target this paragraph
    # (otherwise the X button is suppressed for lack of an identifier).
    paragraphs = list(story.paragraphs or [])
    paragraphs.append({
        "id": str(uuid_mod.uuid4()),
        "text": "",
        "type": "media",
        "media_path": media_url,
        "media_type": "photo",
        "media_name": file.filename or "image",
    })
    story.paragraphs = paragraphs
    story.updated_at = now_ist()
    story.refresh_search_text()
    db.commit()
    db.refresh(story)

    return {"media_url": media_url, "message": "Image uploaded"}


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
