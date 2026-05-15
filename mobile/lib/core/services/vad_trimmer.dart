/// Client-side Voice Activity Detection (VAD) silence trimmer.
///
/// Mirrors the server's `_compress_pcm_silence` logic in pure Dart.
/// Applied to accumulated denoised PCM **before** uploading for batch
/// transcription — strips silent stretches so:
///   1. Upload is smaller (saves bandwidth on Indian mobile networks).
///   2. Fewer audio tokens sent to Gemini (saves cost).
///   3. No silent gaps for the model to hallucinate into.
///
/// Algorithm: split PCM into 200 ms windows, compute RMS per window,
/// keep windows above threshold + 1-window (200 ms) padding on each
/// side of speech to preserve natural word boundaries.
library;

import 'dart:math' as math;
import 'dart:typed_data';

/// Result of a VAD trim operation.
class VadTrimResult {
  const VadTrimResult({
    required this.trimmedPcm,
    required this.originalMs,
    required this.keptMs,
    required this.windowsKept,
    required this.windowsTotal,
  });

  /// PCM bytes after silence removal.
  final Uint8List trimmedPcm;

  /// Duration of the original input audio in milliseconds.
  final int originalMs;

  /// Duration of the kept (speech) audio in milliseconds.
  final int keptMs;

  /// Number of 200 ms windows classified as speech (or padding).
  final int windowsKept;

  /// Total number of 200 ms windows in the input.
  final int windowsTotal;

  /// Fraction of audio retained (0.0–1.0).
  double get retainedRatio => originalMs > 0 ? keptMs / originalMs : 0.0;
}

class VadTrimmer {
  /// Default RMS threshold for speech detection. Matches the server's
  /// `STT_SILENCE_RMS_THRESHOLD` default (150). Phone mics with auto-gain
  /// produce ambient RMS of ~50–100; speech is typically 300–3000+.
  static const double defaultRmsThreshold = 150.0;

  /// Window size in milliseconds. 200 ms is short enough that a single
  /// word's pause boundaries don't bleed across windows, long enough
  /// that RMS averages out instantaneous spikes.
  static const int windowMs = 200;

  /// Number of padding windows to keep on each side of speech windows.
  /// Preserves natural word-boundary pauses so the audio sounds
  /// continuous to the model.
  static const int padWindows = 1;

  /// Sample rate (must match recording config: 16 kHz).
  static const int sampleRate = 16000;

  /// Minimum speech bytes to consider the recording non-silent.
  /// 600 ms of 16 kHz 16-bit mono = 19200 bytes. Below this we
  /// treat the whole recording as silence.
  static const int minSpeechBytes = 19200; // 0.6s × 32000 bytes/s

  /// Trim silence from raw PCM 16-bit mono audio.
  ///
  /// [pcmBytes] must be 16-bit signed little-endian mono PCM at 16 kHz
  /// (the format produced by the `record` package with our config).
  static VadTrimResult trim(
    Uint8List pcmBytes, {
    double rmsThreshold = defaultRmsThreshold,
  }) {
    final empty = Uint8List(0);

    if (pcmBytes.isEmpty) {
      return VadTrimResult(
        trimmedPcm: empty,
        originalMs: 0,
        keptMs: 0,
        windowsKept: 0,
        windowsTotal: 0,
      );
    }

    // Ensure even length (int16 requires pairs of bytes).
    final effectiveLength = pcmBytes.length & ~1;
    if (effectiveLength == 0) {
      return VadTrimResult(
        trimmedPcm: empty,
        originalMs: 0,
        keptMs: 0,
        windowsKept: 0,
        windowsTotal: 0,
      );
    }

    final samplesPerWindow = (sampleRate * windowMs) ~/ 1000; // 3200
    final bytesPerWindow = samplesPerWindow * 2; // 6400
    final totalSamples = effectiveLength ~/ 2;
    final nWindows = totalSamples ~/ samplesPerWindow;
    final originalMs = (effectiveLength ~/ 2 * 1000) ~/ sampleRate;

    if (nWindows == 0) {
      // Sub-window chunk — decide by whole-buffer RMS.
      final rms = _computeRms(pcmBytes, 0, effectiveLength);
      if (rms >= rmsThreshold) {
        return VadTrimResult(
          trimmedPcm: Uint8List.sublistView(pcmBytes, 0, effectiveLength),
          originalMs: originalMs,
          keptMs: originalMs,
          windowsKept: 1,
          windowsTotal: 1,
        );
      }
      return VadTrimResult(
        trimmedPcm: empty,
        originalMs: originalMs,
        keptMs: 0,
        windowsKept: 0,
        windowsTotal: 1,
      );
    }

    // Phase 1: classify each window as speech or silence by RMS.
    final isSpeech = List<bool>.filled(nWindows, false);
    for (int w = 0; w < nWindows; w++) {
      final byteOffset = w * bytesPerWindow;
      final rms = _computeRms(pcmBytes, byteOffset, bytesPerWindow);
      isSpeech[w] = rms >= rmsThreshold;
    }

    // Phase 2: dilate speech regions by padWindows on each side.
    final keep = List<bool>.filled(nWindows, false);
    for (int w = 0; w < nWindows; w++) {
      if (isSpeech[w]) {
        for (int d = -padWindows; d <= padWindows; d++) {
          final idx = w + d;
          if (idx >= 0 && idx < nWindows) {
            keep[idx] = true;
          }
        }
      }
    }

    // Phase 3: emit kept windows into output buffer.
    int windowsKept = 0;
    final outputBuilder = BytesBuilder(copy: false);
    for (int w = 0; w < nWindows; w++) {
      if (keep[w]) {
        windowsKept++;
        final start = w * bytesPerWindow;
        outputBuilder
            .add(Uint8List.sublistView(pcmBytes, start, start + bytesPerWindow));
      }
    }

    // Append trailing partial-window bytes if last full window is kept.
    final remainderStart = nWindows * bytesPerWindow;
    if (remainderStart < effectiveLength && nWindows > 0 && keep[nWindows - 1]) {
      outputBuilder.add(
          Uint8List.sublistView(pcmBytes, remainderStart, effectiveLength));
    }

    final output = outputBuilder.toBytes();
    final keptMs = (output.length ~/ 2 * 1000) ~/ sampleRate;

    return VadTrimResult(
      trimmedPcm: Uint8List.fromList(output),
      originalMs: originalMs,
      keptMs: keptMs,
      windowsKept: windowsKept,
      windowsTotal: nWindows,
    );
  }

  /// Compute RMS energy of int16 PCM samples in [buffer] starting at
  /// [byteOffset] for [byteLength] bytes.
  static double _computeRms(
      Uint8List buffer, int byteOffset, int byteLength) {
    final bd =
        ByteData.sublistView(buffer, byteOffset, byteOffset + byteLength);
    final sampleCount = byteLength ~/ 2;
    if (sampleCount == 0) return 0.0;

    double sumSq = 0.0;
    for (int i = 0; i < sampleCount; i++) {
      final sample = bd.getInt16(i * 2, Endian.little).toDouble();
      sumSq += sample * sample;
    }
    return math.sqrt(sumSq / sampleCount);
  }
}
