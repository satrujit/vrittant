/// Batch audio recording service for the record-then-transcribe flow.
///
/// Replaces [StreamingSttService] for the batch STT path. Records PCM
/// audio locally with on-device DTLN denoising and optional speaker
/// verification, but does NOT open a WebSocket — audio stays on-device
/// until the reporter stops recording, then the caller uploads the
/// accumulated buffer for server-side transcription.
///
/// Keeps: mic capture, DTLN denoising, noise detection, speaker
///   verification filter, audio buffer accumulation, WAV export.
/// Removes: WebSocket connection, reconnect machinery, live transcript
///   stream, message parsing, pending buffer.
library;

import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/foundation.dart' show debugPrint;
import 'package:record/record.dart';

import 'dtln_denoiser.dart';
import 'speaker_verification_service.dart';
import 'vad_trimmer.dart';

class BatchRecordingService {
  /// Called when ambient noise level changes between noisy/quiet.
  void Function(bool isNoisy)? onNoisyChanged;

  /// Called when speaker verification status changes (only when speaker
  /// filtering is active).
  void Function(bool isVerified, double similarity)? onSpeakerStatusChanged;

  final AudioRecorder _recorder = AudioRecorder();
  final DtlnDenoiser _denoiser = DtlnDenoiser();
  StreamSubscription? _audioSubscription;

  // Audio accumulation
  final List<int> _audioBuffer = [];

  // Noise detection
  static const int _noiseRmsThreshold = 500;
  static const int _noiseWindowSize = 25; // ~3s worth of chunks
  final List<double> _rmsWindow = [];
  bool _isNoisy = false;

  // Speaker verification
  bool _verifySpeaker = false;
  List<double>? _enrolledEmbedding;
  SpeakerVerificationService? _speakerSv;
  final List<int> _svBuffer = [];
  static const int _svBufferTarget = 16000; // 0.5s at 16kHz 16-bit mono
  bool _lastSpeakerVerified = true;
  bool _svBusy = false;

  bool _recording = false;
  bool get isRecording => _recording;

  /// Start recording. Captures PCM 16 kHz mono with DTLN denoising.
  /// Audio accumulates in an internal buffer — no network activity.
  Future<void> start({
    bool verifySpeaker = false,
    List<double>? enrolledEmbedding,
  }) async {
    if (_recording) throw BatchRecordingException('Already recording');

    _audioBuffer.clear();
    _rmsWindow.clear();
    _isNoisy = false;

    // Speaker verification setup
    _verifySpeaker = verifySpeaker && enrolledEmbedding != null;
    _enrolledEmbedding = enrolledEmbedding;
    _svBuffer.clear();
    _lastSpeakerVerified = true;

    if (_verifySpeaker) {
      _speakerSv = SpeakerVerificationService();
      final initOk = await _speakerSv!.init();
      if (!initOk) {
        debugPrint('[BatchRec] Speaker verification init failed — disabling');
        _verifySpeaker = false;
        _speakerSv?.dispose();
        _speakerSv = null;
      }
    }

    // Start recording PCM 16kHz mono
    final hasPermission = await _recorder.hasPermission();
    if (!hasPermission) {
      throw BatchRecordingException('Microphone permission denied');
    }

    final audioStream = await _recorder.startStream(
      const RecordConfig(
        encoder: AudioEncoder.pcm16bits,
        sampleRate: 16000,
        numChannels: 1,
        autoGain: true,
        echoCancel: true,
        noiseSuppress: true,
      ),
    );

    // Initialize on-device speech enhancement (fail-safe)
    await _denoiser.init();

    _audioSubscription = audioStream.listen(
      (data) {
        // Check ambient noise level on raw audio
        _updateNoiseDetection(data);

        // Apply DTLN denoising
        final enhanced = _denoiser.process(data);

        // Always accumulate denoised audio
        _audioBuffer.addAll(enhanced);

        // Speaker verification (advisory — doesn't gate recording,
        // just updates UI indicator)
        if (_verifySpeaker) {
          _handleSpeakerVerification(enhanced);
        }
      },
      onError: (error) {
        debugPrint('[BatchRec] Audio stream error: $error');
      },
    );

    _recording = true;
    debugPrint('[BatchRec] Recording started');
  }

