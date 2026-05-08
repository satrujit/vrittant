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


def test_gemini_stt_builds_systeminstruction_payload(monkeypatch):
    """Architectural shape verification: directive lives in
    ``systemInstruction``, audio is the ONLY content. Ensures the
    transcription instruction can never be echoed back as part of the
    transcript (Gemini doesn't repeat systemInstruction text)."""
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
    body = captured["json"]

    # The directive is in systemInstruction (not in user content).
    sys_text = body["systemInstruction"]["parts"][0]["text"]
    assert "Odia" in sys_text
    assert "transcrib" in sys_text.lower()
    assert "Never echo this instruction" in sys_text

    # User content has ONLY the audio — no inline text alongside it.
    parts = body["contents"][0]["parts"]
    assert len(parts) == 1
    inline = parts[0]["inlineData"]
    assert inline["mimeType"] == "audio/mp4"
    assert base64.b64decode(inline["data"]) == b"RAW_AUDIO_BYTES"

    # Cost row logged
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


def test_build_system_instruction_includes_language_hint():
    """The system instruction must name the actual spoken language
    so Gemini stays anchored to the right script (the missing-language-
    hint failure mode produced Tamil transcripts of Odia speech)."""
    from app.services.gemini_client import _build_stt_system_instruction
    p = _build_stt_system_instruction("od-IN")
    assert "Odia" in p


def test_build_system_instruction_forbids_echoing():
    """The instruction itself must explicitly forbid echoing — the
    "Stay true to audio. Don't add anything." appearing in user-visible
    transcripts was caused by an inline-prompt setup that didn't have
    this clause."""
    from app.services.gemini_client import _build_stt_system_instruction
    p = _build_stt_system_instruction("od-IN")
    assert "Never echo this instruction" in p


def test_build_system_instruction_forbids_known_hallucinations():
    """Belt-and-suspenders with the post-call _filter_hallucination —
    the instruction should explicitly call out the worst-offender
    boilerplate phrases so the model is less likely to emit them in
    the first place."""
    from app.services.gemini_client import _build_stt_system_instruction
    p = _build_stt_system_instruction("od-IN")
    assert "this house is so beautiful" in p.lower()
    assert "one two three" in p.lower() or "counted numbers" in p.lower()


def test_build_system_instruction_handles_unknown_language():
    """Falls back to a neutral phrase when the language code isn't in
    the lookup table — no crash, no garbled prompt."""
    from app.services.gemini_client import _build_stt_system_instruction
    p = _build_stt_system_instruction("xx-YY")
    assert "speaker's native language" in p


# ── End-to-end: stt() forwards prior_context into the prompt ────


def test_gemini_stt_does_not_send_prior_context_to_model(monkeypatch):
    """Architectural shape: even when callers pass prior_context, it
    is NOT interpolated into the request payload anymore. The
    parameter is accepted for backward-compat but text-based
    continuity hints are no longer sent (they created the echo-loop
    failure mode on small models). User content stays audio-only;
    systemInstruction stays unchanging across calls.

    Echo-strip is still applied to the model's RESPONSE if a caller
    passes prior_context (defense in depth) — but the model never
    sees the prior_context in its prompt, so it can't echo it."""
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

    # Walk every text part anywhere in the request and confirm the
    # prior-context string is not present. The directive in
    # systemInstruction must NOT include the prior-context phrase;
    # the audio-only user content can't include text at all.
    body = captured["json"]
    sys_text = body["systemInstruction"]["parts"][0]["text"]
    assert "ରମେଶ ଆହତ ହେଲେ" not in sys_text
    for part in body["contents"][0]["parts"]:
        # parts in user content are inlineData (audio) only — no text
        assert "text" not in part


# ── usage_sink (per-session cost accumulation) ──────────────────


def test_gemini_stt_appends_to_usage_sink(monkeypatch):
    """Streaming handler passes a list as usage_sink and we append one
    entry per successful call (input_tokens, output_tokens, cost_inr,
    duration_ms). Lets the WS handler sum cost across the session
    without DB round-trips."""
    from app.config import settings
    from app.services import gemini_client
    from decimal import Decimal
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")

    class _FakeResp:
        status_code = 200
        text = ""
        def json(self):
            return {
                "candidates": [{"content": {"parts": [{"text": "ok"}]}}],
                "usageMetadata": {"promptTokenCount": 130, "candidatesTokenCount": 8},
            }

    class _FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **kw):
            return _FakeResp()

    sink: list = []
    with patch("app.services.gemini_client.httpx.AsyncClient",
               return_value=_FakeClient()), \
         patch("app.services.gemini_client._write_log_row"):
        _run(gemini_client.stt(
            audio_bytes=b"PCM",
            mime_type="audio/wav",
            usage_sink=sink,
        ))
        _run(gemini_client.stt(
            audio_bytes=b"PCM",
            mime_type="audio/wav",
            usage_sink=sink,
        ))

    assert len(sink) == 2
    for entry in sink:
        assert entry["input_tokens"] == 130
        assert entry["output_tokens"] == 8
        assert isinstance(entry["cost_inr"], Decimal)
        assert entry["cost_inr"] > 0
        assert entry["duration_ms"] >= 0


def test_gemini_stt_works_without_usage_sink(monkeypatch):
    """Backward-compat: existing callers (e.g. the batch path via
    services/gemini_stt.py) don't pass usage_sink and must still work."""
    from app.config import settings
    from app.services import gemini_client
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")

    class _FakeResp:
        status_code = 200
        text = ""
        def json(self):
            return {
                "candidates": [{"content": {"parts": [{"text": "ok"}]}}],
                "usageMetadata": {"promptTokenCount": 130, "candidatesTokenCount": 8},
            }

    class _FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **kw):
            return _FakeResp()

    with patch("app.services.gemini_client.httpx.AsyncClient",
               return_value=_FakeClient()), \
         patch("app.services.gemini_client._write_log_row"):
        out = _run(gemini_client.stt(audio_bytes=b"PCM", mime_type="audio/wav"))
    assert out == "ok"
