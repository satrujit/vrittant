"""Tests for the Gupshup webhook signature-verification middleware."""
import hashlib
import hmac
import json

import pytest


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


# ── verify_signature (pure) ────────────────────────────────────


def test_verify_skipped_when_secret_empty():
    from app.services.whatsapp.auth import verify_signature
    assert verify_signature(body=b"any", headers={}, secret="") is True


def test_verify_pass_with_correct_signature():
    from app.services.whatsapp.auth import verify_signature
    body = b'{"hello":"world"}'
    sig = _sign("topsecret", body)
    headers = {"X-Gupshup-Signature": sig}
    assert verify_signature(body=body, headers=headers, secret="topsecret") is True


def test_verify_pass_with_sha256_prefix():
    """Some integrations send `sha256=<hex>` rather than bare hex."""
    from app.services.whatsapp.auth import verify_signature
    body = b'{"x":1}'
    sig = _sign("topsecret", body)
    headers = {"X-Hub-Signature-256": f"sha256={sig}"}
    assert verify_signature(body=body, headers=headers, secret="topsecret") is True


def test_verify_fail_when_header_missing():
    from app.services.whatsapp.auth import verify_signature
    assert verify_signature(body=b"x", headers={}, secret="topsecret") is False


def test_verify_fail_when_signature_wrong():
    from app.services.whatsapp.auth import verify_signature
    body = b"hello"
    headers = {"X-Gupshup-Signature": _sign("OTHER_SECRET", body)}
    assert verify_signature(body=body, headers=headers, secret="topsecret") is False


def test_verify_constant_time_comparison(monkeypatch):
    """Sanity: we don't break out of compare_digest early. Indirect — we
    just call the function with various-length signatures and assert no
    exception. The constant-time guarantee comes from hmac.compare_digest
    which we use directly."""
    from app.services.whatsapp.auth import verify_signature
    body = b"x"
    for fake in ("", "0" * 8, "0" * 64, "0" * 128, "z" * 64):
        verify_signature(
            body=body, headers={"X-Gupshup-Signature": fake}, secret="s",
        )  # no assertion — just shouldn't raise


# ── middleware (integration) ───────────────────────────────────


def test_middleware_passes_through_non_whatsapp_routes(client, monkeypatch):
    """A request to /docs (or any non-/webhooks/whatsapp path) is
    untouched even when the secret is set."""
    from app.config import settings
    monkeypatch.setattr(settings, "GUPSHUP_WEBHOOK_SECRET", "topsecret")
    # The TestClient is built from app.main; non-whatsapp routes still 404
    # but the middleware shouldn't reject them with 403.
    r = client.get("/health-nonexistent")
    assert r.status_code != 403


def test_middleware_rejects_unsigned_when_secret_set(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "GUPSHUP_WEBHOOK_SECRET", "topsecret")
    r = client.post("/webhooks/whatsapp/gupshup", json={"any": "thing"})
    assert r.status_code == 403


def test_middleware_accepts_signed_when_secret_set(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "GUPSHUP_WEBHOOK_SECRET", "topsecret")
    body = b'{"app":"Vrittant","type":"message","payload":{}}'
    sig = _sign("topsecret", body)
    r = client.post(
        "/webhooks/whatsapp/gupshup",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Gupshup-Signature": sig,
        },
    )
    # Reaches the handler — depending on payload shape it may 200 or 400,
    # but it MUST NOT be 403.
    assert r.status_code != 403


def test_middleware_skips_when_secret_empty(client, monkeypatch):
    """Default behaviour during initial rollout: no secret, no rejection.
    The handler still rejects malformed payloads on its own — we only
    care that the middleware doesn't 403 here."""
    from app.config import settings
    monkeypatch.setattr(settings, "GUPSHUP_WEBHOOK_SECRET", "")
    r = client.post("/webhooks/whatsapp/gupshup", json={"any": "thing"})
    assert r.status_code != 403
