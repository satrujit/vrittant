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
from app.models.whatsapp_buffer import WhatsAppThreadState
from app.services.whatsapp import (
    outbound, i18n, dedup, buffer, thread_state, ingest, finalize,
)
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
    """Route a button-reply payload to the right action."""
    from app.models.story import Story

    lang = i18n.resolve_lang(user)
    button_id = (
        payload.get("interactive", {})
        .get("button_reply", {})
        .get("id", "")
    )

    # cancel_thread — drop everything
    if button_id == "cancel_thread":
        thread_state.close(db, sender_phone)
        buffer.drain_for_sender(db, sender_phone, story_id=None)
        db.commit()
        await outbound.send_text(to=sender_phone, body=i18n.t("err.cancelled", lang))
        return

    # submit_thread — finalize a story (or append to existing if add-mode)
    if button_id == "submit_thread":
        if user is None:
            return
        ts_pre = (
            db.query(WhatsAppThreadState)
            .filter_by(sender_phone=sender_phone)
            .first()
        )
        if ts_pre is not None and ts_pre.thread_kind == "add":
            story = await finalize.append_to_story(
                db=db, sender_phone=sender_phone, user=user,
            )
        else:
            story = await finalize.finalize_story_from_thread(
                db=db, sender_phone=sender_phone, user=user,
            )
        if story is None:
            await outbound.send_text(to=sender_phone, body=i18n.t("err.empty", lang))
            return
        db.commit()
        display_id = getattr(story, "display_id", None) or story.id
        body = (
            i18n.t("saved.header", lang)
            + "\n"
            + i18n.t("saved.id", lang, display_id=display_id)
            + "\n"
            + (story.headline or "")[:80]
        )
        msg_id = await outbound.send_interactive_buttons(
            to=sender_phone, body=body,
            buttons=[
                (f"add_to_{story.id}", i18n.t("btn.add", lang)),
                ("today_list", i18n.t("btn.today", lang)),
                ("open_menu", i18n.t("btn.openApp", lang)),
            ],
        )
        if msg_id:
            story.whatsapp_confirm_message_id = msg_id
            db.commit()
        return

    # add_to_<story_id> — open an "add" thread targeting that story
    if button_id.startswith("add_to_"):
        story_id = button_id[len("add_to_"):]
        story = db.query(Story).filter_by(id=story_id).first()
        if story is None or (user and story.reporter_id != user.id):
            await outbound.send_text(to=sender_phone, body=i18n.t("err.crossReporter", lang))
            return
        if story.status not in ("submitted", "flagged"):
            await outbound.send_text(
                to=sender_phone,
                body=i18n.t(
                    "err.locked", lang,
                    display_id=getattr(story, "display_id", None) or story.id,
                ),
            )
            return
        # Reset / open an add-mode thread
        thread_state.close(db, sender_phone)
        thread_state.open_or_get(
            db, sender_phone, thread_kind="add", target_story_id=story_id,
        )
        db.commit()
        await outbound.send_text(
            to=sender_phone,
            body=i18n.t(
                "adding.header", lang,
                display_id=getattr(story, "display_id", None) or story.id,
            ),
        )
        return

    # today_list — Task 15 ships the real handler. For now route minimally.
    if button_id == "today_list":
        try:
            from app.services.whatsapp import today as today_mod  # type: ignore
            await today_mod.handle_today(db=db, sender_phone=sender_phone, user=user)
        except (ImportError, AttributeError):
            await outbound.send_text(
                to=sender_phone,
                body=i18n.t("today.empty", lang),
            )
        return

    # open_menu — render the menu list message
    if button_id == "open_menu":
        await outbound.send_interactive_list(
            to=sender_phone,
            body=i18n.t("menu.prompt", lang),
            button_label=i18n.t("btn.menu", lang),
            sections=[
                ("Submit", [("just_forward", "Just forward your message", None)]),
                ("View",   [("today",        "My stories filed today",     None)]),
                ("Help",   [("help",         "How to use Vrittant on WhatsApp", None)]),
            ],
        )
        return

    # Unknown button id — silent


