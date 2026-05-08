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


# ── Silence detection ───────────────────────────────────────────


def test_peak_amplitude_zero_buffer_is_silent():
    from app.routers.sarvam import _chunk_peak_amplitude, _is_chunk_silent
    pcm = b"\x00\x00" * 16000  # 1 s of true silence at 16 kHz
    assert _chunk_peak_amplitude(pcm) == 0
    assert _is_chunk_silent(pcm) is True


def test_peak_amplitude_low_noise_is_silent():
    """Background noise at peak ≈±200 (well below the 500 threshold)
    is treated as silence and the chunk is gated out."""
    from app.routers.sarvam import _is_chunk_silent
    # Build PCM where every sample is +/- 200 — peak amplitude 200
    # < 500 threshold. Use struct to avoid endian surprises.
    samples = [200, -200] * 8000  # 1 s of low-noise oscillation
    pcm = struct.pack(f"<{len(samples)}h", *samples)
    assert _is_chunk_silent(pcm) is True


def test_peak_amplitude_normal_speech_is_not_silent():
    """Normal speech regularly hits peak amplitudes >2000 — these
    chunks must NOT be gated out."""
    from app.routers.sarvam import _is_chunk_silent, _chunk_peak_amplitude
    samples = [3000, -3000] * 8000  # speech-volume oscillation
    pcm = struct.pack(f"<{len(samples)}h", *samples)
    assert _chunk_peak_amplitude(pcm) >= 3000
    assert _is_chunk_silent(pcm) is False


def test_peak_amplitude_handles_empty_buffer():
    from app.routers.sarvam import _chunk_peak_amplitude, _is_chunk_silent
    assert _chunk_peak_amplitude(b"") == 0
    assert _is_chunk_silent(b"") is True


def test_peak_amplitude_tolerates_odd_byte_length():
    """A buffer with an odd byte count (incomplete sample at the end)
    shouldn't crash — drop the trailing byte and check what's left.
    Real-world cause: a JSON envelope's base64 decoded to an odd
    number of bytes (which shouldn't happen with PCM 16-bit, but
    defending the boundary is cheap insurance)."""
    from app.routers.sarvam import _chunk_peak_amplitude
    # 4 valid samples (peak 0) + 1 trailing byte
    pcm = struct.pack("<4h", 0, 0, 0, 0) + b"\xff"
    assert _chunk_peak_amplitude(pcm) == 0


def test_peak_amplitude_detects_min_int16():
    """The sample value -32768 has |x|=32768 which doesn't fit in
    int16 — peak detection must handle this without overflow."""
    from app.routers.sarvam import _chunk_peak_amplitude
    pcm = struct.pack("<4h", -32768, -32768, -32768, -32768)
    assert _chunk_peak_amplitude(pcm) == 32768
