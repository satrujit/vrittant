"""Tests for the Gemini STT path — gemini_client.stt + services/gemini_stt.

Covers:
  - gemini_client.stt builds the correct multipart payload (audio inline +
    transcription prompt) and returns the text.
  - Empty audio short-circuits.
  - 5xx → SttRetryable; 4xx → SttError (gemini_stt wrapper translation).
  - _cost_stt uses the audio_input_per_m rate, not the text input rate.
  - Name-registry post-processing fires (Indian names → Odia script).
"""
import asyncio
import base64
import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch


def _run(coro):
    return asyncio.run(coro)


# ── gemini_client.stt — payload + parsing ───────────────────────


def test_gemini_stt_builds_correct_payload_and_returns_text(monkeypatch):
    """Verify the request body has audio inlineData + the transcription
    prompt, and that the response's candidate text is returned.
    The legacy chat path uses the same response shape so we only test
    the audio-specific bits here."""
    from app.config import settings
    from app.services import gemini_client
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")

    captured = {}

    class _FakeResp:
        status_code = 200
        text = ""
        def json(self):
            return {
                "candidates": [{"content": {"parts": [{"text": "hello world"}]}}],
                "usageMetadata": {"promptTokenCount": 960, "candidatesTokenCount": 5},
            }

    class _FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, *, json=None, headers=None, timeout=None):
            captured["url"] = url
            captured["json"] = json
            return _FakeResp()

    with patch("app.services.gemini_client.httpx.AsyncClient",
               return_value=_FakeClient()), \
         patch("app.services.gemini_client._write_log_row") as mock_log:
        out = _run(gemini_client.stt(
            audio_bytes=b"RAW_AUDIO_BYTES",
            mime_type="audio/mp4",
            language_code="od-IN",
        ))

    assert out == "hello world"
    # URL contains the model
    assert "gemini-2.5-flash" in captured["url"]
    # Body has TWO parts: audio inlineData + text prompt
    parts = captured["json"]["contents"][0]["parts"]
    assert len(parts) == 2
    inline = parts[0]["inlineData"]
    assert inline["mimeType"] == "audio/mp4"
    assert base64.b64decode(inline["data"]) == b"RAW_AUDIO_BYTES"
    # Prompt mentions Odia (the language for od-IN) and tells Gemini
    # to transcribe (not translate)
    prompt = parts[1]["text"]
    assert "Odia" in prompt
    assert "transcribe" in prompt.lower()
    assert "translate" in prompt.lower()  # "Do not translate"
    # Cost row was logged with service="gemini_stt"
    mock_log.assert_called_once()
    kwargs = mock_log.call_args.kwargs
    assert kwargs["service"] == "gemini_stt"
    assert kwargs["input_tokens"] == 960
    assert kwargs["output_tokens"] == 5


def test_gemini_stt_empty_audio_short_circuits(monkeypatch):
    from app.services import gemini_client
    out = _run(gemini_client.stt(audio_bytes=b"", mime_type="audio/mp4"))
    assert out == ""


# ── Pricing ─────────────────────────────────────────────────────


def test_cost_stt_uses_audio_input_rate(monkeypatch):
    """The audio rate ($1.00/M for Flash) is 3.3× the text input rate
    ($0.30/M). _cost_stt MUST bill at the audio rate or we'll
    massively under-report STT spend in the usage ledger.
    """
    from app.services.gemini_client import _cost_stt
    # 1 million input tokens, 0 output. At Flash audio rate $1.00 → ₹84.
    cost = _cost_stt("gemini-2.5-flash", 1_000_000, 0)
    assert cost == Decimal("84.0000")
    # And at Flash-Lite ($0.30/M audio): 1M tokens → $0.30 → ₹25.20.
    cost_lite = _cost_stt("gemini-2.5-flash-lite", 1_000_000, 0)
    assert cost_lite == Decimal("25.2000")


def test_cost_stt_accounts_for_output_tokens(monkeypatch):
    """A typical 30s voice note: ~960 input audio tokens + ~50 output
    text tokens. Cost should reflect both."""
    from app.services.gemini_client import _cost_stt
    cost = _cost_stt("gemini-2.5-flash", 960, 50)
    # 960 × $1.00 / 1M + 50 × $2.50 / 1M = $0.001085, × ₹84 ≈ ₹0.0911
    assert Decimal("0.08") <= cost <= Decimal("0.10")


# ── gemini_stt wrapper — exception translation ──────────────────


def test_gemini_stt_5xx_raises_retryable(monkeypatch):
    """Gemini returns 503 → wrapper must raise SttRetryable so the
    caller falls back / retries (same contract as the Sarvam path)."""
    from app.services import gemini_stt
    from app.services.gemini_client import GeminiError

    err = GeminiError("gemini stt 503: service unavailable", status_code=503)
    with patch("app.services.gemini_stt.gemini_client.stt",
               new_callable=AsyncMock, side_effect=err):
        try:
            _run(gemini_stt.transcribe_audio(b"\x00\x01", filename="a.m4a"))
        except gemini_stt.SttRetryable:
            pass
        else:
            raise AssertionError("expected SttRetryable")


