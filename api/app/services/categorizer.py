"""Best-effort LLM categorisation for inbound stories.

Used at ingestion time (WhatsApp webhook, editor save) and as a periodic
sweep so reviewers don't have to tag every story by hand. The contract is
best-effort: if Sarvam is unreachable, slow, or returns garbage, we leave
the category unset. **No caller should ever fail because of categorisation.**

Three entry points:
    * ``classify_category`` — async, used by webhook handlers.
    * ``categorize_story_in_background`` — sync wrapper for FastAPI
      ``BackgroundTasks``; opens its own DB session and updates the row.
    * ``sweep_uncategorized`` — batch helper for the cron endpoint.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Iterable, Optional

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from . import sarvam_client

logger = logging.getLogger(__name__)

# Keep the prompt small. Sarvam-30b is fluent in Odia/Hindi/English so we
# don't need to translate first — just hand it the message and the
# allowed keys and ask for one back.
_SYSTEM = (
    "You are a news desk categoriser. Read the news message and pick the "
    "single best category from the allowed list. Reply with only the "
    "category key (lowercase, no punctuation, no explanation). If nothing "
    "fits, reply 'other'."
)

# Sarvam-30b is a reasoning model — it spends completion tokens on an
# internal think-pass before emitting the answer. With a tight cap (we
# tried 16, then 600) it hits finish_reason="length" mid-think and
# returns content=null every time. Empirically the reasoning pass alone
# burns ~900-1000 tokens even with reasoning_effort=low for short
# Odia/English prompts, so 2000 is the safe minimum for the answer to
# actually land. Cost ≈ $0.0005/call — 80-story backfill ≈ 4¢.
_MAX_TOKENS = 2000
_TIMEOUT_SECONDS = 30.0


async def classify_category(
    text: str,
    allowed_keys: Iterable[str],
) -> Optional[str]:
    """Return the best-fit category key for *text*, or ``None`` on failure.

    *allowed_keys* is the org's configured set of category keys (e.g.
    ``["politics", "sports", "crime", ...]``). Pass an empty iterable
    and we'll skip the call and return ``None``.
    """
    keys = [k for k in allowed_keys if k]
    if not keys or not (text and text.strip()):
        return None

    if not settings.GEMINI_API_KEY:
        return None

    user_msg = (
        f"Allowed categories: {', '.join(keys)}\n\n"
        f"News message:\n{text.strip()[:2000]}"
    )

    try:
        from . import gemini_client
        raw = await gemini_client.chat(
            prompt=user_msg,
            system=_SYSTEM,
            max_tokens=_MAX_TOKENS,
            temperature=0.0,
            timeout=_TIMEOUT_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001 — best-effort categorisation
        logger.warning("categorizer: gemini call failed: %s", exc)
        return None

    if not isinstance(raw, str) or not raw:
        return None

    # Strip <think> tags, lower-case, keep alnum + underscore. The model
    # sometimes wraps a single key in quotes or returns "Key: politics" —
    # the regex sweep handles all of that without us hand-rolling cases.
    cleaned = re.sub(r"<think(?:ing)?>[\s\S]*?</think(?:ing)?>", "", raw, flags=re.IGNORECASE)
    cleaned = cleaned.strip().lower()
    tokens = re.findall(r"[a-z_]+", cleaned)

    keys_set = {k.lower() for k in keys}
    for tok in tokens:
        if tok in keys_set:
            return tok

    # The model said something but it doesn't match any key — log so we
    # can spot prompt drift, then give up.
    logger.info("categorizer: unmatched reply %r (allowed=%s)", raw[:80], keys)
    return None


# ---------------------------------------------------------------------------
# Org category-keys lookup — used by the webhook AND the editor save path.
# ---------------------------------------------------------------------------

def org_category_keys(db: Session, organization_id: str) -> list[str]:
    """Return the org's active category keys, falling back to platform
    defaults if the org has no OrgConfig row or empty categories.

    Imported lazily to avoid a circular import (models import services).
    """
    from ..models.org_config import DEFAULT_CATEGORIES, OrgConfig

    cfg = (
        db.query(OrgConfig)
        .filter(OrgConfig.organization_id == organization_id)
        .first()
    )
    raw = (cfg.categories if cfg else None) or DEFAULT_CATEGORIES
    return [
        c["key"] for c in raw
        if isinstance(c, dict) and c.get("key") and c.get("is_active", True)
    ]


# ---------------------------------------------------------------------------
# Story-level helpers used by the editor save path and the cron sweep.
# ---------------------------------------------------------------------------

def _story_text_for_classification(story) -> str:
    """Build a short snippet to send to Sarvam.

    Uses headline + first non-empty paragraph text. Caps to keep token
    spend flat regardless of story length — the model only needs enough
    to pick a slot, not the whole article.
    """
    parts: list[str] = []
    if story.headline:
        parts.append(story.headline.strip())
    for p in (story.paragraphs or []):
        if not isinstance(p, dict):
            continue
        text = (p.get("text") or "").strip()
        if text:
            parts.append(text)
            break  # one body paragraph is plenty
    return "\n\n".join(parts).strip()


def categorize_story_in_background(
    story_id: str,
    expected_org_id: Optional[str] = None,
) -> None:
    """Sync entrypoint for ``BackgroundTasks``: classify one story and persist.

    Opens its own DB session (FastAPI's request-scoped session is gone by
    the time background tasks run). Skips work if the story already has a
    category, has no usable text, or has been deleted.

    [expected_org_id] is the organization the calling endpoint validated
    the story belongs to. We re-check inside the helper as
    defense-in-depth: a future caller that forgets to validate before
    queueing this task will quietly drop the categorization rather than
    write to a story in a different org. Optional for backward-compat —
    callers should always pass it.

    Failures are swallowed — categorisation is best-effort. The cron sweep
    will retry on the next tick.
    """
    from ..database import SessionLocal
    from ..models.story import Story

    db: Session = SessionLocal()
    try:
        q = db.query(Story).filter(
            Story.id == story_id, Story.deleted_at.is_(None)
        )
        if expected_org_id is not None:
            q = q.filter(Story.organization_id == expected_org_id)
        story = q.first()
        if story is None:
            return
        if (story.category or "").strip():
            return  # someone (human or earlier task) already set it

        text = _story_text_for_classification(story)
        if not text:
            return

        keys = org_category_keys(db, story.organization_id)
        if not keys:
            return

        try:
            async def _classify_attributed():
                with sarvam_client.cost_context(story_id=story_id):
                    return await classify_category(text, keys)
            category = asyncio.run(_classify_attributed())
        except RuntimeError:
            # Already in an event loop (shouldn't happen in BackgroundTasks
            # context, but safe to handle). Skip rather than crash.
            logger.warning("categorize_story_in_background: nested event loop, skipping %s", story_id)
            return

        if not category:
            return

        # Re-read inside the same session so we don't clobber a parallel
        # human-tagged category. The race window is tiny but real. Org
        # filter is preserved on the re-fetch — same defense-in-depth as
        # the initial query.
        re_q = db.query(Story).filter(Story.id == story_id)
        if expected_org_id is not None:
            re_q = re_q.filter(Story.organization_id == expected_org_id)
        story = re_q.first()
        if story is None or (story.category or "").strip():
            return
        story.category = category
        db.commit()
        logger.info("auto-categorized story=%s as %s", story_id, category)
    except Exception as exc:  # noqa: BLE001
        # Categorisation must never break the calling request.
        logger.warning("categorize_story_in_background: failed for %s: %s", story_id, exc)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
    finally:
        db.close()


async def sweep_uncategorized(db: Session, *, limit: int = 20, lookback_days: int = 14) -> dict:
    """Classify up to ``limit`` recently-touched, uncategorised stories.

    Runs synchronously (one Sarvam call per story) — the helper itself is
    async so the cron endpoint can ``await`` it. Sequential calls keep us
    inside Sarvam's request budget; ~20 calls fit comfortably inside the
    300s Cloud Scheduler deadline.

    Skips stories with no usable text (empty + no paragraphs). Restricts
    to the last ``lookback_days`` so we don't churn over stale archives.
    """
    from datetime import timedelta

    from ..models.story import Story
    from ..utils.tz import now_ist

    cutoff = now_ist() - timedelta(days=lookback_days)
    candidates = (
        db.query(Story)
        .filter(Story.updated_at >= cutoff)
        .filter(Story.deleted_at.is_(None))
        .filter((Story.category.is_(None)) | (Story.category == ""))
        .order_by(Story.updated_at.desc())
        .limit(limit)
        .all()
    )

    swept = succeeded = skipped_no_text = failed = 0
    for story in candidates:
        swept += 1
        text = _story_text_for_classification(story)
        if not text:
            skipped_no_text += 1
            continue
        keys = org_category_keys(db, story.organization_id)
        if not keys:
            skipped_no_text += 1
            continue
        with sarvam_client.cost_context(story_id=story.id):
            category = await classify_category(text, keys)
        if not category:
            failed += 1
            continue
        # Re-fetch the row freshly so we don't clobber a parallel update.
        fresh = db.query(Story).filter(Story.id == story.id).first()
        if fresh is None or (fresh.category or "").strip():
            continue
        fresh.category = category
        db.commit()
        succeeded += 1
        logger.info("sweep: auto-categorized story=%s as %s", story.id, category)

    return {
        "swept": swept,
        "succeeded": succeeded,
        "skipped_no_text": skipped_no_text,
        "failed": failed,
    }
