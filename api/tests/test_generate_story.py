"""Tests for POST /api/llm/generate-story.

Coverage:
- Post-processing (Odia digit normalization, danda spacing)
- Transient vs non-transient classification
- Happy path (Anthropic serves)
- Fallback path (Anthropic transient → Sarvam serves)
- No-fallback path (Anthropic 401/400 → 502, Sarvam never called)
- Both-fail path (Anthropic 529 → Sarvam fails → 502)
- Empty notes → 400
- Empty Anthropic body → triggers fallback (treated as transient)
"""
from __future__ import annotations

import pytest

from app.routers import generate_story as gs_module
from app.services.anthropic_client import AnthropicError, is_transient_error


# ---------------------------------------------------------------------------
# Pure-function tests — no fixtures needed
# ---------------------------------------------------------------------------


def test_post_process_converts_ascii_digits_to_odia():
    assert gs_module._post_process("123") == "୧୨୩"


def test_post_process_adds_space_before_unspaced_danda():
    assert gs_module._post_process("ଶିକ୍ଷା।") == "ଶିକ୍ଷା ।"


def test_post_process_preserves_already_spaced_danda():
    assert gs_module._post_process("ଶିକ୍ଷା ।") == "ଶିକ୍ଷା ।"


def test_post_process_handles_empty_string():
    assert gs_module._post_process("") == ""
    assert gs_module._post_process("   ") == ""


def test_post_process_combines_both_transforms():
    # Roman 2026 → Odia ୨୦୨୬, and the unspaced danda gets a space.
    assert gs_module._post_process("ତା 24/4 2026।") == "ତା ୨୪/୪ ୨୦୨୬ ।"


# is_transient_error classification (drives the fallback decision) ----------


def test_transient_5xx_is_transient():
    assert is_transient_error(AnthropicError("oops", status_code=503)) is True


def test_transient_429_is_transient():
    assert is_transient_error(AnthropicError("rate limit", status_code=429)) is True


def test_transient_529_overload_is_transient():
    assert is_transient_error(AnthropicError("overloaded", status_code=529)) is True


def test_transient_no_status_is_transient():
    # Network/timeout errors arrive with status_code=None.
    assert is_transient_error(AnthropicError("timeout", status_code=None)) is True


def test_400_is_NOT_transient():
    # Bad payload — our bug. Don't fall back, surface it loud.
    assert is_transient_error(AnthropicError("bad request", status_code=400)) is False


def test_401_is_NOT_transient():
    # Bad/missing key — deploy bug. Don't fall back.
    assert is_transient_error(AnthropicError("unauthorized", status_code=401)) is False


def test_403_is_NOT_transient():
    assert is_transient_error(AnthropicError("forbidden", status_code=403)) is False


