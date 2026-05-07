"""Tests for the Gupshup webhook authentication middleware.

Gupshup attaches a static shared-secret token in a header (configured
via their dashboard's "Includes headers" feature). We compare the
header value to the configured secret in constant time.
"""
import pytest


# ── verify_signature (pure) ────────────────────────────────────


def test_verify_skipped_when_secret_empty():
    from app.services.whatsapp.auth import verify_signature
    assert verify_signature(headers={}, secret="") is True


def test_verify_pass_with_matching_token():
    from app.services.whatsapp.auth import verify_signature
    headers = {"X-Gupshup-Signature": "topsecret"}
    assert verify_signature(headers=headers, secret="topsecret") is True


def test_verify_fail_when_header_missing():
    from app.services.whatsapp.auth import verify_signature
    assert verify_signature(headers={}, secret="topsecret") is False


def test_verify_fail_with_wrong_token():
    from app.services.whatsapp.auth import verify_signature
    headers = {"X-Gupshup-Signature": "wrongtoken"}
    assert verify_signature(headers=headers, secret="topsecret") is False


def test_verify_accepts_authorization_bearer_prefix():
    """Authorization: Bearer <token> is the more conventional shape;
    accept it for users who configure that header on Gupshup."""
    from app.services.whatsapp.auth import verify_signature
    headers = {"Authorization": "Bearer topsecret"}
    assert verify_signature(headers=headers, secret="topsecret") is True


def test_verify_accepts_alternate_header_names():
    """X-Webhook-Token and X-Auth-Token also accepted."""
    from app.services.whatsapp.auth import verify_signature
    for h in ("X-Webhook-Token", "X-Auth-Token"):
        assert verify_signature(headers={h: "topsecret"}, secret="topsecret") is True


def test_verify_case_insensitive_header_lookup():
    from app.services.whatsapp.auth import verify_signature
    headers = {"x-gupshup-signature": "topsecret"}  # lowercase
    assert verify_signature(headers=headers, secret="topsecret") is True


def test_verify_strips_whitespace():
    from app.services.whatsapp.auth import verify_signature
    headers = {"X-Gupshup-Signature": "  topsecret  "}
    assert verify_signature(headers=headers, secret="topsecret") is True


# ── middleware (integration) ───────────────────────────────────


def test_middleware_passes_through_non_whatsapp_routes(client, monkeypatch):
    """A request to a non-/webhooks/whatsapp path is untouched even when
    the secret is set."""
    from app.config import settings
    monkeypatch.setattr(settings, "GUPSHUP_WEBHOOK_SECRET", "topsecret")
    r = client.get("/health-nonexistent")
    assert r.status_code != 403


def test_middleware_rejects_unauthenticated_when_secret_set(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "GUPSHUP_WEBHOOK_SECRET", "topsecret")
    r = client.post("/webhooks/whatsapp/gupshup", json={"any": "thing"})
    assert r.status_code == 403


def test_middleware_accepts_authenticated_when_secret_set(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "GUPSHUP_WEBHOOK_SECRET", "topsecret")
    r = client.post(
        "/webhooks/whatsapp/gupshup",
        json={"app": "Vrittant", "type": "message", "payload": {}},
        headers={"X-Gupshup-Signature": "topsecret"},
    )
    # Reaches the handler — depending on payload shape it may 200 or 4xx,
    # but it MUST NOT be 403.
    assert r.status_code != 403


def test_middleware_skips_when_secret_empty(client, monkeypatch):
    """Default behaviour during initial rollout: no secret, no rejection."""
    from app.config import settings
    monkeypatch.setattr(settings, "GUPSHUP_WEBHOOK_SECRET", "")
    r = client.post("/webhooks/whatsapp/gupshup", json={"any": "thing"})
    assert r.status_code != 403