def test_gemini_stt_4xx_raises_unrecoverable(monkeypatch):
    from app.services import gemini_stt
    from app.services.gemini_client import GeminiError

    err = GeminiError("gemini stt 400: bad mime", status_code=400)
    with patch("app.services.gemini_stt.gemini_client.stt",
               new_callable=AsyncMock, side_effect=err):
        try:
            _run(gemini_stt.transcribe_audio(b"\x00", filename="a.m4a"))
        except gemini_stt.SttError as e:
            assert "400" in str(e)
        else:
            raise AssertionError("expected SttError")


def test_gemini_stt_applies_name_registry(monkeypatch):
    """The wrapper applies the same Odia-name fixup as the Sarvam path
    (replace_english_names) — so a transcript with romanised names
    gets normalised."""
    from app.services import gemini_stt

    with patch("app.services.gemini_stt.gemini_client.stt",
               new_callable=AsyncMock, return_value="raw transcript"), \
         patch("app.services.gemini_stt.name_registry.replace_english_names",
               return_value="fixed-up transcript") as mock_fixup:
        out = _run(gemini_stt.transcribe_audio(b"\x00", filename="a.m4a"))
    assert out == "fixed-up transcript"
    mock_fixup.assert_called_once_with("raw transcript")


# ── Hallucination filter ────────────────────────────────────────


def test_filter_hallucination_strips_known_phrase():
    from app.services.gemini_client import _filter_hallucination
    assert _filter_hallucination("This house is so beautiful") == ""
    # case-insensitive
    assert _filter_hallucination("THIS HOUSE IS SO BEAUTIFUL.") == ""
    # substring match
    assert _filter_hallucination("Well, this house is so beautiful actually.") == ""


def test_filter_hallucination_strips_pure_digits():
    from app.services.gemini_client import _filter_hallucination
    assert _filter_hallucination("1 2 3 4 5") == ""
    assert _filter_hallucination("one two three four") == ""
    # but a real transcript with a number stays
    assert _filter_hallucination(
        "ଆଜି ୨୦ ଜଣ ଲୋକ ଆସିଲେ"
    ) == "ଆଜି ୨୦ ଜଣ ଲୋକ ଆସିଲେ"


def test_filter_hallucination_passes_real_transcript():
    from app.services.gemini_client import _filter_hallucination
    odia = "ଆଜି ଗ୍ରାମରେ ଏକ ଦୁର୍ଘଟଣା ଘଟିଲା"
    assert _filter_hallucination(odia) == odia


# ── Echo stripping ──────────────────────────────────────────────


def test_strip_echoed_prior_removes_full_overlap():
    from app.services.gemini_client import _strip_echoed_prior
    out = _strip_echoed_prior(
        "ramesh was injured today the police arrived",
        "ramesh was injured",
    )
    assert out == "today the police arrived"


def test_strip_echoed_prior_partial_suffix_overlap():
    """Model may echo only the LAST few words of the prior context.
    Detect and strip just those."""
    from app.services.gemini_client import _strip_echoed_prior
    out = _strip_echoed_prior(
        "was injured today the police arrived",
        "the man was injured",
    )
    assert out == "today the police arrived"


def test_strip_echoed_prior_no_overlap_returns_unchanged():
    from app.services.gemini_client import _strip_echoed_prior
    out = _strip_echoed_prior(
        "completely fresh content here",
        "earlier unrelated words",
    )
    assert out == "completely fresh content here"


def test_strip_echoed_prior_empty_inputs_pass_through():
    from app.services.gemini_client import _strip_echoed_prior
    assert _strip_echoed_prior("", "anything") == ""
    assert _strip_echoed_prior("anything", "") == "anything"


# ── Prompt building ─────────────────────────────────────────────


def test_build_stt_prompt_without_prior_context():
    from app.services.gemini_client import _build_stt_prompt
    p = _build_stt_prompt("od-IN")
    assert "Odia" in p
    assert "EMPTY STRING" in p  # anti-hallucination instruction present
    assert "this house" in p.lower()  # call-out the specific bad phrase
    # No prior-context block when none supplied
    assert "continues a longer recording" not in p


def test_build_stt_prompt_with_prior_context():
    from app.services.gemini_client import _build_stt_prompt
    p = _build_stt_prompt("od-IN", prior_context="ରମେଶ ଆହତ ହେଲେ")
    assert "Odia" in p
    assert "ରମେଶ ଆହତ ହେଲେ" in p
    assert "DO NOT repeat" in p


# ── End-to-end: stt() forwards prior_context into the prompt ────


def test_gemini_stt_forwards_prior_context_to_prompt(monkeypatch):
    from app.config import settings
    from app.services import gemini_client
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")

    captured = {}

    class _FakeResp:
        status_code = 200
        text = ""
        def json(self):
            return {
                "candidates": [{"content": {"parts": [{"text": "new content here"}]}}],
                "usageMetadata": {"promptTokenCount": 200, "candidatesTokenCount": 4},
            }

    class _FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, *, json=None, headers=None, timeout=None):
            captured["json"] = json
            return _FakeResp()

    with patch("app.services.gemini_client.httpx.AsyncClient",
               return_value=_FakeClient()), \
         patch("app.services.gemini_client._write_log_row"):
        out = _run(gemini_client.stt(
            audio_bytes=b"PCM",
            mime_type="audio/wav",
            language_code="od-IN",
            prior_context="ରମେଶ ଆହତ ହେଲେ",
        ))

    assert out == "new content here"
    prompt_text = captured["json"]["contents"][0]["parts"][1]["text"]
    assert "ରମେଶ ଆହତ ହେଲେ" in prompt_text
    assert "DO NOT repeat" in prompt_text