  /// Stop recording and return accumulated audio as WAV bytes with
  /// client-side VAD trimming applied.
  ///
  /// Returns a [BatchRecordingResult] containing the trimmed WAV and
  /// stats. The caller uploads this to the batch transcribe endpoint.
  Future<BatchRecordingResult> stop() async {
    _recording = false;

    await _audioSubscription?.cancel();
    _audioSubscription = null;

    try {
      await _recorder.stop();
    } catch (_) {}
    _denoiser.reset();
    _rmsWindow.clear();
    _isNoisy = false;

    // Clean up speaker verification
    _svBuffer.clear();
    _speakerSv?.dispose();
    _speakerSv = null;
    _verifySpeaker = false;
    _enrolledEmbedding = null;
    _lastSpeakerVerified = true;
    _svBusy = false;

    if (_audioBuffer.isEmpty) {
      debugPrint('[BatchRec] Stopped — empty buffer');
      return BatchRecordingResult.empty();
    }

    final rawPcm = Uint8List.fromList(_audioBuffer);
    final rawSeconds = rawPcm.length / 32000; // 16kHz × 2 bytes

    // Client-side VAD trimming — strip silent stretches
    final vadResult = VadTrimmer.trim(rawPcm);
    final trimmedSeconds = vadResult.keptMs / 1000.0;

    debugPrint(
      '[BatchRec] Stopped — raw=${rawSeconds.toStringAsFixed(1)}s, '
      'trimmed=${trimmedSeconds.toStringAsFixed(1)}s '
      '(${(vadResult.retainedRatio * 100).toStringAsFixed(0)}% retained, '
      '${vadResult.windowsKept}/${vadResult.windowsTotal} windows)',
    );

    // Build WAV from trimmed PCM
    final wavBytes = _buildWav(vadResult.trimmedPcm);

    // Also build full (untrimmed) WAV for backup upload
    final fullWavBytes = _buildWav(rawPcm);

    _audioBuffer.clear();

    return BatchRecordingResult(
      trimmedWav: wavBytes,
      fullWav: fullWavBytes,
      rawSeconds: rawSeconds,
      trimmedSeconds: trimmedSeconds,
      retainedRatio: vadResult.retainedRatio,
      isSilent: vadResult.trimmedPcm.isEmpty ||
          vadResult.trimmedPcm.length < VadTrimmer.minSpeechBytes,
    );
  }

  /// Get the raw (untrimmed) WAV bytes without stopping.
  /// Used by the always-upload backup pipeline.
  Uint8List getRawWavBytes() {
    if (_audioBuffer.isEmpty) return Uint8List(0);
    return _buildWav(Uint8List.fromList(_audioBuffer));
  }

  void dispose() {
    _recording = false;
    _audioSubscription?.cancel();
    _audioSubscription = null;
    _recorder.dispose();
    _denoiser.dispose();
    _speakerSv?.dispose();
    _audioBuffer.clear();
    _rmsWindow.clear();
    _svBuffer.clear();
  }

  // ── WAV builder ──────────────────────────────────────────────────────

  static Uint8List _buildWav(Uint8List pcm) {
    if (pcm.isEmpty) return Uint8List(0);

    const sampleRate = 16000;
    const numChannels = 1;
    const bitsPerSample = 16;
    final dataSize = pcm.length;
    final fileSize = 36 + dataSize;

    final header = ByteData(44);
    // RIFF header
    header.setUint8(0, 0x52); // R
    header.setUint8(1, 0x49); // I
    header.setUint8(2, 0x46); // F
    header.setUint8(3, 0x46); // F
    header.setUint32(4, fileSize, Endian.little);
    header.setUint8(8, 0x57); // W
    header.setUint8(9, 0x41); // A
    header.setUint8(10, 0x56); // V
    header.setUint8(11, 0x45); // E
    // fmt sub-chunk
    header.setUint8(12, 0x66); // f
    header.setUint8(13, 0x6D); // m
    header.setUint8(14, 0x74); // t
    header.setUint8(15, 0x20); // (space)
    header.setUint32(16, 16, Endian.little);
    header.setUint16(20, 1, Endian.little); // PCM
    header.setUint16(22, numChannels, Endian.little);
    header.setUint32(24, sampleRate, Endian.little);
    header.setUint32(
        28, sampleRate * numChannels * bitsPerSample ~/ 8, Endian.little);
    header.setUint16(
        32, numChannels * bitsPerSample ~/ 8, Endian.little);
    header.setUint16(34, bitsPerSample, Endian.little);
    // data sub-chunk
    header.setUint8(36, 0x64); // d
    header.setUint8(37, 0x61); // a
    header.setUint8(38, 0x74); // t
    header.setUint8(39, 0x61); // a
    header.setUint32(40, dataSize, Endian.little);

    final wav = Uint8List(44 + dataSize);
    wav.setAll(0, header.buffer.asUint8List());
    wav.setAll(44, pcm);
    return wav;
  }

