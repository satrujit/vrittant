import pytest
from app.services import whatsapp_classifier as wc


@pytest.mark.asyncio
async def test_classifies_news(monkeypatch):
    async def fake_call(prompt):
        return "news"
    monkeypatch.setattr(wc, "_sarvam_call", fake_call)
    assert await wc.classify("Police seized 50kg ganja in Cuttack today.") == "news"


@pytest.mark.asyncio
async def test_classifies_chitchat(monkeypatch):
    async def fake_call(prompt):
        return "chitchat"
    monkeypatch.setattr(wc, "_sarvam_call", fake_call)
    assert await wc.classify("hi are you there") == "chitchat"


@pytest.mark.asyncio
async def test_unknown_label_falls_back_to_unclear(monkeypatch):
    async def fake_call(prompt):
        return "blahblah"
    monkeypatch.setattr(wc, "_sarvam_call", fake_call)
    assert await wc.classify("ambiguous text") == "unclear"


@pytest.mark.asyncio
async def test_call_failure_falls_back_to_unclear(monkeypatch):
    async def boom(prompt):
        raise RuntimeError("upstream 500")
    monkeypatch.setattr(wc, "_sarvam_call", boom)
    assert await wc.classify("anything") == "unclear"


@pytest.mark.asyncio
async def test_empty_text_returns_unclear():
    # Should not even attempt the call for blank input
    assert await wc.classify("") == "unclear"
    assert await wc.classify("   ") == "unclear"


@pytest.mark.asyncio
async def test_timeout_falls_back_to_unclear(monkeypatch):
    import httpx
    async def timeout(prompt):
        raise httpx.TimeoutException("sarvam slow")
    monkeypatch.setattr(wc, "_sarvam_call", timeout)
    assert await wc.classify("anything") == "unclear"


@pytest.mark.asyncio
async def test_label_with_trailing_punctuation_is_accepted(monkeypatch):
    async def fake(prompt):
        return "news."
    monkeypatch.setattr(wc, "_sarvam_call", fake)
    assert await wc.classify("anything") == "news"
