"""WordPress auto-publish for approved stories.

Vrittant approves a story → ``wp_push_status='pending'`` → cron sweep
hits :func:`push_or_update` → translates the Odia content to English
via Claude Haiku → uploads featured image to ``/wp-json/wp/v2/media``
→ creates (or updates) ``/wp-json/wp/v2/posts/{id?}`` with
``status=draft`` so the WP team is the human gate.

The same sweep also handles the un-approve path via :func:`retract`,
moving still-draft posts to the WP trash. Once a WP-side person has
already published or trashed a post, both paths become no-ops with a
``skipped_wp_status_*`` outcome — Vrittant never silently overwrites
work the WP team has owned.

Configuration lives on ``org_configs.wordpress_config`` (JSON);
credentials are referenced by name and resolved against the process
environment so they can come from Secret Manager. A missing or empty
config is graceful: the story stays at ``pending`` until config arrives.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import httpx
from sqlalchemy.orm import Session

from ..models.org_config import OrgConfig
from ..models.story import Story
from ..utils.tz import now_ist
from . import anthropic_client, sarvam_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class PushResult:
    """Outcome of a single push/update/retract attempt.

    ``status`` is what we stamp onto ``stories.wp_push_status``. Callers
    set ``ok``/``failed``/``skipped_*`` based on this. Errors are stored
    on ``stories.wp_push_error`` for the editor to see.
    """
    status: str
    error: Optional[str] = None
    wp_post_id: Optional[int] = None
    wp_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def _load_wp_config(db: Session, organization_id: str) -> Optional[dict]:
    """Return the per-org WP config dict, or None if not configured.

    The dict carries the resolved app_password (read from env / Secret
    Manager) so callers don't need to know about secret resolution.
    """
    cfg_row = (
        db.query(OrgConfig)
        .filter(OrgConfig.organization_id == organization_id)
        .first()
    )
    if not cfg_row or not cfg_row.wordpress_config:
        return None
    cfg = dict(cfg_row.wordpress_config)
    if not cfg.get("base_url") or not cfg.get("username"):
        return None
    secret_name = cfg.get("app_password_secret") or ""
    if not secret_name:
        return None
    app_password = os.environ.get(secret_name) or ""
    if not app_password:
        return None
    cfg["_app_password"] = app_password
    return cfg


def _auth(cfg: dict) -> httpx.BasicAuth:
    return httpx.BasicAuth(cfg["username"], cfg["_app_password"])


# ---------------------------------------------------------------------------
# Translation
# ---------------------------------------------------------------------------

_TRANSLATE_SYSTEM = (
    "You are a senior wire-service editor translating Odia news stories "
    "to clean, neutral, publication-ready English for a regional "
    "newspaper's website. Preserve all facts, names, places, and "
    "numbers exactly. Do not add commentary, framing, or speculation. "
    "Use Indian English conventions (e.g. 'Bhubaneswar' not "
    "'Bhubaneśvar'). Keep paragraphing — return one paragraph per "
    "input paragraph. Headlines should be active and concise (under "
    "100 characters)."
)


async def translate_story_to_english(
    *,
    headline: str,
    body: str,
    user_id: Optional[str] = None,
    story_id: Optional[str] = None,
) -> dict:
    """Return ``{"title": ..., "body": ..., "excerpt": ...}`` in English.

    Body keeps paragraph breaks (``\\n\\n`` separated). Excerpt is a
    single-sentence summary (~30 words). Cost lands in
    ``sarvam_usage_log`` with ``service='anthropic_chat'`` via the
    existing client.
    """
    user_prompt = (
        "Translate the following Odia news story into English. Return "
        "JSON with three keys: 'title' (string, ≤100 chars), 'body' "
        "(string, paragraphs joined with two newlines), and 'excerpt' "
        "(single sentence, ~30 words). Return ONLY the JSON object — "
        "no markdown fences, no preamble.\n\n"
        f"HEADLINE: {headline}\n\n"
        f"BODY:\n{body}\n"
    )

    # Cost ledger is shared with Sarvam; the helper just stamps a context
    # onto the next ``_write_log_row`` call so /usage/cost reports can
    # group spend by story / user / bucket.
    with sarvam_client.cost_context(
        bucket="wordpress-translate",
        story_id=story_id,
        user_id=user_id,
    ):
        response = await anthropic_client.chat(
            model="claude-haiku-4-5",
            system=_TRANSLATE_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=2000,
            temperature=0.2,
        )
    text = anthropic_client.extract_text(response).strip()

    # Tolerate an occasional ```json``` fence even though we asked for raw.
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Claude returned non-JSON for translate: {text[:200]}") from exc
    title = (parsed.get("title") or "").strip()
    body_out = (parsed.get("body") or "").strip()
    excerpt = (parsed.get("excerpt") or "").strip()
    if not title or not body_out:
        raise ValueError(f"Claude returned incomplete translation: {parsed}")
    return {"title": title, "body": body_out, "excerpt": excerpt}


# ---------------------------------------------------------------------------
# WordPress REST helpers
# ---------------------------------------------------------------------------

async def _get_post_status(client: httpx.AsyncClient, base_url: str, post_id: int, auth: httpx.BasicAuth) -> Optional[str]:
    """Return the WP-side ``status`` of a post, or None if 404."""
    r = await client.get(
        f"{base_url}/wp-json/wp/v2/posts/{post_id}?context=edit",
        auth=auth,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return (r.json() or {}).get("status")


async def _upload_featured_media(
    client: httpx.AsyncClient,
    base_url: str,
    auth: httpx.BasicAuth,
    image_url: str,
    filename: str,
) -> Optional[int]:
    """Download a Vrittant-side image and upload it to WP /media.

    Returns the WP attachment id or None if anything fails. WP
    enforces a multipart upload with a Content-Disposition header that
    names the file — without it WP rejects the request.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as down:
            blob = await down.get(image_url)
            blob.raise_for_status()
            content_type = blob.headers.get("content-type", "image/jpeg")
            payload = blob.content
    except Exception as exc:  # noqa: BLE001 — image upload is best-effort
        logger.warning("WP media: download failed for %s: %s", image_url, exc)
        return None
    try:
        r = await client.post(
            f"{base_url}/wp-json/wp/v2/media",
            content=payload,
            headers={
                "Content-Type": content_type,
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
            auth=auth,
        )
        if r.status_code not in (200, 201):
            logger.warning("WP media upload failed %s: %s", r.status_code, r.text[:300])
            return None
        return int((r.json() or {}).get("id"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("WP media upload errored: %s", exc)
        return None


def _featured_image_url(story: Story) -> Optional[tuple[str, str]]:
    """First photo paragraph's public URL + filename suggestion.

    Only returns fully-qualified URLs (https://...) since WP fetches
    the file directly from us. GCS-backed uploads are already stored as
    public storage.googleapis.com URLs in ``media_path``; local-disk
    paths are skipped (no featured image attached on dev).
    """
    for p in (story.paragraphs or []):
        if not isinstance(p, dict):
            continue
        media_path = p.get("media_path") or p.get("photo_path")
        if not media_path or not isinstance(media_path, str):
            continue
        if not media_path.startswith(("http://", "https://")):
            continue
        media_type = (p.get("media_type") or "").lower()
        is_photo = media_type in ("photo", "image", "") or media_path.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
        if not is_photo:
            continue
        name = (p.get("media_name") or "featured.jpg").replace("/", "_")
        return media_path, name
    return None


def _build_post_payload(
    *,
    english: dict,
    cfg: dict,
    category_key: Optional[str],
    featured_media_id: Optional[int],
) -> dict:
    payload: dict[str, Any] = {
        "title": english["title"],
        "content": english["body"].replace("\n\n", "\n\n"),  # WP accepts plain newlines as paragraph breaks
        "excerpt": english.get("excerpt") or "",
        "status": cfg.get("default_status") or "draft",
    }
    if cfg.get("default_author_id"):
        payload["author"] = int(cfg["default_author_id"])
    cat_map = cfg.get("category_map") or {}
    if category_key and category_key in cat_map:
        payload["categories"] = [int(cat_map[category_key])]
    if featured_media_id:
        payload["featured_media"] = featured_media_id
    return payload


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

async def push_or_update(db: Session, story: Story, *, force: bool = False) -> PushResult:
    """Create or update a WP draft for ``story``.

    Idempotent: if ``story.wp_post_id`` is set and the WP-side post is
    still ``draft``, this updates that post in place. If the WP team
    has published / trashed it, the call is a no-op and reports back
    via ``status='skipped_wp_status_*'`` unless ``force=True``.
    """
    cfg = _load_wp_config(db, story.organization_id)
    if not cfg:
        return PushResult(status="skipped_no_config", error="WordPress not configured for this org")

    base_url = cfg["base_url"].rstrip("/")
    auth = _auth(cfg)

    # Translate first — most expensive step, but failing here doesn't
    # leave a half-created WP post behind.
    body_text = "\n\n".join(
        (p.get("text") or "").strip()
        for p in (story.paragraphs or [])
        if isinstance(p, dict) and not p.get("media_path") and (p.get("text") or "").strip()
    )
    if not body_text:
        return PushResult(status="failed", error="Story has no body text to translate")

    try:
        english = await translate_story_to_english(
            headline=story.headline or "",
            body=body_text,
            user_id=story.assigned_to,
            story_id=story.id,
        )
    except Exception as exc:  # noqa: BLE001
        return PushResult(status="failed", error=f"Translation failed: {exc}")

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Update branch — guard against clobbering WP-side decisions.
        if story.wp_post_id and not force:
            try:
                wp_status = await _get_post_status(client, base_url, story.wp_post_id, auth)
            except httpx.HTTPError as exc:
                return PushResult(status="failed", error=f"GET post failed: {exc}")
            if wp_status is None:
                # 404 — WP team hard-deleted; treat next push as fresh create
                story.wp_post_id = None
            elif wp_status != "draft":
                return PushResult(
                    status=f"skipped_wp_status_{wp_status}",
                    error=None,
                    wp_post_id=story.wp_post_id,
                    wp_url=story.wp_url,
                )

        # Featured image (best-effort; failure doesn't block the push).
        featured = None
        img = _featured_image_url(story)
        if img:
            url, filename = img
            featured = await _upload_featured_media(client, base_url, auth, url, filename)

        payload = _build_post_payload(
            english=english,
            cfg=cfg,
            category_key=story.category,
            featured_media_id=featured,
        )

        url = (
            f"{base_url}/wp-json/wp/v2/posts/{story.wp_post_id}"
            if story.wp_post_id
            else f"{base_url}/wp-json/wp/v2/posts"
        )
        try:
            r = await client.post(url, json=payload, auth=auth)
        except httpx.HTTPError as exc:
            return PushResult(status="failed", error=f"POST failed: {exc}")
        if r.status_code not in (200, 201):
            return PushResult(status="failed", error=f"WP {r.status_code}: {r.text[:300]}")
        data = r.json() or {}

    return PushResult(
        status="ok",
        wp_post_id=int(data.get("id")) if data.get("id") else story.wp_post_id,
        wp_url=data.get("link") or story.wp_url,
    )


async def retract(db: Session, story: Story) -> PushResult:
    """Trash the WP draft if still in draft. Skip if already published."""
    if not story.wp_post_id:
        return PushResult(status="ok", error=None)  # nothing to retract
    cfg = _load_wp_config(db, story.organization_id)
    if not cfg:
        return PushResult(status="skipped_no_config")
    base_url = cfg["base_url"].rstrip("/")
    auth = _auth(cfg)
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            wp_status = await _get_post_status(client, base_url, story.wp_post_id, auth)
        except httpx.HTTPError as exc:
            return PushResult(status="failed", error=f"GET post failed: {exc}")
        if wp_status is None:
            # Already gone; treat retract as success.
            return PushResult(status="ok")
        if wp_status != "draft":
            # WP team published it — we don't unpublish silently.
            return PushResult(status=f"skipped_wp_status_{wp_status}")
        try:
            r = await client.delete(
                f"{base_url}/wp-json/wp/v2/posts/{story.wp_post_id}",  # default → trash, ?force=true to hard-delete
                auth=auth,
            )
        except httpx.HTTPError as exc:
            return PushResult(status="failed", error=f"DELETE failed: {exc}")
        if r.status_code not in (200, 410):
            return PushResult(status="failed", error=f"WP {r.status_code}: {r.text[:300]}")
    return PushResult(status="ok")


# ---------------------------------------------------------------------------
# Sweep entry point (called from /internal/sweep-wp-push)
# ---------------------------------------------------------------------------

MAX_ATTEMPTS = 5
BATCH_SIZE = 10


async def sweep_pending(db: Session) -> dict:
    """Drain up to ``BATCH_SIZE`` pending pushes/retracts.

    Pure data manipulation — caller (the FastAPI route) commits.
    Returns counts for observability.
    """
    pending = (
        db.query(Story)
        .filter(
            Story.wp_push_status.in_(["pending", "retract"]),
            Story.wp_push_attempts < MAX_ATTEMPTS,
            Story.deleted_at.is_(None),
        )
        .order_by(Story.wp_push_attempts.asc(), Story.updated_at.asc())
        .limit(BATCH_SIZE)
        .all()
    )

    processed: dict[str, int] = {"ok": 0, "failed": 0, "skipped": 0, "exhausted": 0}
    for story in pending:
        story.wp_push_attempts = (story.wp_push_attempts or 0) + 1
        try:
            if story.wp_push_status == "retract":
                result = await retract(db, story)
            else:
                result = await push_or_update(db, story)
        except Exception as exc:  # noqa: BLE001
            logger.exception("sweep_pending: unhandled error on story %s", story.id)
            result = PushResult(status="failed", error=f"unhandled: {exc}")

        story.wp_push_error = result.error
        if result.wp_post_id:
            story.wp_post_id = result.wp_post_id
        if result.wp_url:
            story.wp_url = result.wp_url
        if result.status == "ok":
            story.wp_push_status = "ok"
            story.wp_pushed_at = now_ist()
            processed["ok"] += 1
        elif result.status.startswith("skipped"):
            # WP team has acted (or no config yet) — mirror the WP-side
            # decision and stop retrying. wp_push_status carries the
            # specific reason (skipped_no_config, skipped_wp_status_publish, …).
            story.wp_push_status = result.status
            processed["skipped"] += 1
        else:
            # Transient failure — keep wp_push_status='pending' so the
            # next sweep retries, until we hit MAX_ATTEMPTS at which
            # point we flip to 'failed' and stop. The error text on the
            # row tells the editor what went wrong.
            if story.wp_push_attempts >= MAX_ATTEMPTS:
                story.wp_push_status = "failed"
                processed["exhausted"] += 1
            # else: leave wp_push_status as it was ('pending' or 'retract')
            processed["failed"] += 1
    return {"picked": len(pending), **processed}
