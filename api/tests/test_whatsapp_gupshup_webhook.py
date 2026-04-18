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


def test_image_message_records_caption_and_media_url(client, db, gupshup_reporter, no_send):
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

    stories = db.query(Story).filter_by(reporter_id=gupshup_reporter.id).all()
    assert len(stories) == 1
    flat_text = " ".join(p.get("text", "") for p in (stories[0].paragraphs or []) if isinstance(p, dict))
    assert "press conference" in (stories[0].headline + flat_text).lower()
    assert "https://gupshup-media.example/abc.jpg" in flat_text or any(
        p.get("media_url") == "https://gupshup-media.example/abc.jpg"
        for p in (stories[0].paragraphs or []) if isinstance(p, dict)
    )


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
