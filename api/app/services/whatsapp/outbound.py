"""Gupshup outbound message API wrapper.

Four primitives:
- send_text(): plain text reply
- send_interactive_buttons(): text + up to 3 reply buttons
- send_interactive_list(): text + List CTA opening rows (menu fallback)
- edit_or_send_interactive(): tries to edit an existing interactive
  message; falls back to a fresh send if Gupshup rejects/errors. Caller
  stores the returned msg_id back into thread_state.interactive_msg_id
  either way.

Config lives as module constants + GUPSHUP_API_KEY env var, matching
the convention used by the legacy api/app/routers/webhooks_whatsapp.py.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Optional, Sequence, Tuple

import httpx

log = logging.getLogger("whatsapp.outbound")

GUPSHUP_SOURCE_PHONE = "918984336534"
GUPSHUP_APP_NAME = "Vrittant"
GUPSHUP_BASE = "https://api.gupshup.io/wa/api/v1"


def _api_key() -> str:
    return os.environ.get("GUPSHUP_API_KEY", "")


def _headers() -> dict:
    return {
        "apikey": _api_key(),
        "Content-Type": "application/x-www-form-urlencoded",
    }


def _base_payload(to: str) -> dict:
    return {
        "channel": "whatsapp",
        "source": GUPSHUP_SOURCE_PHONE,
        "destination": to.lstrip("+"),
        "src.name": GUPSHUP_APP_NAME,
    }


async def send_text(*, to: str, body: str) -> Optional[str]:
    """Send a plain text reply. Returns the Gupshup messageId on success,
    None on any failure (logged but not raised — callers should not
    branch on outbound failures)."""
    payload = {**_base_payload(to), "message": json.dumps({"type": "text", "text": body})}
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{GUPSHUP_BASE}/msg", data=payload, headers=_headers())
    except Exception as e:
        log.warning("send_text raised: %r", e)
        return None
    if r.status_code not in (200, 202):
        log.warning("send_text http %s: %s", r.status_code, r.text[:200])
        return None
    try:
        return r.json().get("messageId")
    except Exception:
        return None


def _build_interactive_button_message(
    body: str,
    buttons: Sequence[Tuple[str, str]],
    header: Optional[str] = None,
) -> dict:
    """Construct Gupshup's quick_reply payload for buttons.

    Gupshup partner API v1 uses a proprietary format that is NOT the
    WhatsApp Cloud API native shape — sending `type: "interactive"`
    causes Gupshup to forward the JSON literally as a text message
    (the user sees raw `{"type":...}` in WhatsApp).

    Their format for buttons:

        {
          "type": "quick_reply",
          "msgid": "<unique-id>",
          "content": {"type": "text", "header": "...", "text": "..."},
          "options": [
            {"type": "text", "title": "Submit", "postbackText": "submit_thread"},
            ...
          ]
        }

    `postbackText` is what comes back in the inbound webhook when the
    button is tapped — it replaces WhatsApp Cloud API's button id.
    Labels still capped at 20 chars (WhatsApp UI limit, regardless of
    API surface).
    """
    msg = {
        "type": "quick_reply",
        "msgid": str(uuid.uuid4())[:24],
        "content": {
            "type": "text",
            "text": body,
        },
        "options": [
            {"type": "text", "title": label[:20], "postbackText": bid}
            for bid, label in list(buttons)[:3]
        ],
    }
    if header:
        msg["content"]["header"] = header
    return msg


async def send_interactive_buttons(
    *, to: str, body: str,
    buttons: Sequence[Tuple[str, str]],
    header: Optional[str] = None,
) -> Optional[str]:
    """Send a text body + up to 3 reply buttons. `buttons` is a sequence
    of (button_id, label) — labels truncated to 20 chars."""
    msg = _build_interactive_button_message(body, buttons, header)
    payload = {**_base_payload(to), "message": json.dumps(msg)}
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{GUPSHUP_BASE}/msg", data=payload, headers=_headers())
    except Exception as e:
        log.warning("send_interactive_buttons raised: %r", e)
        return None
    if r.status_code not in (200, 202):
        log.warning("send_interactive_buttons http %s: %s", r.status_code, r.text[:200])
        return None
    try:
        return r.json().get("messageId")
    except Exception:
        return None


async def send_interactive_list(
    *, to: str, body: str, button_label: str,
    sections: Sequence[Tuple[str, Sequence[Tuple[str, str, Optional[str]]]]],
    header: Optional[str] = None,
) -> Optional[str]:
    """Send a List Message via Gupshup's `list` proprietary format.

    Gupshup's shape:

        {
          "type": "list",
          "msgid": "<unique-id>",
          "title": "Header",
          "body": "Body text",
          "globalButtons": [{"type": "text", "title": "Open menu"}],
          "items": [
            {
              "title": "Section title",
              "subtitle": "...",  // optional
              "options": [
                {"type": "text", "title": "Row title",
                 "description": "Row desc", "postbackText": "row_id"}
              ]
            }
          ]
        }

    `postbackText` becomes the inbound payload when a row is tapped.
    """
    items = []
    for title, rows in sections:
        options = []
        for rid, rtitle, rdesc in list(rows)[:10]:
            opt: dict = {
                "type": "text",
                "title": rtitle[:24],
                "postbackText": rid,
            }
            if rdesc:
                opt["description"] = rdesc[:72]
            options.append(opt)
        items.append({"title": title[:24], "options": options})

    msg = {
        "type": "list",
        "msgid": str(uuid.uuid4())[:24],
        "body": body,
        "globalButtons": [{"type": "text", "title": button_label[:20]}],
        "items": items[:10],
    }
    if header:
        msg["title"] = header
    payload = {**_base_payload(to), "message": json.dumps(msg)}
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{GUPSHUP_BASE}/msg", data=payload, headers=_headers())
    except Exception as e:
        log.warning("send_interactive_list raised: %r", e)
        return None
    if r.status_code not in (200, 202):
        log.warning("send_interactive_list http %s: %s", r.status_code, r.text[:200])
        return None
    try:
        return r.json().get("messageId")
    except Exception:
        return None


async def edit_or_send_interactive(
    *, to: str, existing_msg_id: Optional[str],
    body: str,
    buttons: Sequence[Tuple[str, str]],
) -> Optional[str]:
    """Try to edit `existing_msg_id` in place; on any failure, send a
    fresh interactive. Returns the resulting msg_id (the original one
    if edit succeeded, the new one if we sent fresh).

    Gupshup's /msg/edit endpoint may not be supported on every
    account/tier. We treat any non-200 or exception as "edit unavailable"
    and fall through gracefully — worst case the chat shows a new
    progress message instead of an in-place update.
    """
    if existing_msg_id:
        msg = _build_interactive_button_message(body, buttons)
        edit_payload = {
            **_base_payload(to),
            "messageId": existing_msg_id,
            "message": json.dumps(msg),
        }
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post(f"{GUPSHUP_BASE}/msg/edit", data=edit_payload, headers=_headers())
            if r.status_code in (200, 202):
                return existing_msg_id
            log.info("interactive edit returned %s, falling back to fresh send", r.status_code)
        except Exception as e:
            log.info("interactive edit raised (%r), falling back to fresh send", e)
    return await send_interactive_buttons(to=to, body=body, buttons=buttons)
