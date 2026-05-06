"""Story creation from a drained thread.

Called by handle_button when the user taps Submit. Owns:
- Drain pending_media (download Gupshup URLs, upload to GCS via the
  legacy _persist_media helper)
- Build paragraphs (text + media)
- Pick a category via the existing Sarvam classifier
- Assign next seq_no via story_seq.assign_next_seq
- Create Story row with status='submitted', source='whatsapp'
- Close the thread state

This deliberately mirrors a subset of the legacy
api/app/routers/webhooks_whatsapp.py story-creation logic. The legacy
path still exists; this module is used only when
WHATSAPP_SELF_SERVICE_ENABLED=true. After we cut over and the legacy
path is removed, future tickets can DRY-up by extracting a single
shared helper.
"""
from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.story import Story
from app.models.user import User
from app.models.whatsapp_buffer import WhatsAppThreadState
from app.routers.webhooks_whatsapp import (
    STITCH_MINUTES,
    _media_type_for,
    _persist_media,
)
from app.services.categorizer import classify_category, org_category_keys
from app.services.story_seq import assign_next_seq
from app.services.whatsapp import buffer, thread_state
from app.utils.tz import now_ist


log = logging.getLogger("whatsapp.finalize")


def _build_headline(text: str) -> str:
    if not text:
        return "Forwarded from WhatsApp"
    first_line = (text.split("\n", 1)[0] or "").strip()
    if not first_line:
        return "Forwarded from WhatsApp"
    if len(first_line) > 120:
        first_line = first_line[:119].rstrip() + "…"
    return first_line


async def finalize_story_from_thread(
    *,
    db: Session,
    sender_phone: str,
    user: User,
) -> Optional[Story]:
    """Drain the active thread for `sender_phone`, create a Story, return it.

    Returns None if the thread is empty (nothing to submit). Caller is
    responsible for sending the user-facing confirmation message.
    """
    ts = db.query(WhatsAppThreadState).filter_by(sender_phone=sender_phone).first()
    if ts is None:
        return None
    if (ts.pending_text_count or 0) == 0 and (ts.pending_media_count or 0) == 0:
        return None

    text = (ts.pending_text_concat or "").strip()

    # Build paragraphs: text first, then media (in receipt order)
    paragraphs: list[dict] = []
    if text:
        paragraphs.append({"id": str(uuid.uuid4()), "text": text})

    # Drain pending media (story_id linked after we have the new story.id)
    pending = buffer.drain_for_sender(db, sender_phone, story_id=None)
    for pm in pending:
        try:
            stored, _body, _ct, variants = await _persist_media(
                pm.gupshup_media_url, None, None,
            )
            if not stored:
                stored = pm.gupshup_media_url
        except Exception as e:
            log.warning("media persist failed for %s: %r", pm.gupshup_media_url, e)
            stored = pm.gupshup_media_url
            variants = None

        para: dict = {
            "id": str(uuid.uuid4()),
            "text": pm.caption or "",
            "media_path": stored,
            "media_type": _media_type_for(pm.media_type),
        }
        if variants:
            if variants.get("media_path_web"):
                para["media_path_web"] = variants["media_path_web"]
            if variants.get("media_path_thumb"):
                para["media_path_thumb"] = variants["media_path_thumb"]
        paragraphs.append(para)
        pm.storage_url = stored

    # Category classification (best-effort)
    try:
        cat_keys = org_category_keys(db, user.organization_id) if user.organization_id else []
        category = await classify_category(text, cat_keys) if text else None
    except Exception as e:
        log.warning("classify_category failed: %r", e)
        category = None

    new_id = str(uuid.uuid4())
    story = Story(
        id=new_id,
        organization_id=user.organization_id,
        seq_no=assign_next_seq(db, user.organization_id),
        reporter_id=user.id,
        assigned_to=None if user.user_type == "reporter" else user.id,
        assigned_match_reason=None if user.user_type == "reporter" else "manual",
        headline=_build_headline(text),
        category=category,
        paragraphs=paragraphs,
        status="submitted",
        submitted_at=now_ist(),
        source="whatsapp",
        whatsapp_session_open_until=now_ist() + timedelta(minutes=STITCH_MINUTES),
    )
    db.add(story)
    db.flush()

    # Link drained media rows to the new story
    for pm in pending:
        pm.drained_into_story_id = story.id

    # Close the thread state
    thread_state.close(db, sender_phone)
    return story
