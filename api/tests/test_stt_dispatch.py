"""Dispatcher tests for services/stt.py — provider routing + dual-log A/B.

Covers:
  - STT_PROVIDER="sarvam" routes to the Sarvam path (existing behaviour).
  - STT_PROVIDER="gemini" routes to the Gemini path.
  - Empty audio short-circuits to "" without calling either provider.
  - STT_DUAL_LOG=True calls both providers in parallel, returns the
    primary, and emits one stt.shadow INFO log line.
  - Shadow failure does not break the hot path.
  - Primary failure still propagates (and shadow is awaited / not leaked).
  - Unknown STT_PROVIDER falls back to sarvam with a warning.
"""
import asyncio
import logging
from unittest.mock import AsyncMock, patch


def _run(coro):
    return asyncio.run(coro)


# ── Routing ─────────────────────────────────────────────────────


def test_empty_audio_short_circuits():
    from app.services.stt import transcribe_audio
    # No provider should be invoked for empty input.
    with patch("app.services.stt._dispatch_one", new_callable=AsyncMock) as mock_dispatch:
        result = _run(transcribe_audio(b"", filename="audio.m4a"))
    assert result == ""
    mock_dispatch.assert_not_called()


def test_provider_sarvam_routes_to_sarvam(monkeypatch):
    from app.config import settings
    from app.services import stt
    monkeypatch.setattr(settings, "STT_PROVIDER", "sarvam")
    monkeypatch.setattr(settings, "STT_DUAL_LOG", False)

    with patch.object(stt, "_sarvam_transcribe", new_callable=AsyncMock,
                      return_value="from sarvam") as mock_sarvam:
        out = _run(stt.transcribe_audio(b"\x00\x01\x02", filename="a.m4a"))
    assert out == "from sarvam"
    mock_sarvam.assert_awaited_once()


def test_provider_gemini_routes_to_gemini(monkeypatch):
    from app.config import settings
    from app.services import stt, gemini_stt
    monkeypatch.setattr(settings, "STT_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "STT_DUAL_LOG", False)
    monkeypatch.setattr(settings, "STT_GEMINI_MODEL", "gemini-2.5-flash")

    with patch.object(gemini_stt, "transcribe_audio", new_callable=AsyncMock,
                      return_value="from gemini") as mock_gemini:
        out = _run(stt.transcribe_audio(b"\x00\x01\x02", filename="a.m4a"))
    assert out == "from gemini"
    mock_gemini.assert_awaited_once()


def test_unknown_provider_falls_back_to_sarvam(monkeypatch):
    from app.config import settings
    from app.services import stt
    monkeypatch.setattr(settings, "STT_PROVIDER", "azure")  # not a valid choice
    monkeypatch.setattr(settings, "STT_DUAL_LOG", False)

    # Patch the module logger so we can assert the warning was emitted
    # without depending on caplog's interaction with the test config's
    # log filters.
    with patch.object(stt, "_sarvam_transcribe", new_callable=AsyncMock,
                      return_value="fallback") as mock_sarvam, \
         patch.object(stt.logger, "warning") as mock_warn:
        out = _run(stt.transcribe_audio(b"\x00", filename="a.m4a"))

    assert out == "fallback"
    mock_sarvam.assert_awaited_once()
    # At least one warning mentioned the unknown provider
    assert any(
        "Unknown STT_PROVIDER" in (call.args[0] if call.args else "")
        for call in mock_warn.call_args_list
    )


# ── Dual-log A/B mode ───────────────────────────────────────────


def test_dual_log_calls_both_and_returns_primary(monkeypatch, caplog):
    from app.config import settings
    from app.services import stt, gemini_stt
    monkeypatch.setattr(settings, "STT_PROVIDER", "sarvam")
    monkeypatch.setattr(settings, "STT_DUAL_LOG", True)

    with patch.object(stt, "_sarvam_transcribe", new_callable=AsyncMock,
                      return_value="primary text") as mock_sarvam, \
         patch.object(gemini_stt, "transcribe_audio", new_callable=AsyncMock,
                      return_value="shadow text") as mock_gemini:
        with caplog.at_level(logging.INFO, logger="stt.shadow"):
            out = _run(stt.transcribe_audio(b"\x00\x01\x02", filename="a.m4a"))

    # Primary is what callers see
    assert out == "primary text"
    mock_sarvam.assert_awaited_once()
    mock_gemini.assert_awaited_once()
    # And we logged a comparison line on the dedicated logger
    compare_lines = [r for r in caplog.records if r.name == "stt.shadow"]
    assert len(compare_lines) == 1
    msg = compare_lines[0].getMessage()
    assert "primary text" in msg
    assert "shadow text" in msg
    assert "primary=sarvam" in msg
    assert "shadow=gemini" in msg


def test_dual_log_shadow_failure_does_not_break_hot_path(monkeypatch, caplog):
    """Shadow provider crashes — primary's result must still be returned,
    and the comparison log records '<failed>' for the shadow side."""
    from app.config import settings
    from app.services import stt, gemini_stt
    monkeypatch.setattr(settings, "STT_PROVIDER", "sarvam")
    monkeypatch.setattr(settings, "STT_DUAL_LOG", True)

    with patch.object(stt, "_sarvam_transcribe", new_callable=AsyncMock,
                      return_value="primary survives"), \
         patch.object(gemini_stt, "transcribe_audio", new_callable=AsyncMock,
                      side_effect=RuntimeError("gemini exploded")):
        with caplog.at_level(logging.INFO, logger="stt.shadow"):
            out = _run(stt.transcribe_audio(b"\x00", filename="a.m4a"))

    assert out == "primary survives"
    compare_lines = [r for r in caplog.records if r.name == "stt.shadow"]
    assert len(compare_lines) == 1
    assert "<failed>" in compare_lines[0].getMessage()


def test_dual_log_primary_failure_still_propagates(monkeypatch):
    """Primary raises — the call must still raise that exception even
    though the shadow ran. Shadow result is discarded."""
    from app.config import settings
    from app.services import stt, gemini_stt
    monkeypatch.setattr(settings, "STT_PROVIDER", "sarvam")
    monkeypatch.setattr(settings, "STT_DUAL_LOG", True)

    with patch.object(stt, "_sarvam_transcribe", new_callable=AsyncMock,
                      side_effect=stt.SttError("sarvam down")), \
         patch.object(gemini_stt, "transcribe_audio", new_callable=AsyncMock,
                      return_value="shadow ok"):
        try:
            _run(stt.transcribe_audio(b"\x00", filename="a.m4a"))
        except stt.SttError as e:
            assert "sarvam down" in str(e)
        else:
            raise AssertionError("expected SttError to propagate")
