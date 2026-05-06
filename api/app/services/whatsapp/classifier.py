"""Classify a Gupshup inbound payload into one of a small set of kinds.

The dispatcher uses the result to delegate to the right handler. Keeping
classification pure-functional + payload-shaped makes the dispatcher
trivially testable.

Gupshup partner API shapes (different from WhatsApp Cloud API native):
- Button tap from a `quick_reply` we sent: `type` is one of
  `button_reply`, `quick_reply`, `button` (the field name varies by
  Gupshup tier and we accept all three).
- List row tap: `type` is `list_reply` (sometimes also delivered as a
  text whose body matches the row's `postbackText`).
- Text / media forwards: `type` is `text` / `image` / etc., with content
  under `payload.payload` (see _extract_content() in the legacy router).

Defensive fallback: an inbound text whose body is exactly one of our
known button IDs (or matches an `add_to_<uuid>` prefix) is treated as a
button tap. Some Gupshup tiers deliver button taps as plain text
messages whose body equals the postbackText we configured, instead of
the typed `button_reply` shape.
"""
from enum import Enum


class MessageKind(str, Enum):
    BUTTON = "button"             # interactive button reply
    QUOTED_REPLY = "quoted"       # reply to one of our outbound messages
    FORWARD = "forward"           # text / image / document / audio / video
    SKIP_STICKER = "sticker"
    SKIP_LOCATION = "location"
    SKIP_CONTACT = "contact"
    SKIP_OTHER = "skip_other"


_FORWARD_TYPES = frozenset({"text", "image", "document", "audio", "video"})

# Gupshup-native interactive types we recognise.
_BUTTON_TYPES = frozenset({
    "interactive",       # WhatsApp Cloud API native (just in case)
    "button_reply",      # Gupshup variant 1
    "list_reply",        # Gupshup list-row tap
    "quick_reply",       # Gupshup variant 2
    "button",            # Gupshup variant 3 (some tiers)
})

# Known button ids — used to recognise a text-shaped button tap.
KNOWN_BUTTON_IDS = frozenset({
    "submit_thread", "cancel_thread",
    "today_list", "open_menu",
    "save_additions", "discard_additions",
    "today", "help", "just_forward",  # menu rows
})
KNOWN_BUTTON_PREFIXES = ("add_to_",)


def _looks_like_button_text(body: str) -> bool:
    body = (body or "").strip()
    if not body:
        return False
    if body in KNOWN_BUTTON_IDS:
        return True
    return any(body.startswith(p) for p in KNOWN_BUTTON_PREFIXES)


def classify(payload: dict) -> MessageKind:
    """Pure function. `payload` is the Gupshup inner message dict
    (`outer["payload"]`), not the outer webhook envelope.

    Order matters: BUTTON before QUOTED_REPLY (an interactive reply
    technically has a context, but we want to dispatch it as a button).
    QUOTED_REPLY before FORWARD (a quoted text/image is not a fresh
    forward — it's an add-to-story).
    """
    t = payload.get("type")
    if t in _BUTTON_TYPES:
        return MessageKind.BUTTON
    # Defensive: some Gupshup tiers send button taps as plain text whose
    # body == the postbackText we configured.
    if t == "text":
        body = (payload.get("payload") or {}).get("text") or ""
        if _looks_like_button_text(body):
            return MessageKind.BUTTON
    if payload.get("context"):
        return MessageKind.QUOTED_REPLY
    if t in _FORWARD_TYPES:
        return MessageKind.FORWARD
    if t == "sticker":
        return MessageKind.SKIP_STICKER
    if t == "location":
        return MessageKind.SKIP_LOCATION
    if t == "contacts":
        return MessageKind.SKIP_CONTACT
    return MessageKind.SKIP_OTHER