  // ── Noise detection ──────────────────────────────────────────────────

  void _updateNoiseDetection(List<int> pcmBytes) {
    final count = pcmBytes.length ~/ 2;
    if (count == 0) return;
    final bd = ByteData.sublistView(Uint8List.fromList(pcmBytes));
    double sumSq = 0;
    for (int i = 0; i < count; i++) {
      final s = bd.getInt16(i * 2, Endian.little).toDouble();
      sumSq += s * s;
    }
    final rms = (sumSq / count).isNaN ? 0.0 : (sumSq / count);
    _rmsWindow.add(rms > 0 ? rms.toDouble() : 0.0);
    if (_rmsWindow.length > _noiseWindowSize) _rmsWindow.removeAt(0);
    if (_rmsWindow.length >= _noiseWindowSize ~/ 2) {
      final sorted = List<double>.from(_rmsWindow)..sort();
      final noiseFloor = sorted[sorted.length ~/ 4];
      final wasNoisy = _isNoisy;
      _isNoisy = noiseFloor > _noiseRmsThreshold;
      if (_isNoisy != wasNoisy) onNoisyChanged?.call(_isNoisy);
    }
  }

  // ── Speaker verification (advisory) ──────────────────────────────────

  void _handleSpeakerVerification(Uint8List enhanced) {
    _svBuffer.addAll(enhanced);

    if (_svBuffer.length >= _svBufferTarget && !_svBusy) {
      final chunk = Uint8List.fromList(_svBuffer);
      _svBuffer.clear();

      if (!SpeakerVerificationService.hasSpeechEnergy(chunk)) return;

      _svBusy = true;
      _speakerSv!
          .verifyInIsolate(chunk, _enrolledEmbedding!)
          .timeout(const Duration(seconds: 3), onTimeout: () {
        debugPrint('[BatchRec] SV isolate timeout');
        return (true, 0.0);
      }).then((result) {
        _svBusy = false;
        final (verified, score) = result;
        if (verified != _lastSpeakerVerified) {
          _lastSpeakerVerified = verified;
          onSpeakerStatusChanged?.call(verified, score);
        }
      }).catchError((_) {
        _svBusy = false;
      });
    }
  }
}

/// Result of stopping a batch recording.
class BatchRecordingResult {
  const BatchRecordingResult({
    required this.trimmedWav,
    required this.fullWav,
    required this.rawSeconds,
    required this.trimmedSeconds,
    required this.retainedRatio,
    required this.isSilent,
  });

  factory BatchRecordingResult.empty() => BatchRecordingResult(
        trimmedWav: Uint8List(0),
        fullWav: Uint8List(0),
        rawSeconds: 0.0,
        trimmedSeconds: 0.0,
        retainedRatio: 0.0,
        isSilent: true,
      );

  /// VAD-trimmed WAV bytes for transcription upload.
  final Uint8List trimmedWav;

  /// Full (untrimmed) WAV bytes for the always-upload backup pipeline.
  final Uint8List fullWav;

  /// Total recording duration in seconds (before trimming).
  final double rawSeconds;

  /// Speech-only duration in seconds (after VAD trimming).
  final double trimmedSeconds;

  /// Fraction of audio retained by VAD (0.0–1.0).
  final double retainedRatio;

  /// True if the recording contained no detectable speech.
  final bool isSilent;
}

class BatchRecordingException implements Exception {
  final String message;
  const BatchRecordingException(this.message);

  @override
  String toString() => 'BatchRecordingException: $message';
}
