"""Inbound WhatsApp webhook (Gupshup v2 payload format).

Reporters forward government press releases to the Vrittant WABA number
(+91 89843 36534, hosted by Gupshup). For each inbound message:

1. Look up the sender phone in the `users` table.
2. If registered + active, create a draft `Story` assigned to them with
   `source="whatsapp"` and the message text as the body. Reply with a
   confirmation.
3. If not registered, reply with a polite "contact your editor" note and
   drop the message.

Always returns 200 — Gupshup retries on any non-2xx, which would amplify
errors and double-create stories. Idempotency is enforced via the
`whatsapp_inbound_dedup` table (PK on Gupshup's `message.id`).
"""
import json
import logging
import os
import uuid

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.story import Story
from ..models.user import User
from ..models.webhook_dedup import WhatsappInboundDedup
from ..utils.tz import now_ist

router = APIRouter(prefix="/webhooks/whatsapp", tags=["webhooks"])
logger = logging.getLogger(__name__)

# The Vrittant WABA number provisioned in Gupshup. Hard-coded because it
# identifies the source of *outbound* replies; if the number ever changes
# this is the one place to update.
GUPSHUP_SOURCE_PHONE = "918984336534"
GUPSHUP_APP_NAME = "Vrittant"
GUPSHUP_API_URL = "https://api.gupshup.io/wa/api/v1/msg"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _normalize_phone(raw: str) -> str:
    """Gupshup sends '919...' (no plus); our DB stores '+919...'. Normalize."""
    raw = (raw or "").strip()
    if not raw:
        return raw
    return raw if raw.startswith("+") else "+" + raw


def _extract_content(inner_type: str, inner_payload: dict) -> tuple[str, str | None]:
    """Return (text, media_url) from a Gupshup v2 inner payload.

    Gupshup wraps the actual content under `payload.payload` and the type
    under `payload.type`. For text it's `{"text": "..."}`; for media it's
    `{"url": "...", "caption": "...", "name": "...", "contentType": "..."}`.
    """
    if inner_type == "text":
        return (inner_payload.get("text") or "", None)
    if inner_type in ("image", "video", "audio", "document", "file"):
        caption = inner_payload.get("caption") or inner_payload.get("name") or ""
        return (caption, inner_payload.get("url"))
    return ("", None)


async def _send_gupshup_reply(to_phone: str, text: str) -> None:
    """POST a text reply via Gupshup. No-op when no API key is configured
    (e.g. tests, local dev) so the integration degrades gracefully."""
    api_key = os.environ.get("GUPSHUP_API_KEY", "")
    if not api_key:
        logger.info("GUPSHUP_API_KEY unset; would have replied to %s: %s", to_phone, text)
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                GUPSHUP_API_URL,
                headers={"apikey": api_key},
                data={
                    "channel": "whatsapp",
                    "source": GUPSHUP_SOURCE_PHONE,
                    "destination": to_phone,
                    "message": json.dumps({"type": "text", "text": text}),
                    "src.name": GUPSHUP_APP_NAME,
                },
            )
    except Exception:  # pragma: no cover — best-effort reply
        logger.exception("Gupshup reply to %s failed", to_phone)


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------
@router.post("/gupshup")
async def gupshup_inbound(request: Request, db: Session = Depends(get_db)):
    body = await request.json()

    # Gupshup posts many event types; we only care about user-sent messages.
    # Status callbacks (sent/delivered/read/failed) come as type="message-event".
    if body.get("type") != "message":
        return {"ok": True, "skipped": "non-message event"}

    payload = body.get("payload") or {}
    msg_id = payload.get("id")
    sender_raw = (payload.get("sender") or {}).get("phone") or payload.get("source")
    if not msg_id or not sender_raw:
        return {"ok": True, "skipped": "missing id or sender"}

    # Idempotency check first — duplicate retries should be the cheapest path.
    if db.query(WhatsappInboundDedup).filter_by(message_id=msg_id).first():
        return {"ok": True, "skipped": "duplicate"}

    sender_phone = _normalize_phone(sender_raw)
    user = (
        db.query(User)
        .filter(User.phone == sender_phone, User.is_active == True)  # noqa: E712
        .first()
    )

    # Record the dedup row regardless of outcome — we don't want to keep
    # re-processing an unknown sender on every Gupshup retry.
    db.add(WhatsappInboundDedup(message_id=msg_id, received_at=now_ist()))

    if not user:
        db.commit()
        await _send_gupshup_reply(
            sender_raw,
            "This number is not registered with Vrittant. Please contact your editor.",
        )
        return {"ok": True, "skipped": "unknown sender"}

    inner_type = payload.get("type", "text")
    inner_payload = payload.get("payload") or {}
    text, media_url = _extract_content(inner_type, inner_payload)

    headline = (text.split("\n", 1)[0][:120] if text else "Forwarded from WhatsApp")
    paragraphs: list[dict] = []
    if text:
        paragraphs.append({"id": str(uuid.uuid4()), "text": text})
    if media_url:
        paragraphs.append({
            "id": str(uuid.uuid4()),
            "text": f"[Attachment: {media_url}]",
            "media_url": media_url,
        })

    story = Story(
        organization_id=user.organization_id,
        reporter_id=user.id,
        assigned_to=user.id,
        assigned_match_reason="manual",
        headline=headline,
        paragraphs=paragraphs,
        status="submitted",
        submitted_at=now_ist(),
        source="whatsapp",
    )
    story.refresh_search_text()
    db.add(story)
    db.commit()

    await _send_gupshup_reply(
        sender_raw,
        f"Saved as draft story #{story.id[:8]}. Open Vrittant to review and publish.",
    )
    return {"ok": True, "story_id": story.id}