async def handle_quoted_reply(*, db, sender_phone, user, payload):
    """Reporter long-pressed our saved-confirmation and replied with
    new content → append to that story (after permission checks).

    Falls through to handle_forward when:
    - context.id doesn't match any story (treat as fresh forward)
    - story is locked (reply with err.locked, then process as fresh)

    Replies with err.crossReporter when the matched story belongs to a
    different reporter — does NOT fall through (would create a story
    impersonating someone else's, even though our content is theirs).
    """
    lang = i18n.resolve_lang(user)

    # Unregistered → polite decline (same as forward path)
    if user is None:
        await outbound.send_text(
            to=sender_phone, body=i18n.t("err.unregistered", lang),
        )
        return

    context_id = (payload.get("context") or {}).get("id")

    target = None
    if context_id:
        from app.models.story import Story
        target = (
            db.query(Story)
            .filter(Story.whatsapp_confirm_message_id == context_id)
            .first()
        )

    # No matching story → process as fresh forward, ignoring the quote
    if target is None:
        # Strip the context key so the forward handler doesn't re-trigger
        # quoted-reply classification (defensive — classifier already
        # routed us here based on this key).
        clean_payload = {k: v for k, v in payload.items() if k != "context"}
        await handle_forward(
            db=db, sender_phone=sender_phone, user=user, payload=clean_payload,
        )
        return

    # Cross-reporter — reject without processing content
    if target.reporter_id != user.id:
        await outbound.send_text(to=sender_phone, body=i18n.t("err.crossReporter", lang))
        return

    # Locked story — inform AND fall through as fresh forward
    if target.status not in ("submitted", "flagged"):
        display_id = getattr(target, "display_id", None) or target.id
        await outbound.send_text(
            to=sender_phone, body=i18n.t("err.locked", lang, display_id=display_id),
        )
        clean_payload = {k: v for k, v in payload.items() if k != "context"}
        await handle_forward(
            db=db, sender_phone=sender_phone, user=user, payload=clean_payload,
        )
        return

    # Open / refresh an add-mode thread targeting this story
    thread_state.close(db, sender_phone)
    thread_state.open_or_get(
        db, sender_phone, thread_kind="add", target_story_id=target.id,
    )
    db.commit()

    # Now process the inbound content via the forward path. The thread
    # we just opened (kind='add') means handle_button(submit_thread) will
    # call append_to_story instead of finalize_story_from_thread.
    clean_payload = {k: v for k, v in payload.items() if k != "context"}
    await handle_forward(
        db=db, sender_phone=sender_phone, user=user, payload=clean_payload,
    )


async def handle_forward(*, db, sender_phone, user, payload):
    """Handle an inbound text/media forward.

    Owns: buffer the media, accumulate text, send/edit the [Submit]
    [Cancel] interactive message. Does NOT create stories — that's
    handle_button(submit_thread)'s job.
    """
    lang = i18n.resolve_lang(user)

    # 1. Unregistered phone → polite decline
    if user is None:
        await outbound.send_text(to=sender_phone, body=i18n.t("err.unregistered", lang))
        return

    # 2. Auto-close stale thread (60s idle) so unrelated forward groups
    #    from the same reporter don't false-merge.
    if thread_state.is_idle(db, sender_phone, idle_seconds=60):
        prior = db.query(WhatsAppThreadState).filter_by(sender_phone=sender_phone).first()
        if prior is not None and (prior.pending_text_count or prior.pending_media_count):
            thread_state.close(db, sender_phone)
            db.commit()

    inner_type = payload.get("type")

    # 3. Text branch
    if inner_type == "text":
        raw = payload.get("text", {}).get("body", "") or ""
        cleaned = ingest.strip_forward_boilerplate(raw)
        if ingest.word_count(cleaned) < 20:
            await outbound.send_text(to=sender_phone, body=i18n.t("err.tooShort", lang))
            return
        h = dedup.hash_text(cleaned)
        if dedup.is_duplicate(db, sender_phone, h):
            return  # silent skip
        dedup.mark_seen(db, sender_phone, h)
        thread_state.increment_text(db, sender_phone, cleaned)

    # 4. Media branch
    elif inner_type in ("image", "document", "audio", "video"):
        media_subdict = payload.get(inner_type) or {}
        media_url = media_subdict.get("url") or media_subdict.get("id") or ""
        if not media_url:
            return  # malformed payload — silent
        h = dedup.hash_text(media_url)  # SHA256 of URL as content_hash placeholder
        if dedup.is_duplicate(db, sender_phone, h):
            return
        dedup.mark_seen(db, sender_phone, h)
        caption = media_subdict.get("caption")
        buffer.add_to_buffer(
            db, sender_phone=sender_phone, media_type=inner_type,
            gupshup_url=media_url, content_hash=h, caption=caption,
        )
        thread_state.increment_media(db, sender_phone)
    else:
        return  # not a forward we handle here

    # 5. Send / edit the [Submit][Cancel] interactive
    ts = thread_state.open_or_get(db, sender_phone)
    total = (ts.pending_text_count or 0) + (ts.pending_media_count or 0)
    if total <= 1:
        body = i18n.t("thread.first", lang)
    else:
        body = i18n.t(
            "thread.update", lang,
            count=total,
            text=ts.pending_text_count,
            media=ts.pending_media_count,
        )
    new_msg_id = await outbound.edit_or_send_interactive(
        to=sender_phone,
        existing_msg_id=ts.interactive_msg_id,
        body=body,
        buttons=[
            ("submit_thread", i18n.t("btn.submit", lang)),
            ("cancel_thread", i18n.t("btn.cancel", lang)),
        ],
    )
    if new_msg_id:
        ts.interactive_msg_id = new_msg_id
    db.commit()


async def handle_skip(*, db, sender_phone, user, kind):
    """Polite decline for sticker / location / contact; silent for
    everything else. We don't open a thread or buffer anything — these
    are dead-end message types as far as story creation goes.
    """
    if kind == MessageKind.SKIP_OTHER:
        return  # silent — unknown types shouldn't talk back
    lang = i18n.resolve_lang(user)
    await outbound.send_text(to=sender_phone, body=i18n.t("err.sticker", lang))
