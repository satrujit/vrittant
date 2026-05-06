"""Single entry point for WhatsApp inbound webhooks (new self-service path).

Classifies the payload, then delegates to a handler. Each handler is
responsible for its own outbound replies, buffer writes, and dedup.

Handlers are stubs in this commit (raise NotImplementedError) — they
get filled in by Tasks 12-16. The dispatcher wiring is feature-flagged
in webhooks_whatsapp.py so the legacy path remains fully functional
until every handler ships and the flag is flipped.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.whatsapp import outbound, i18n
from app.services.whatsapp.classifier import classify, MessageKind


def resolve_user_for_phone(db: Session, sender_phone: str) -> Optional[User]:
    """Look up the active reporter by phone. Returns None if no match
    (unregistered) or if the matching reporter is deactivated.

    Phone is matched as-is — the caller is responsible for normalising
    via the same `_normalize_phone` helper the legacy code uses.
    """
    return (
        db.query(User)
        .filter(
            User.phone == sender_phone,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
        .first()
    )


async def dispatch(
    *,
    db: Session,
    sender_phone: str,
    user: Optional[User],
    payload: dict,
) -> None:
    """Route an inbound payload to its handler.

    `user` may be None — the forward handler is responsible for the
    polite "not registered" reply when that's the case. Other handler
    kinds (button / quoted / skip) generally require a known user but
    handle the None case defensively.
    """
    kind = classify(payload)
    if kind == MessageKind.BUTTON:
        await handle_button(db=db, sender_phone=sender_phone, user=user, payload=payload)
    elif kind == MessageKind.QUOTED_REPLY:
        await handle_quoted_reply(db=db, sender_phone=sender_phone, user=user, payload=payload)
    elif kind == MessageKind.FORWARD:
        await handle_forward(db=db, sender_phone=sender_phone, user=user, payload=payload)
    else:
        await handle_skip(db=db, sender_phone=sender_phone, user=user, kind=kind)


# ── Handler stubs ───────────────────────────────────────────────
# Replaced by real implementations in Tasks 13-16. Until those land, an
# inbound webhook arriving while WHATSAPP_SELF_SERVICE_ENABLED=true would
# raise NotImplementedError → the retry middleware catches it via the
# generic 503 path → Gupshup retries → eventually gives up. So leaving
# the flag OFF until handlers are filled is non-negotiable.


async def handle_button(*, db, sender_phone, user, payload):
    raise NotImplementedError("handle_button — implemented in Task 14")


async def handle_quoted_reply(*, db, sender_phone, user, payload):
    raise NotImplementedError("handle_quoted_reply — implemented in Task 16")


async def handle_forward(*, db, sender_phone, user, payload):
    raise NotImplementedError("handle_forward — implemented in Task 13")


async def handle_skip(*, db, sender_phone, user, kind):
    """Polite decline for sticker / location / contact; silent for
    everything else. We don't open a thread or buffer anything — these
    are dead-end message types as far as story creation goes.
    """
    if kind == MessageKind.SKIP_OTHER:
        return  # silent — unknown types shouldn't talk back
    lang = i18n.resolve_lang(user)
    await outbound.send_text(to=sender_phone, body=i18n.t("err.sticker", lang))
