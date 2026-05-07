"""Tests for the Gupshup WhatsApp inbound webhook.

Reporters forward government press releases to the Vrittant WABA number;
if the sender is a registered active reporter we create a draft story
that routes through pick_assignee to a reviewer (reporters never review
their own submissions). Reviewers/admins forwarding from WhatsApp keep
self-assign — they're working on it themselves. The webhook always
returns 200 (Gupshup retries non-2xx) and replies via the Gupshup HTTP
API.
"""
import pytest

from app.models.story import Story
from app.models.user import User


@pytest.fixture()
def gupshup_reporter(db):
    user = User(
        id="reporter-wa-1",
        name="WA Reporter",
        phone="+919876543210",
        user_type="reporter",
        organization="Test Org",
        organization_id="org-test",
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture()
def no_send(monkeypatch):
    """Stub the outbound Gupshup reply so tests stay offline."""
    sent: list[tuple[str, str]] = []

    async def fake_send(to_phone: str, text: str) -> None:
        sent.append((to_phone, text))

    from app.routers import webhooks_whatsapp

    monkeypatch.setattr(webhooks_whatsapp, "_send_gupshup_reply", fake_send)
    return sent


@pytest.fixture()
def fake_persist(monkeypatch):
    """Stub media download/upload — record the URL it was asked to persist
    and return a fake GCS URL so the test can assert what got stored."""
    persisted: list[str] = []

    async def fake(url: str, content_type: str | None = None, original_name: str | None = None):
        persisted.append(url)
        stored = f"https://storage.googleapis.com/test-bucket/whatsapp/fake-{len(persisted)}.bin"
        # _persist_media returns (stored_url, body, content_type, image_variants).
        # body is only consumed for docx text extraction; image_variants
        # is non-None only for image uploads (web + thumbnail variants).
        return (stored, None, content_type, None)

    from app.routers import webhooks_whatsapp

    monkeypatch.setattr(webhooks_whatsapp, "_persist_media", fake)
    return persisted


def _text_payload(sender: str, msg_id: str, text: str) -> dict:
    return {
        "app": "Vrittant",
        "type": "message",
        "payload": {
            "id": msg_id,
            "source": sender,
            "type": "text",
            "payload": {"text": text},
            "sender": {"phone": sender, "name": "WA Reporter"},
        },
    }


def test_inbound_text_from_registered_reporter_creates_story(client, db, gupshup_reporter, no_send):
    body = _text_payload("919876543210", "wamid.001", "Press release: New highway opened in Cuttack.")
    r = client.post("/webhooks/whatsapp/gupshup", json=body)
    assert r.status_code == 200

    stories = db.query(Story).filter_by(reporter_id=gupshup_reporter.id).all()
    assert len(stories) == 1
    s = stories[0]
    assert s.source == "whatsapp"
    assert s.status == "submitted"
    # Reporter-sourced WA stories must NOT self-assign back to the
    # reporter — they go through the reviewer queue. With no reviewers
    # in this fixture org, pick_assignee raises NoReviewersAvailable and
    # the story is left unassigned for an admin to triage.
    assert s.assigned_to is None
    assert s.organization_id == gupshup_reporter.organization_id
    assert "highway" in (s.headline + " ".join(p.get("text", "") for p in (s.paragraphs or []) if isinstance(p, dict))).lower()
    # Confirmation reply was sent to the same phone
    assert len(no_send) == 1
    assert no_send[0][0] == "919876543210"


def test_inbound_text_from_reporter_routes_to_reviewer_when_present(client, db, gupshup_reporter, no_send):
    """When a reviewer exists in the org, pick_assignee should route to them."""
    reviewer = User(
        id="reviewer-wa-1",
        name="Org Reviewer",
        phone="+919000000001",
        user_type="reviewer",
        organization="Test Org",
        organization_id=gupshup_reporter.organization_id,
        is_active=True,
    )
    db.add(reviewer)
    db.commit()

    body = _text_payload("919876543210", "wamid.route1", "Routing test story body.")
    r = client.post("/webhooks/whatsapp/gupshup", json=body)
    assert r.status_code == 200

    s = db.query(Story).filter_by(reporter_id=gupshup_reporter.id).one()
    assert s.assigned_to == reviewer.id
    assert s.assigned_match_reason is not None  # set by pick_assignee


def test_inbound_text_from_reviewer_self_assigns(client, db, no_send):
    """Reviewers/admins forwarding from WA are working on it — keep self-assign."""
    reviewer = User(
        id="reviewer-self-1",
        name="Self Reviewer",
        phone="+919876500000",
        user_type="reviewer",
        organization="Test Org",
        organization_id="org-test",
        is_active=True,
    )
    db.add(reviewer)
    db.commit()

    body = _text_payload("919876500000", "wamid.self1", "I'm working on this story myself.")
    r = client.post("/webhooks/whatsapp/gupshup", json=body)
    assert r.status_code == 200

    s = db.query(Story).filter_by(reporter_id=reviewer.id).one()
    assert s.assigned_to == reviewer.id
    assert s.assigned_match_reason == "manual"


def test_inbound_from_unregistered_phone_does_not_create_story(client, db, no_send):
    body = _text_payload("919999999999", "wamid.002", "test")
    r = client.post("/webhooks/whatsapp/gupshup", json=body)
    assert r.status_code == 200
    assert db.query(Story).count() == 0
    # Politely tell them they're not registered
    assert len(no_send) == 1
    assert "not registered" in no_send[0][1].lower()


def test_inbound_dedup_same_message_id_only_creates_one_story(client, db, gupshup_reporter, no_send):
    body = _text_payload("919876543210", "wamid.dup", "first delivery")
    r1 = client.post("/webhooks/whatsapp/gupshup", json=body)
    r2 = client.post("/webhooks/whatsapp/gupshup", json=body)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert db.query(Story).filter_by(reporter_id=gupshup_reporter.id).count() == 1
    # Second hit shouldn't have triggered another reply either
    assert len(no_send) == 1


def test_non_message_event_type_is_ignored(client, db, gupshup_reporter, no_send):
    body = {"app": "Vrittant", "type": "message-event", "payload": {"type": "delivered"}}
    r = client.post("/webhooks/whatsapp/gupshup", json=body)
    assert r.status_code == 200
    assert db.query(Story).count() == 0
    assert len(no_send) == 0


def test_inactive_user_treated_as_unregistered(client, db, gupshup_reporter, no_send):
    gupshup_reporter.is_active = False
    db.commit()
    body = _text_payload("919876543210", "wamid.003", "anything")
    r = client.post("/webhooks/whatsapp/gupshup", json=body)
    assert r.status_code == 200
    assert db.query(Story).count() == 0


def test_image_message_persists_media_to_gcs(client, db, gupshup_reporter, no_send, fake_persist):
    """Image messages should be downloaded from Gupshup and re-hosted on our
    own storage — Gupshup media URLs expire, and we want the photo, not a
    soon-dead link."""
    body = {
        "app": "Vrittant",
        "type": "message",
        "payload": {
            "id": "wamid.img",
            "source": "919876543210",
            "type": "image",
            "payload": {
                "url": "https://gupshup-media.example/abc.jpg",
                "caption": "Govt press conference photo",
                "contentType": "image/jpeg",
            },
            "sender": {"phone": "919876543210", "name": "WA Reporter"},
        },
    }
    r = client.post("/webhooks/whatsapp/gupshup", json=body)
    assert r.status_code == 200

    # The original Gupshup URL was handed to _persist_media…
    assert fake_persist == ["https://gupshup-media.example/abc.jpg"]

    stories = db.query(Story).filter_by(reporter_id=gupshup_reporter.id).all()
    assert len(stories) == 1
    paragraphs = stories[0].paragraphs or []
    media_paras = [p for p in paragraphs if isinstance(p, dict) and p.get("media_path")]
    assert media_paras, "expected a paragraph carrying media_path"
    # …and the stored media_path is OUR GCS URL, not Gupshup's transient one
    assert media_paras[0]["media_path"].startswith("https://storage.googleapis.com/")
    assert "gupshup-media.example" not in media_paras[0]["media_path"]
    # Caption is still preserved
    flat_text = " ".join(p.get("text", "") for p in paragraphs if isinstance(p, dict))
    assert "press conference" in (stories[0].headline + flat_text).lower()


def test_image_message_falls_back_to_link_if_persist_fails(client, db, gupshup_reporter, no_send, monkeypatch):
    """If we can't fetch/upload the media (network blip, expired URL, etc.)
    we still want the story created — fall back to recording the Gupshup URL
    so the reporter doesn't have to resend."""
    async def failing_persist(url, content_type=None, original_name=None):
        return (None, None, None, None)

    from app.routers import webhooks_whatsapp
    monkeypatch.setattr(webhooks_whatsapp, "_persist_media", failing_persist)

    body = {
        "app": "Vrittant",
        "type": "message",
        "payload": {
            "id": "wamid.img-fail",
            "source": "919876543210",
            "type": "image",
            "payload": {
                "url": "https://gupshup-media.example/fail.jpg",
                "caption": "lost",
                "contentType": "image/jpeg",
            },
            "sender": {"phone": "919876543210", "name": "WA Reporter"},
        },
    }
    r = client.post("/webhooks/whatsapp/gupshup", json=body)
    assert r.status_code == 200
    stories = db.query(Story).filter_by(reporter_id=gupshup_reporter.id).all()
    assert len(stories) == 1
    paragraphs = stories[0].paragraphs or []
    media_paras = [p for p in paragraphs if isinstance(p, dict) and p.get("media_path")]
    assert media_paras and media_paras[0]["media_path"] == "https://gupshup-media.example/fail.jpg"


def test_missing_message_id_is_ignored_safely(client, db, gupshup_reporter, no_send):
    body = {
        "app": "Vrittant",
        "type": "message",
        "payload": {
            "source": "919876543210",
            "type": "text",
            "payload": {"text": "no id"},
            "sender": {"phone": "919876543210"},
        },
    }
    r = client.post("/webhooks/whatsapp/gupshup", json=body)
    assert r.status_code == 200
    assert db.query(Story).count() == 0


from datetime import timedelta
from app.utils.tz import now_ist


def _close_payload(sender, msg_id, word):
    return _text_payload(sender, msg_id, word)


def test_two_messages_within_window_stitch_into_one_story(
    client, db, gupshup_reporter, no_send, monkeypatch
):
    from app.routers import webhooks_whatsapp
    async def news(_): return "news"
    monkeypatch.setattr(webhooks_whatsapp.classifier, "classify", news)

    client.post("/webhooks/whatsapp/gupshup",
        json=_text_payload("919876543210", "wamid.s1", "Cuttack police seized ganja."))
    client.post("/webhooks/whatsapp/gupshup",
        json=_text_payload("919876543210", "wamid.s2", "Three arrests made."))

    stories = db.query(Story).filter_by(reporter_id=gupshup_reporter.id).all()
    assert len(stories) == 1
    paras = stories[0].paragraphs or []
    texts = " ".join(p.get("text", "") for p in paras if isinstance(p, dict))
    assert "ganja" in texts and "arrests" in texts
    # Only one reply (on the first message)
    assert len(no_send) == 1


def test_message_after_window_starts_new_story(
    client, db, gupshup_reporter, no_send, monkeypatch
):
    from app.routers import webhooks_whatsapp
    async def news(_): return "news"
    monkeypatch.setattr(webhooks_whatsapp.classifier, "classify", news)

    client.post("/webhooks/whatsapp/gupshup",
        json=_text_payload("919876543210", "wamid.w1", "Story one."))
    s = db.query(Story).filter_by(reporter_id=gupshup_reporter.id).one()
    s.whatsapp_session_open_until = now_ist() - timedelta(minutes=1)
    db.commit()
    client.post("/webhooks/whatsapp/gupshup",
        json=_text_payload("919876543210", "wamid.w2", "Story two unrelated."))

    stories = db.query(Story).filter_by(reporter_id=gupshup_reporter.id).order_by(Story.created_at).all()
    assert len(stories) == 2


def test_done_keyword_seals_open_draft(client, db, gupshup_reporter, no_send, monkeypatch):
    from app.routers import webhooks_whatsapp
    async def news(_): return "news"
    monkeypatch.setattr(webhooks_whatsapp.classifier, "classify", news)

    client.post("/webhooks/whatsapp/gupshup",
        json=_text_payload("919876543210", "wamid.d1", "Story body."))
    client.post("/webhooks/whatsapp/gupshup",
        json=_close_payload("919876543210", "wamid.d2", "done"))

    s = db.query(Story).filter_by(reporter_id=gupshup_reporter.id).one()
    assert s.whatsapp_session_open_until is None
    assert any("sealed" in body.lower() for _, body in no_send)


def test_done_with_no_open_story_replies_politely(client, db, gupshup_reporter, no_send, monkeypatch):
    from app.routers import webhooks_whatsapp
    async def news(_): return "news"
    monkeypatch.setattr(webhooks_whatsapp.classifier, "classify", news)

    client.post("/webhooks/whatsapp/gupshup",
        json=_close_payload("919876543210", "wamid.d3", "done"))
    assert db.query(Story).count() == 0
    assert any("no open story" in body.lower() for _, body in no_send)


def test_chitchat_first_message_does_not_create_story(
    client, db, gupshup_reporter, no_send, monkeypatch
):
    from app.routers import webhooks_whatsapp
    async def chitchat(_): return "chitchat"
    monkeypatch.setattr(webhooks_whatsapp.classifier, "classify", chitchat)

    r = client.post("/webhooks/whatsapp/gupshup",
        json=_text_payload("919876543210", "wamid.cc1", "hi are you there"))
    assert r.status_code == 200
    assert db.query(Story).count() == 0
    assert any("forward press releases" in body.lower() or "news" in body.lower() for _, body in no_send)


def test_unclear_first_message_creates_story_with_triage_flag(
    client, db, gupshup_reporter, no_send, monkeypatch
):
    from app.routers import webhooks_whatsapp
    async def unclear(_): return "unclear"
    monkeypatch.setattr(webhooks_whatsapp.classifier, "classify", unclear)

    client.post("/webhooks/whatsapp/gupshup",
        json=_text_payload("919876543210", "wamid.u1", "ambiguous text"))
    s = db.query(Story).filter_by(reporter_id=gupshup_reporter.id).one()
    assert s.needs_triage is True


def test_photo_only_first_message_buffers_and_prompts(
    client, db, gupshup_reporter, no_send, fake_persist, monkeypatch
):
    """A photo without a caption is BUFFERED (not turned into a placeholder
    story) and the reporter receives ONE polite Odia prompt asking them to
    add a caption or send text. Subsequent photos in the same session add
    to the buffer silently — no prompt spam.

    When the reporter sends text within the session, the buffered photos
    are auto-stitched into the new story (covered by a separate test).
    """
    from app.routers import webhooks_whatsapp
    from app.models.whatsapp_buffer import WhatsAppPendingMedia

    called = []
    async def boom(_):
        called.append(True)
        return "chitchat"
    monkeypatch.setattr(webhooks_whatsapp.classifier, "classify", boom)

    body = {
        "app": "Vrittant", "type": "message",
        "payload": {
            "id": "wamid.p1", "source": "919876543210", "type": "image",
            "payload": {"url": "https://gupshup-media.example/x.jpg",
                        "contentType": "image/jpeg"},
            "sender": {"phone": "919876543210"},
        },
    }
    r = client.post("/webhooks/whatsapp/gupshup", json=body)
    assert r.status_code == 200
    assert r.json().get("buffered") == "pending-media"
    assert called == []  # classifier never invoked
    assert db.query(Story).count() == 0  # no story created
    assert db.query(WhatsAppPendingMedia).count() == 1  # photo buffered


def test_photo_burst_prompts_only_once(
    client, db, gupshup_reporter, no_send, fake_persist
):
    """5 photos in a row should produce 1 prompt + 5 buffer rows."""
    from app.models.whatsapp_buffer import WhatsAppPendingMedia
    for i in range(5):
        body = {
            "app": "Vrittant", "type": "message",
            "payload": {
                "id": f"wamid.b{i}", "source": "919876543210", "type": "image",
                "payload": {"url": f"https://gupshup-media.example/p{i}.jpg",
                            "contentType": "image/jpeg"},
                "sender": {"phone": "919876543210"},
            },
        }
        r = client.post("/webhooks/whatsapp/gupshup", json=body)
        assert r.status_code == 200
        assert r.json().get("buffered") == "pending-media"

    assert db.query(Story).count() == 0
    assert db.query(WhatsAppPendingMedia).filter_by(drained_at=None).count() == 5
    # Reply count = 1 (only the first photo triggered _send_gupshup_reply)
    assert len(no_send) == 1


def test_text_after_buffered_photos_drains_into_new_story(
    client, db, gupshup_reporter, no_send, fake_persist, monkeypatch
):
    """Photos buffered first, text arrives within session — text becomes
    the story headline/body and all buffered photos auto-attach as media
    paragraphs. The reporter's intuition of "send photos then explain"
    just works."""
    from app.routers import webhooks_whatsapp
    from app.models.whatsapp_buffer import WhatsAppPendingMedia

    async def cls(_): return "news"
    monkeypatch.setattr(webhooks_whatsapp.classifier, "classify", cls)
    async def cat(_t, _k): return None
    monkeypatch.setattr(webhooks_whatsapp, "classify_category", cat)

    # Three photos arrive first
    for i in range(3):
        client.post("/webhooks/whatsapp/gupshup", json={
            "app": "Vrittant", "type": "message",
            "payload": {
                "id": f"wamid.t{i}", "source": "919876543210", "type": "image",
                "payload": {"url": f"https://gupshup-media.example/q{i}.jpg",
                            "contentType": "image/jpeg"},
                "sender": {"phone": "919876543210"},
            },
        })
    assert db.query(WhatsAppPendingMedia).filter_by(drained_at=None).count() == 3

    # Then the text arrives
    r = client.post("/webhooks/whatsapp/gupshup", json={
        "app": "Vrittant", "type": "message",
        "payload": {
            "id": "wamid.t-text", "source": "919876543210", "type": "text",
            "payload": {"text": "Inauguration ceremony at the Pragativadi office."},
            "sender": {"phone": "919876543210"},
        },
    })
    assert r.status_code == 200

    stories = db.query(Story).all()
    assert len(stories) == 1
    s = stories[0]
    # Headline = first line of the text
    assert "Inauguration" in (s.headline or "")
    # Paragraphs = text + 3 media (drained from buffer)
    assert len(s.paragraphs) == 4
    media_paragraphs = [p for p in s.paragraphs if p.get("media_path")]
    assert len(media_paragraphs) == 3
    # Buffer rows now linked back to this story
    drained = db.query(WhatsAppPendingMedia).filter_by(drained_into_story_id=s.id).all()
    assert len(drained) == 3


# ── Integration tests for the dispatcher (self-service flag ON) ──


@pytest.fixture()
def self_service_on(monkeypatch):
    """Flip WHATSAPP_SELF_SERVICE_ENABLED=true for the duration of one test."""
    from app.config import settings
    monkeypatch.setattr(settings, "WHATSAPP_SELF_SERVICE_ENABLED", True)


def test_router_invokes_dispatcher_when_flag_on(
    client, db, gupshup_reporter, no_send, self_service_on, monkeypatch
):
    """With the flag on, the router routes inbound to the new dispatcher
    (not the legacy ingest). Verifies the routing handoff that was
    previously only unit-tested in services."""
    from app.routers import webhooks_whatsapp
    from app.services.whatsapp import dispatcher as new_dispatcher

    calls = []

    async def fake_dispatch(*, db, sender_phone, user, payload):
        calls.append({"sender": sender_phone, "user_id": getattr(user, "id", None),
                      "payload_type": payload.get("type")})

    monkeypatch.setattr(new_dispatcher, "dispatch", fake_dispatch)

    body = {
        "app": "Vrittant", "type": "message",
        "payload": {
            "id": "wamid.disp1", "source": "919876543210", "type": "text",
            "payload": {"text": "Hello there"},
            "sender": {"phone": "919876543210"},
        },
    }
    r = client.post("/webhooks/whatsapp/gupshup", json=body)
    assert r.status_code == 200
    assert len(calls) == 1
    assert calls[0]["sender"] == "+919876543210"
    assert calls[0]["user_id"] == gupshup_reporter.id
    assert calls[0]["payload_type"] == "text"


def test_dedup_committed_when_dispatch_succeeds(
    client, db, gupshup_reporter, no_send, self_service_on, monkeypatch
):
    """After a successful dispatch the dedup row exists, so a retry of
    the same message_id from Gupshup is a no-op."""
    from app.models.webhook_dedup import WhatsappInboundDedup
    from app.services.whatsapp import dispatcher as new_dispatcher

    async def ok_dispatch(**_): return None  # no-op
    monkeypatch.setattr(new_dispatcher, "dispatch", ok_dispatch)

    body = {
        "app": "Vrittant", "type": "message",
        "payload": {
            "id": "wamid.dedup-ok", "source": "919876543210", "type": "text",
            "payload": {"text": "Hello"}, "sender": {"phone": "919876543210"},
        },
    }
    r = client.post("/webhooks/whatsapp/gupshup", json=body)
    assert r.status_code == 200

    # Dedup row exists
    assert db.query(WhatsappInboundDedup).filter_by(message_id="wamid.dedup-ok").first() is not None

    # Replay returns "duplicate" without invoking dispatcher
    calls = []
    async def replay_dispatch(**kwargs):
        calls.append(kwargs)
    monkeypatch.setattr(new_dispatcher, "dispatch", replay_dispatch)
    r2 = client.post("/webhooks/whatsapp/gupshup", json=body)
    assert r2.status_code == 200
    assert r2.json().get("skipped") == "duplicate"
    assert calls == []  # dispatcher NOT called on replay


def test_dedup_rolled_back_when_dispatch_raises(
    client, db, gupshup_reporter, no_send, self_service_on, monkeypatch
):
    """If the handler raises before committing, the dedup row must roll
    back too — otherwise a Gupshup retry sees the message as already
    processed and the reporter's content is lost permanently. This is
    the data-loss bug the code review flagged."""
    from app.models.webhook_dedup import WhatsappInboundDedup
    from app.services.whatsapp import dispatcher as new_dispatcher

    async def boom(**_):
        raise RuntimeError("simulated handler failure before commit")
    monkeypatch.setattr(new_dispatcher, "dispatch", boom)

    body = {
        "app": "Vrittant", "type": "message",
        "payload": {
            "id": "wamid.dedup-fail", "source": "919876543210", "type": "text",
            "payload": {"text": "Hello"}, "sender": {"phone": "919876543210"},
        },
    }
    # The router will raise; the test client either propagates it or returns
    # 500 depending on TestClient config. Either way, what matters is the DB.
    try:
        client.post("/webhooks/whatsapp/gupshup", json=body)
    except RuntimeError:
        pass  # expected — bubbled out from the dispatcher

    # Dedup row must NOT have been committed
    assert db.query(WhatsappInboundDedup).filter_by(message_id="wamid.dedup-fail").first() is None


# ── _find_open_draft must filter closed/deleted stories ──


def test_find_open_draft_excludes_approved_story(db, gupshup_reporter):
    """A WhatsApp story in 'approved' status must NOT be treated as
    appendable, even if its session window is still open. Otherwise
    a forward arriving in the same window silently mutates a story
    the editor already signed off on."""
    from datetime import timedelta
    from app.models.story import Story
    from app.routers.webhooks_whatsapp import _find_open_draft
    from app.utils.tz import now_ist

    db.add(Story(
        id="s_approved", organization_id="o_test", reporter_id=gupshup_reporter.id,
        seq_no=1, headline="Already approved", paragraphs=[],
        status="approved",                # closed status
        source="whatsapp",
        whatsapp_session_open_until=now_ist() + timedelta(minutes=5),
    ))
    db.commit()

    assert _find_open_draft(db, gupshup_reporter.id) is None


def test_find_open_draft_excludes_soft_deleted_story(db, gupshup_reporter):
    from datetime import timedelta
    from app.models.story import Story
    from app.routers.webhooks_whatsapp import _find_open_draft
    from app.utils.tz import now_ist

    db.add(Story(
        id="s_deleted", organization_id="o_test", reporter_id=gupshup_reporter.id,
        seq_no=1, headline="Tombstone", paragraphs=[],
        status="submitted", source="whatsapp",
        whatsapp_session_open_until=now_ist() + timedelta(minutes=5),
        deleted_at=now_ist(),
    ))
    db.commit()

    assert _find_open_draft(db, gupshup_reporter.id) is None


def test_find_open_draft_includes_submitted_story(db, gupshup_reporter):
    """Sanity: stories in OPEN statuses with active window ARE returned."""
    from datetime import timedelta
    from app.models.story import Story
    from app.routers.webhooks_whatsapp import _find_open_draft
    from app.utils.tz import now_ist

    db.add(Story(
        id="s_open", organization_id="o_test", reporter_id=gupshup_reporter.id,
        seq_no=1, headline="Mid-thread", paragraphs=[],
        status="submitted", source="whatsapp",
        whatsapp_session_open_until=now_ist() + timedelta(minutes=5),
    ))
    db.commit()

    found = _find_open_draft(db, gupshup_reporter.id)
    assert found is not None
    assert found.id == "s_open"
