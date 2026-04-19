"""Tests for the Gupshup WhatsApp inbound webhook.

Reporters forward government press releases to the Vrittant WABA number;
if the sender is a registered active user we create a draft story
assigned to them. The webhook always returns 200 (Gupshup retries
non-2xx) and replies via the Gupshup HTTP API.
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

    async def fake(url: str, content_type: str | None = None) -> str | None:
        persisted.append(url)
        return f"https://storage.googleapis.com/test-bucket/whatsapp/fake-{len(persisted)}.bin"

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
    assert s.assigned_to == gupshup_reporter.id
    assert s.organization_id == gupshup_reporter.organization_id
    assert "highway" in (s.headline + " ".join(p.get("text", "") for p in (s.paragraphs or []) if isinstance(p, dict))).lower()
    # Confirmation reply was sent to the same phone
    assert len(no_send) == 1
    assert no_send[0][0] == "919876543210"


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
    async def failing_persist(url, content_type=None):
        return None

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


def test_photo_only_first_message_skips_classifier(
    client, db, gupshup_reporter, no_send, fake_persist, monkeypatch
):
    from app.routers import webhooks_whatsapp
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
    client.post("/webhooks/whatsapp/gupshup", json=body)
    assert called == []  # classifier never invoked
    assert db.query(Story).count() == 1
    assert db.query(Story).first().needs_triage is False
