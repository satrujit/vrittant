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


# ── Sub-window VAD compression ──────────────────────────────────


def _make_pcm(seconds: float, amplitude: int, sample_rate: int = 16000) -> bytes:
    """Build a deterministic PCM buffer: alternating +amp/-amp samples
    of the requested duration. Useful for setting an exact RMS."""
    n = int(sample_rate * seconds)
    samples = [amplitude if i % 2 == 0 else -amplitude for i in range(n)]
    return struct.pack(f"<{n}h", *samples)


def test_vad_strips_silent_prefix(monkeypatch):
    """User's described scenario: 3 s of silence followed by 1 s of
    speech in a 4 s chunk. Whole-chunk RMS gate fails because the
    speech pulls the average above threshold; sub-window VAD strips
    the silent 3 s and only sends ~1 s to Gemini."""
    from app.config import settings
    from app.routers.sarvam import _compress_pcm_silence

    monkeypatch.setattr(settings, "STT_SILENCE_RMS_THRESHOLD", 200)

    silent = _make_pcm(3.0, 50)        # RMS ≈ 50, well below threshold
    speech = _make_pcm(1.0, 2000)      # RMS ≈ 2000, far above threshold
    pcm = silent + speech

    compressed, stats = _compress_pcm_silence(pcm)

    # Original: 4 s = 4000 ms
    assert stats["original_ms"] == 4000
    # Output should be roughly the 1 s of speech + 1 padding window
    # (200 ms) before it. Allow some slop for window-boundary effects.
    assert 1000 <= stats["kept_ms"] <= 1500
    # Compression ratio: kept significantly less than original
    assert stats["kept_ms"] < stats["original_ms"] * 0.5


def test_vad_strips_silent_suffix(monkeypatch):
    """Mirror of the prefix case: 1 s speech then 3 s silence."""
    from app.config import settings
    from app.routers.sarvam import _compress_pcm_silence

    monkeypatch.setattr(settings, "STT_SILENCE_RMS_THRESHOLD", 200)

    speech = _make_pcm(1.0, 2000)
    silent = _make_pcm(3.0, 50)
    pcm = speech + silent

    compressed, stats = _compress_pcm_silence(pcm)
    assert stats["original_ms"] == 4000
    assert 1000 <= stats["kept_ms"] <= 1500


def test_vad_keeps_short_pause_between_words(monkeypatch):
    """A typical word-pause is 100-200 ms. The 200 ms padding around
    each speech window means short inter-word pauses are preserved
    in the compressed output (natural cadence for the model)."""
    from app.config import settings
    from app.routers.sarvam import _compress_pcm_silence

    monkeypatch.setattr(settings, "STT_SILENCE_RMS_THRESHOLD", 200)

    word = _make_pcm(0.4, 2000)        # 400 ms of speech
    pause = _make_pcm(0.2, 50)          # 200 ms of pause
    pcm = word + pause + word + pause + word  # 3 words separated by pauses

    compressed, stats = _compress_pcm_silence(pcm)
    # All speech kept; short inter-word pauses kept too because they
    # fall within the dilation window of adjacent speech.
    assert stats["kept_ms"] >= stats["original_ms"] * 0.85


def test_vad_full_silence_collapses_to_empty(monkeypatch):
    """A chunk that is silent throughout produces an empty output —
    handler treats this as silent_dropped and skips the API call."""
    from app.config import settings
    from app.routers.sarvam import _compress_pcm_silence

    monkeypatch.setattr(settings, "STT_SILENCE_RMS_THRESHOLD", 200)

    pcm = _make_pcm(4.0, 50)  # 4 s of low-amplitude noise

    compressed, stats = _compress_pcm_silence(pcm)
    assert compressed == b""
    assert stats["kept_ms"] == 0
    assert stats["windows_kept"] == 0


def test_vad_full_speech_passes_through(monkeypatch):
    """A chunk that's speech throughout passes through almost unchanged
    (every window is kept; padding doesn't change the output because
    everything is already speech)."""
    from app.config import settings
    from app.routers.sarvam import _compress_pcm_silence

    monkeypatch.setattr(settings, "STT_SILENCE_RMS_THRESHOLD", 200)

    pcm = _make_pcm(4.0, 2000)

    compressed, stats = _compress_pcm_silence(pcm)
    # Allow tiny boundary loss but expect ~100% retention
    assert stats["kept_ms"] >= stats["original_ms"] * 0.95


def test_vad_handles_empty_input(monkeypatch):
    from app.routers.sarvam import _compress_pcm_silence
    compressed, stats = _compress_pcm_silence(b"")
    assert compressed == b""
    assert stats["original_ms"] == 0
    assert stats["kept_ms"] == 0


def test_vad_threshold_reads_from_settings(monkeypatch):
    """Threshold defaults to settings.STT_SILENCE_RMS_THRESHOLD,
    overridable via env var without redeploy."""
    from app.config import settings
    from app.routers.sarvam import _compress_pcm_silence

    pcm = _make_pcm(2.0, 150)  # RMS ≈ 150

    monkeypatch.setattr(settings, "STT_SILENCE_RMS_THRESHOLD", 200)
    _, stats_strict = _compress_pcm_silence(pcm)
    assert stats_strict["kept_ms"] == 0  # 150 < 200, all silent

    monkeypatch.setattr(settings, "STT_SILENCE_RMS_THRESHOLD", 100)
    _, stats_loose = _compress_pcm_silence(pcm)
    assert stats_loose["kept_ms"] > 0  # 150 > 100, all speech
