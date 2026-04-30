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
from fastapi import APIRouter, Body, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from ..config import settings
from ..database import SessionLocal, get_db
from ..models.edition import Edition, EditionPage
from ..models.org_config import OrgConfig
from ..models.story import Story
from ..services import stt as stt_service
from ..services.categorizer import sweep_uncategorized
from ..services.storage import UPLOAD_DIR
from ..utils.tz import now_ist

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])


# Cap how many paragraphs one sweep handles so the request fits inside
# Cloud Scheduler's HTTP target deadline (default 30s; we set 300s).
_SWEEP_BATCH_LIMIT = 20
_MAX_ATTEMPTS = 3

# Categorisation sweep: same fits-in-300s budget. Each Sarvam call is
# ~1-2s, so 20 stories per tick comfortably finishes inside the deadline.
_CATEGORY_SWEEP_LIMIT = 20
_CATEGORY_LOOKBACK_DAYS = 14


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


@router.post("/sweep-pending-categorization")
async def sweep_pending_categorization(
    x_internal_token: Optional[str] = Header(default=None, alias="X-Internal-Token"),
):
    """Auto-categorise stories that landed without a category.

    Designed to run every 30 minutes. Picks up stories the inline
    background task missed (Sarvam was down, network blip, etc.) plus any
    stories the editor saved without categorising. Sequential per-story
    Sarvam calls; ``_CATEGORY_SWEEP_LIMIT`` per tick keeps token spend
    predictable and the request inside Scheduler's deadline.
    """
    _require_internal_token(x_internal_token)

    db: Session = SessionLocal()
    try:
        result = await sweep_uncategorized(
            db,
            limit=_CATEGORY_SWEEP_LIMIT,
            lookback_days=_CATEGORY_LOOKBACK_DAYS,
        )
    finally:
        db.close()

    return result


@router.post("/seed-todays-editions")
async def seed_todays_editions(
    payload: Optional[dict] = Body(default=None),
    x_internal_token: Optional[str] = Header(default=None, alias="X-Internal-Token"),
    db: Session = Depends(get_db),
):
    """Stamp out today's editions for every org with a non-empty
    ``edition_schedule``. Idempotent: a per-(org, date, title) pre-check
    skips existing rows. Stories that aren't placed on any page stay in
    review status until a future day's editions are created.

    Hit nightly (~02:00 IST) by Cloud Scheduler. Optional ``date``
    override in the body (ISO string) is for back-fills and tests.
    """
    _require_internal_token(x_internal_token)

    from datetime import date as _date

    payload = payload or {}
    if payload.get("date"):
        target = _date.fromisoformat(payload["date"])
    else:
        target = now_ist().date()
    weekday = target.weekday()  # Mon=0..Sun=6

    created: list[str] = []
    skipped: list[str] = []

    cfgs = db.query(OrgConfig).all()
    for cfg in cfgs:
        schedule = cfg.edition_schedule or []
        for tpl in schedule:
            if weekday not in (tpl.get("weekdays") or []):
                continue
            tag = f"{cfg.organization_id}:{target}:{tpl['name']}"
            existing = db.query(Edition).filter_by(
                organization_id=cfg.organization_id,
                publication_date=target,
                title=tpl["name"],
            ).first()
            if existing:
                skipped.append(tag)
                continue
            ed = Edition(
                organization_id=cfg.organization_id,
                publication_date=target,
                paper_type="daily",
                title=tpl["name"],
                status="draft",
            )
            db.add(ed)
            db.flush()
            for p in tpl.get("pages", []):
                db.add(EditionPage(
                    edition_id=ed.id,
                    page_number=p["page_number"],
                    page_name=p.get("page_name", ""),
                    sort_order=p["page_number"],
                ))
            created.append(tag)
    db.commit()
    return {"created": created, "skipped": skipped, "date": target.isoformat()}


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


@router.post("/sweep-news-retention")
async def sweep_news_retention(
    x_internal_token: Optional[str] = Header(default=None, alias="X-Internal-Token"),
    days: int = 60,
):
    """Delete news_articles older than ``days`` days (default 60).

    Designed to be hit once daily by Cloud Scheduler. Reviewers don't
    research multi-month-old articles; the news feed exists to surface
    fresh material. Without a retention sweep the table accumulates
    forever (~2.3K/day current ingest rate → 500K rows in ~7 months,
    ~1 GB with indexes), and every INSERT pays the maintenance cost of
    the running indexes.

    The DELETE is a single statement scoped by ``published_at`` so it
    plays nice with the index on that column. Falls back to
    ``fetched_at`` for rows missing ``published_at``.

    Returns the count of deleted rows so observability can spot if
    ingest has dropped (deleted == 0 over a long horizon would mean we
    aren't expiring anything, which would mean either the table is
    empty or the cron is broken).
    """
    _require_internal_token(x_internal_token)
    from sqlalchemy import text

    if days < 1:
        raise HTTPException(status_code=400, detail="days must be >= 1")

    db = SessionLocal()
    try:
        # Two-phase delete: published_at-bound rows first (covered by
        # ix_news_articles_published_at), then the no-published_at
        # rows by fetched_at fallback. Both phases run in a single tx.
        result_a = db.execute(text(
            "DELETE FROM news_articles "
            "WHERE published_at IS NOT NULL "
            "  AND published_at < now() - (:days || ' days')::interval"
        ), {"days": days})
        result_b = db.execute(text(
            "DELETE FROM news_articles "
            "WHERE published_at IS NULL "
            "  AND fetched_at < now() - (:days || ' days')::interval"
        ), {"days": days})
        db.commit()
        deleted = (result_a.rowcount or 0) + (result_b.rowcount or 0)
        logger.info(
            "news-retention-sweep: deleted %d articles older than %d days",
            deleted, days,
        )
        return {"deleted": deleted, "days": days}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/sweep-wp-push")
async def sweep_wp_push(
    x_internal_token: Optional[str] = Header(default=None, alias="X-Internal-Token"),
):
    """Drain pending WordPress pushes/retracts.

    Designed to be hit every 60s by Cloud Scheduler. The publisher
    handles its own create-vs-update branching, the WP-side status
    guard, and the retract path; this endpoint just opens a session,
    invokes the sweep, and commits.

    Returns counts so Cloud Scheduler / observability can spot
    backlogs (``picked`` rising = pushes outpacing the cron tick).
    """
    _require_internal_token(x_internal_token)
    from ..services import wordpress_publisher

    db = SessionLocal()
    try:
        result = await wordpress_publisher.sweep_pending(db)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
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
