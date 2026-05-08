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


# ── Silence detection (RMS) ─────────────────────────────────────


def test_rms_zero_buffer_is_silent():
    from app.routers.sarvam import _chunk_rms, _is_chunk_silent
    pcm = b"\x00\x00" * 16000  # 1 s of true silence
    assert _chunk_rms(pcm) == 0.0
    assert _is_chunk_silent(pcm, threshold=200) is True


def test_rms_low_noise_is_silent():
    """Background noise at sustained ±100 has RMS ≈ 100 < 200 threshold
    → chunk is gated out (no Gemini call, no hallucination risk)."""
    from app.routers.sarvam import _chunk_rms, _is_chunk_silent
    samples = [100, -100] * 8000
    pcm = struct.pack(f"<{len(samples)}h", *samples)
    rms = _chunk_rms(pcm)
    assert 99 < rms < 101  # exact-ish 100
    assert _is_chunk_silent(pcm, threshold=200) is True


def test_rms_normal_speech_is_not_silent():
    """Sustained ±3000 has RMS ≈ 3000 ≫ 200 — chunk goes through to
    Gemini."""
    from app.routers.sarvam import _chunk_rms, _is_chunk_silent
    samples = [3000, -3000] * 8000
    pcm = struct.pack(f"<{len(samples)}h", *samples)
    assert _chunk_rms(pcm) > 2900
    assert _is_chunk_silent(pcm, threshold=200) is False


def test_rms_robust_against_single_spike():
    """RMS averages over the whole buffer, so one transient sample of
    ±20000 in an otherwise-silent chunk doesn't fool the gate.
    This is the key advantage over peak-only detection."""
    from app.routers.sarvam import _chunk_rms, _is_chunk_silent
    # 64000 samples of zero + 1 spike
    samples = [0] * 64000
    samples[0] = 20000
    pcm = struct.pack(f"<{len(samples)}h", *samples)
    rms = _chunk_rms(pcm)
    # √(20000² / 64000) ≈ 79 — well below threshold despite the spike.
    assert rms < 100
    assert _is_chunk_silent(pcm, threshold=200) is True


def test_rms_handles_empty_buffer():
    from app.routers.sarvam import _chunk_rms, _is_chunk_silent
    assert _chunk_rms(b"") == 0.0
    assert _is_chunk_silent(b"", threshold=200) is True


def test_rms_tolerates_odd_byte_length():
    """Odd-byte payloads from a malformed client envelope shouldn't
    crash — trailing byte is dropped and what's left is analysed."""
    from app.routers.sarvam import _chunk_rms
    pcm = struct.pack("<4h", 0, 0, 0, 0) + b"\xff"
    assert _chunk_rms(pcm) == 0.0


def test_silence_gate_reads_threshold_from_settings(monkeypatch):
    """Default threshold comes from settings.STT_SILENCE_RMS_THRESHOLD
    so we can tune in prod via env var without redeploying."""
    from app.config import settings
    from app.routers.sarvam import _is_chunk_silent
    # Build a chunk with RMS = 150
    samples = [150, -150] * 8000
    pcm = struct.pack(f"<{len(samples)}h", *samples)

    # With threshold=200 (default) → silent
    monkeypatch.setattr(settings, "STT_SILENCE_RMS_THRESHOLD", 200)
    assert _is_chunk_silent(pcm) is True

    # With threshold=100 → not silent
    monkeypatch.setattr(settings, "STT_SILENCE_RMS_THRESHOLD", 100)
    assert _is_chunk_silent(pcm) is False


def test_peak_amplitude_kept_for_diagnostic_logging():
    """Peak amplitude helper still exists (for diagnostic log lines
    during eval — the gating signal moved to RMS but operators may
    want both numbers when calibrating)."""
    from app.routers.sarvam import _chunk_peak_amplitude
    pcm = struct.pack("<4h", 0, 5000, 0, 0)
    assert _chunk_peak_amplitude(pcm) == 5000
