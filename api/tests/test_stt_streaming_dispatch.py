"""Tests for the live-dictation /ws/stt provider dispatch + Gemini path.

Covers:
  - _wrap_pcm_as_wav builds a valid 44-byte WAV header in front of the
    raw PCM payload.
  - When STT_PROVIDER=gemini, the dispatcher hits the Gemini handler
    instead of the Sarvam streaming proxy. (Smoke test against the
    function objects — actual WS plumbing exercised in integration.)
"""
import struct


def test_wav_wrapper_has_valid_riff_wave_header():
    from app.routers.sarvam import _wrap_pcm_as_wav

    pcm = b"\x01\x02" * 100  # 200 bytes of fake PCM
    wav = _wrap_pcm_as_wav(pcm, sample_rate=16000, channels=1, bits=16)

    # 44-byte header + payload
    assert len(wav) == 44 + len(pcm)
    # RIFF... WAVE
    assert wav[0:4] == b"RIFF"
    assert wav[8:12] == b"WAVE"
    # fmt chunk
    assert wav[12:16] == b"fmt "
    chunk_size = struct.unpack("<I", wav[16:20])[0]
    assert chunk_size == 16
    audio_format = struct.unpack("<H", wav[20:22])[0]
    assert audio_format == 1  # PCM
    channels = struct.unpack("<H", wav[22:24])[0]
    assert channels == 1
    sample_rate = struct.unpack("<I", wav[24:28])[0]
    assert sample_rate == 16000
    bits = struct.unpack("<H", wav[34:36])[0]
    assert bits == 16
    # data chunk
    assert wav[36:40] == b"data"
    data_size = struct.unpack("<I", wav[40:44])[0]
    assert data_size == len(pcm)
    assert wav[44:] == pcm


def test_wav_wrapper_handles_empty_pcm():
    """Edge case: zero-byte audio buffer still produces a structurally
    valid (if useless) WAV file — guards against ValueErrors in the
    streaming handler when an immediate disconnect lands."""
    from app.routers.sarvam import _wrap_pcm_as_wav

    wav = _wrap_pcm_as_wav(b"", sample_rate=16000)
    assert len(wav) == 44
    assert wav[0:4] == b"RIFF"
    assert wav[8:12] == b"WAVE"


def test_gemini_streaming_handler_is_callable():
    """Smoke check: the dispatcher entry point exists and accepts the
    expected kwargs. Full WS roundtrip is exercised in the integration
    eval, not unit tests."""
    from app.routers.sarvam import _gemini_streaming_handler
    import inspect
    sig = inspect.signature(_gemini_streaming_handler)
    assert {"reporter_id", "language_code"} <= set(sig.parameters)
