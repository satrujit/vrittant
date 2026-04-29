import pytest
from app.services import whatsapp_classifier as wc


# All tests mock gemini_client.chat directly, since the classifier now
# calls Gemini (post 2026-04-29 migration) instead of Sarvam. The
# behavior under test is the parsing/normalisation of the LLM response,
# not the provider details.

def _patch_gemini(monkeypatch, returner):
    async def fake_chat(*args, **kwargs):
        return await returner(kwargs.get("prompt", ""))
    monkeypatch.setattr(wc.gemini_client, "chat", fake_chat)


@pytest.mark.asyncio
async def test_classifies_news(monkeypatch):
    async def returner(_): return "news"
    _patch_gemini(monkeypatch, returner)
    assert await wc.classify("Police seized 50kg ganja in Cuttack today.") == "news"


@pytest.mark.asyncio
async def test_classifies_chitchat(monkeypatch):
    async def returner(_): return "chitchat"
    _patch_gemini(monkeypatch, returner)
    assert await wc.classify("hi are you there") == "chitchat"


@pytest.mark.asyncio
async def test_unknown_label_falls_back_to_unclear(monkeypatch):
    async def returner(_): return "blahblah"
    _patch_gemini(monkeypatch, returner)
    assert await wc.classify("ambiguous text") == "unclear"


@pytest.mark.asyncio
async def test_call_failure_falls_back_to_unclear(monkeypatch):
    async def boom(_): raise RuntimeError("upstream 500")
    _patch_gemini(monkeypatch, boom)
    assert await wc.classify("anything") == "unclear"


@pytest.mark.asyncio
async def test_empty_text_returns_unclear():
    # Should not even attempt the call for blank input
    assert await wc.classify("") == "unclear"
    assert await wc.classify("   ") == "unclear"


@pytest.mark.asyncio
async def test_timeout_falls_back_to_unclear(monkeypatch):
    import httpx
    async def timeout(_): raise httpx.TimeoutException("gemini slow")
    _patch_gemini(monkeypatch, timeout)
    assert await wc.classify("anything") == "unclear"


@pytest.mark.asyncio
async def test_label_with_trailing_punctuation_is_accepted(monkeypatch):
    async def fake(_): return "news."
    _patch_gemini(monkeypatch, fake)
    assert await wc.classify("anything") == "news"
