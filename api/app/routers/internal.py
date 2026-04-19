"""Internal endpoints — invoked by Cloud Scheduler / cron, not by clients.

Auth is a shared secret in the ``X-Internal-Token`` header. The token lives
in Cloud Run as the ``INTERNAL_TOKEN`` env var (set from Secret Manager) and
in the Cloud Scheduler job config. Empty token = endpoints disabled (so
dev environments can't be hit by accident).
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx
from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from ..config import settings
from ..database import SessionLocal
from ..models.story import Story
from ..services import stt as stt_service
from ..services.storage import UPLOAD_DIR
from ..utils.tz import now_ist

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])


# Cap how many paragraphs one sweep handles so the request fits inside
# Cloud Scheduler's HTTP target deadline (default 30s; we set 300s).
_SWEEP_BATCH_LIMIT = 20
_MAX_ATTEMPTS = 3


def _require_internal_token(token: Optional[str]) -> None:
    if not settings.INTERNAL_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal endpoints disabled (no INTERNAL_TOKEN set)",
        )
    if not token or token != settings.INTERNAL_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid internal token",
        )


@router.post("/sweep-pending-stt")
async def sweep_pending_stt(
    x_internal_token: Optional[str] = Header(default=None, alias="X-Internal-Token"),
):
    """Re-run STT for paragraphs marked ``pending_retry``.

    Designed to be hit every 5 minutes by Cloud Scheduler. Picks up to
    ``_SWEEP_BATCH_LIMIT`` paragraphs per call; gives up after
    ``_MAX_ATTEMPTS`` total attempts (set in upload-audio + here combined).
    """
    _require_internal_token(x_internal_token)

    db: Session = SessionLocal()
    try:
        candidates = _find_pending_paragraphs(db, limit=_SWEEP_BATCH_LIMIT)
    finally:
        db.close()

    if not candidates:
        return {"swept": 0, "succeeded": 0, "still_failing": 0, "given_up": 0}

    succeeded = 0
    still_failing = 0
    given_up = 0

    for item in candidates:
        story_id = item["story_id"]
        para_id = item["paragraph_id"]
        attempts = item["attempts"]
        audio_url = item["audio_url"]
        language_code = item["language_code"] or "od-IN"

        if attempts >= _MAX_ATTEMPTS:
            _mark_status(story_id, para_id, "failed", increment_attempts=False)
            given_up += 1
            continue

        audio_bytes = await _fetch_audio_bytes(audio_url)
        if not audio_bytes:
            logger.warning("sweep: audio fetch failed for %s/%s", story_id, para_id)
            _mark_status(story_id, para_id, "pending_retry", increment_attempts=True)
            still_failing += 1
            continue

        try:
            transcript = await stt_service.transcribe_audio(
                audio_bytes,
                filename=os.path.basename(audio_url) or "audio.m4a",
                language_code=language_code,
            )
        except stt_service.SttRetryable as exc:
            logger.info("sweep: still retryable for %s/%s: %s", story_id, para_id, exc)
            _mark_status(story_id, para_id, "pending_retry", increment_attempts=True)
            still_failing += 1
            continue
        except stt_service.SttError as exc:
            logger.warning("sweep: permanent failure for %s/%s: %s", story_id, para_id, exc)
            _mark_status(story_id, para_id, "failed", increment_attempts=True)
            given_up += 1
            continue
        except Exception as exc:  # noqa: BLE001
            logger.exception("sweep: unexpected error for %s/%s: %s", story_id, para_id, exc)
            _mark_status(story_id, para_id, "pending_retry", increment_attempts=True)
            still_failing += 1
            continue

        _apply_transcript(story_id, para_id, transcript)
        succeeded += 1

    return {
        "swept": len(candidates),
        "succeeded": succeeded,
        "still_failing": still_failing,
        "given_up": given_up,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_pending_paragraphs(db: Session, *, limit: int) -> list[dict]:
    """Return up to ``limit`` paragraphs across all stories needing retry.

    The ``paragraphs`` column is plain JSON (not JSONB), so we can't push
    the predicate into Postgres efficiently. The volume is small in
    practice — recent stories only — so a Python-side scan is fine.
    Order by oldest updated first so we don't starve old failures.
    """
    out: list[dict] = []
    # Only look at stories touched in the last 7 days. Audio older than
    # that is unlikely to retry-succeed — Sarvam outages don't last days.
    from datetime import timedelta
    cutoff = now_ist() - timedelta(days=7)
    stories = (
        db.query(Story)
        .filter(Story.updated_at >= cutoff)
        .filter(Story.deleted_at.is_(None))
        .order_by(Story.updated_at.asc())
        .all()
    )
    for story in stories:
        for p in (story.paragraphs or []):
            if not isinstance(p, dict):
                continue
            if p.get("transcription_status") != "pending_retry":
                continue
            if not p.get("transcription_audio_path"):
                continue
            out.append({
                "story_id": story.id,
                "paragraph_id": p.get("id"),
                "attempts": p.get("transcription_attempts") or 0,
                "audio_url": p["transcription_audio_path"],
                "language_code": p.get("transcription_language"),
            })
            if len(out) >= limit:
                return out
    return out


def _mark_status(story_id: str, paragraph_id: str, new_status: str, *, increment_attempts: bool) -> None:
    db = SessionLocal()
    try:
        story = db.query(Story).filter(Story.id == story_id).first()
        if story is None:
            return
        paragraphs = list(story.paragraphs or [])
        for i, p in enumerate(paragraphs):
            if isinstance(p, dict) and p.get("id") == paragraph_id:
                p = dict(p)
                p["transcription_status"] = new_status
                if increment_attempts:
                    p["transcription_attempts"] = (p.get("transcription_attempts") or 0) + 1
                paragraphs[i] = p
                break
        else:
            return
        story.paragraphs = paragraphs
        story.updated_at = now_ist()
        flag_modified(story, "paragraphs")
        db.commit()
    finally:
        db.close()


def _apply_transcript(story_id: str, paragraph_id: str, transcript: str) -> None:
    db = SessionLocal()
    try:
        story = db.query(Story).filter(Story.id == story_id).first()
        if story is None:
            return
        paragraphs = list(story.paragraphs or [])
        for i, p in enumerate(paragraphs):
            if isinstance(p, dict) and p.get("id") == paragraph_id:
                p = dict(p)
                p["transcription_status"] = "ok"
                p["transcription_attempts"] = (p.get("transcription_attempts") or 0) + 1
                # Same rule as the upload-time background task: never clobber
                # text the user can already see.
                if transcript and not (p.get("text") or "").strip():
                    p["text"] = transcript
                paragraphs[i] = p
                break
        else:
            return
        story.paragraphs = paragraphs
        story.updated_at = now_ist()
        story.refresh_search_text()
        flag_modified(story, "paragraphs")
        db.commit()
    finally:
        db.close()


async def _fetch_audio_bytes(audio_url: str) -> bytes:
    """Pull audio bytes back from where ``save_file`` parked them."""
    if audio_url.startswith("http://") or audio_url.startswith("https://"):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(audio_url)
                if resp.status_code != 200:
                    return b""
                return resp.content
        except httpx.RequestError:
            return b""
    rel = audio_url.lstrip("/").removeprefix("uploads/")
    path = os.path.join(UPLOAD_DIR, rel)
    if not os.path.exists(path):
        return b""
    with open(path, "rb") as f:
        return f.read()