# ---------------------------------------------------------------------------
# Endpoint tests — patch anthropic_client.chat + sarvam_client.chat
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_reporter_header(reporter, db):
    """JWT for the reporter fixture — generate-story is reporter-facing."""
    from jose import jwt
    from app.config import settings
    token = jwt.encode({"sub": reporter.id}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


def _fake_anthropic_response(text: str) -> dict:
    """Shape Anthropic's /v1/messages response so extract_text() finds the body."""
    return {
        "id": "msg_test",
        "content": [{"type": "text", "text": text}],
        "usage": {"input_tokens": 100, "output_tokens": 50},
        "stop_reason": "end_turn",
    }


def _fake_sarvam_response(text: str) -> dict:
    """OpenAI-compatible chat shape with `text` as the assistant content."""
    return {
        "id": "chatcmpl-test",
        "model": "sarvam-30b",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }


def test_generate_story_happy_path(client, reporter, auth_reporter_header, monkeypatch):
    """Anthropic returns content → endpoint returns it, fallback_used=False."""
    sarvam_called = {"yes": False}

    async def fake_anthropic_chat(**kwargs):
        return _fake_anthropic_response("ପ୍ରଥମ ପାରା ।\n\nଦ୍ୱିତୀୟ ପାରା ।")

    async def fake_sarvam_chat(**kwargs):
        sarvam_called["yes"] = True
        raise AssertionError("Sarvam must NOT be called when Anthropic succeeds")

    monkeypatch.setattr(gs_module.anthropic_client, "chat", fake_anthropic_chat)
    monkeypatch.setattr(gs_module.sarvam_client, "chat", fake_sarvam_chat)

    r = client.post(
        "/api/llm/generate-story",
        json={"notes": "ରିପୋର୍ଟରଙ୍କ କଞ୍ଚା ନୋଟ ।"},
        headers=auth_reporter_header,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["model"] == "claude-haiku-4-5"
    assert data["fallback_used"] is False
    assert "ପ୍ରଥମ ପାରା" in data["body"]
    assert sarvam_called["yes"] is False


def test_generate_story_falls_back_on_anthropic_529(client, reporter, auth_reporter_header, monkeypatch):
    """Anthropic 529 (overloaded) → Sarvam serves, fallback_used=True."""

    async def fake_anthropic_chat(**kwargs):
        raise AnthropicError("overloaded", status_code=529)

    async def fake_sarvam_chat(**kwargs):
        return _fake_sarvam_response("ଫଲବ୍ୟାକ ବଡୀ ।")

    monkeypatch.setattr(gs_module.anthropic_client, "chat", fake_anthropic_chat)
    monkeypatch.setattr(gs_module.sarvam_client, "chat", fake_sarvam_chat)

    r = client.post(
        "/api/llm/generate-story",
        json={"notes": "ଖବର"},
        headers=auth_reporter_header,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["model"] == "sarvam-30b"
    assert data["fallback_used"] is True
    assert "ଫଲବ୍ୟାକ" in data["body"]


def test_generate_story_falls_back_on_anthropic_timeout(client, reporter, auth_reporter_header, monkeypatch):
    """Anthropic network error (status_code=None) → fall back."""

    async def fake_anthropic_chat(**kwargs):
        raise AnthropicError("connection timed out", status_code=None)

    async def fake_sarvam_chat(**kwargs):
        return _fake_sarvam_response("ଫଲବ୍ୟାକ ।")

    monkeypatch.setattr(gs_module.anthropic_client, "chat", fake_anthropic_chat)
    monkeypatch.setattr(gs_module.sarvam_client, "chat", fake_sarvam_chat)

    r = client.post(
        "/api/llm/generate-story",
        json={"notes": "ଖବର"},
        headers=auth_reporter_header,
    )
    assert r.status_code == 200, r.text
    assert r.json()["fallback_used"] is True


def test_generate_story_does_NOT_fall_back_on_anthropic_401(client, reporter, auth_reporter_header, monkeypatch):
    """Anthropic 401 (auth bug) → 502 to client, Sarvam NOT called."""
    sarvam_called = {"yes": False}

    async def fake_anthropic_chat(**kwargs):
        raise AnthropicError("invalid api key", status_code=401)

    async def fake_sarvam_chat(**kwargs):
        sarvam_called["yes"] = True
        raise AssertionError("Sarvam must NOT be called on 401")

    monkeypatch.setattr(gs_module.anthropic_client, "chat", fake_anthropic_chat)
    monkeypatch.setattr(gs_module.sarvam_client, "chat", fake_sarvam_chat)

    r = client.post(
        "/api/llm/generate-story",
        json={"notes": "ଖବର"},
        headers=auth_reporter_header,
    )
    assert r.status_code == 502
    assert sarvam_called["yes"] is False


def test_generate_story_does_NOT_fall_back_on_anthropic_400(client, reporter, auth_reporter_header, monkeypatch):
    """Anthropic 400 (bad payload) → 502, no fallback."""

    async def fake_anthropic_chat(**kwargs):
        raise AnthropicError("messages: invalid", status_code=400)

    async def fake_sarvam_chat(**kwargs):
        raise AssertionError("Sarvam must NOT be called on 400")

    monkeypatch.setattr(gs_module.anthropic_client, "chat", fake_anthropic_chat)
    monkeypatch.setattr(gs_module.sarvam_client, "chat", fake_sarvam_chat)

    r = client.post(
        "/api/llm/generate-story",
        json={"notes": "ଖବର"},
        headers=auth_reporter_header,
    )
    assert r.status_code == 502


def test_generate_story_502_when_both_providers_fail(client, reporter, auth_reporter_header, monkeypatch):
    """Anthropic 529 → Sarvam raises → 502."""

    async def fake_anthropic_chat(**kwargs):
        raise AnthropicError("overloaded", status_code=529)

    async def fake_sarvam_chat(**kwargs):
        raise RuntimeError("sarvam down too")

    monkeypatch.setattr(gs_module.anthropic_client, "chat", fake_anthropic_chat)
    monkeypatch.setattr(gs_module.sarvam_client, "chat", fake_sarvam_chat)

    r = client.post(
        "/api/llm/generate-story",
        json={"notes": "ଖବର"},
        headers=auth_reporter_header,
    )
    assert r.status_code == 502


def test_generate_story_empty_anthropic_response_triggers_fallback(client, reporter, auth_reporter_header, monkeypatch):
    """Empty content from Anthropic → treat as transient → fall back."""

    async def fake_anthropic_chat(**kwargs):
        return {"content": [], "usage": {"input_tokens": 10, "output_tokens": 0}}

    async def fake_sarvam_chat(**kwargs):
        return _fake_sarvam_response("ଫଲବ୍ୟାକ ।")

    monkeypatch.setattr(gs_module.anthropic_client, "chat", fake_anthropic_chat)
    monkeypatch.setattr(gs_module.sarvam_client, "chat", fake_sarvam_chat)

    r = client.post(
        "/api/llm/generate-story",
        json={"notes": "ଖବର"},
        headers=auth_reporter_header,
    )
    assert r.status_code == 200, r.text
    assert r.json()["fallback_used"] is True


def test_generate_story_rejects_empty_notes(client, reporter, auth_reporter_header):
    """Empty/whitespace notes → 400 from validation, no LLM call."""
    r = client.post(
        "/api/llm/generate-story",
        json={"notes": ""},
        headers=auth_reporter_header,
    )
    # Pydantic min_length=1 rejects with 422 before we hit the handler.
    assert r.status_code in (400, 422)


def test_generate_story_requires_auth(client):
    """No bearer token → unauthorized.

    FastAPI's HTTPBearer dependency returns 403 by default when the
    Authorization header is missing; some auth setups return 401 instead.
    Either is fine — the point is "not 200" without credentials.
    """
    r = client.post("/api/llm/generate-story", json={"notes": "ଖବର"})
    assert r.status_code in (401, 403)


def test_generate_story_response_is_post_processed(client, reporter, auth_reporter_header, monkeypatch):
    """End-to-end: ASCII digits in LLM output get normalized; danda spacing fixed."""

    async def fake_anthropic_chat(**kwargs):
        # Return a body with ASCII digits and an unspaced danda — the
        # endpoint should clean both before returning.
        return _fake_anthropic_response("ତା 24/4 2026 (ପିଏନଏସ) ଖବର।")

    monkeypatch.setattr(gs_module.anthropic_client, "chat", fake_anthropic_chat)

    r = client.post(
        "/api/llm/generate-story",
        json={"notes": "ଖବର"},
        headers=auth_reporter_header,
    )
    assert r.status_code == 200, r.text
    body = r.json()["body"]
    assert "୨୪/୪" in body  # Roman 24/4 → Odia ୨୪/୪
    assert "୨୦୨୬" in body  # Roman 2026 → Odia ୨୦୨୬
    assert " ।" in body     # danda gets its space
    assert "0" not in body and "1" not in body and "2" not in body  # no ASCII digits left
