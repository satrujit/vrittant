"""Classify a Gupshup inbound payload into one of a small set of kinds.

The dispatcher uses the result to delegate to the right handler. Keeping
classification pure-functional + payload-shaped makes the dispatcher
trivially testable.

Note on QUOTED_REPLY: any inbound message (text OR media) whose payload
includes a `context.id` is treated as a reply to one of our outbound
messages. That `context.id` is the message_id of OUR earlier outbound,
which the add-to-story handler looks up against
stories.whatsapp_confirm_message_id.
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


def classify(payload: dict) -> MessageKind:
    """Pure function. `payload` is the inner message dict from Gupshup,
    not the outer envelope. Caller must extract the inner payload before
    calling.

    Order matters: BUTTON before QUOTED_REPLY (an interactive reply
    technically has a context, but we want to dispatch it as a button).
    QUOTED_REPLY before FORWARD (a quoted text/image is not a fresh
    forward — it's an add-to-story).
    """
    t = payload.get("type")
    if t == "interactive":
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
