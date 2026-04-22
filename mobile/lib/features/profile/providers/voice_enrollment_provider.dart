import 'dart:async';
import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:record/record.dart';

import '../../../core/services/api_service.dart';
import '../../../core/services/enrollment_storage.dart';
import '../../../core/services/speaker_verification_service.dart';

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

class VoiceEnrollmentState {
  final bool isEnrolled;
  final bool isLoading;
  final bool isRecording;
  final int sampleCount;
  final int targetSamples;
  final String? error;

  /// Result of the last voice test (null = not tested yet).
  final ({bool passed, double score})? testResult;

  const VoiceEnrollmentState({
    this.isEnrolled = false,
    this.isLoading = false,
    this.isRecording = false,
    this.sampleCount = 0,
    this.targetSamples = 3,
    this.error,
    this.testResult,
  });

  VoiceEnrollmentState copyWith({
    bool? isEnrolled,
    bool? isLoading,
    bool? isRecording,
    int? sampleCount,
    String? error,
    bool clearError = false,
    ({bool passed, double score})? testResult,
    bool clearTestResult = false,
  }) {
    return VoiceEnrollmentState(
      isEnrolled: isEnrolled ?? this.isEnrolled,
      isLoading: isLoading ?? this.isLoading,
      isRecording: isRecording ?? this.isRecording,
      sampleCount: sampleCount ?? this.sampleCount,
      targetSamples: targetSamples,
      error: clearError ? null : (error ?? this.error),
      testResult: clearTestResult ? null : (testResult ?? this.testResult),
    );
  }
}

// ---------------------------------------------------------------------------
// Notifier
// ---------------------------------------------------------------------------

class VoiceEnrollmentNotifier extends Notifier<VoiceEnrollmentState> {
  late final ApiService _api;
  final SpeakerVerificationService _sv = SpeakerVerificationService();
  final AudioRecorder _recorder = AudioRecorder();

  /// In-progress enrollment embeddings collected so far (before averaging).
  final List<List<double>> _enrollmentEmbeddings = [];

  /// Averaged enrollment embedding (after all samples are collected).
  List<double>? _enrolledEmbedding;

  // Audio accumulation during enrollment recording.
  final List<int> _audioBuffer = [];
  StreamSubscription? _audioSub;

  @override
  VoiceEnrollmentState build() {
    _api = ref.read(apiServiceProvider);
    // Kick off an async status check (non-blocking).
    Future.microtask(() => checkStatus());
    return const VoiceEnrollmentState(isLoading: true);
  }

  // -----------------------------------------------------------------------
  // Status
  // -----------------------------------------------------------------------

  /// Check whether the user has an existing enrollment (local first, then
  /// backend fallback for device migration).
  Future<void> checkStatus() async {
    state = state.copyWith(isLoading: true, clearError: true);

    try {
      // 1. Initialise the ONNX model (must succeed before any recording)
      final initOk = await _sv.init();
      if (!initOk) {
        state = state.copyWith(
          isLoading: false,
          error: 'Failed to initialise voice model',
        );
        return;
      }

      // 2. Check local storage
      final local = await EnrollmentStorage.load();
      if (local != null && local.embedding.isNotEmpty) {
        _enrolledEmbedding = local.embedding;
        state = state.copyWith(
          isLoading: false,
          isEnrolled: true,
          sampleCount: local.sampleCount,
        );
        return;
      }

      // 3. Fallback: try backend
      try {
        final remote = await _api.getEnrollment();
        if (remote != null) {
          _enrolledEmbedding = remote.embedding;
          await EnrollmentStorage.save(
            embedding: remote.embedding,
            sampleCount: remote.sampleCount,
          );
          state = state.copyWith(
            isLoading: false,
            isEnrolled: true,
            sampleCount: remote.sampleCount,
          );
          return;
        }
      } catch (_) {
        // Backend unreachable — not critical.
      }

      state = state.copyWith(isLoading: false, isEnrolled: false);
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: 'Failed to initialise voice model',
      );
    }
  }

  // -----------------------------------------------------------------------
  // Recording an enrollment sample
  // -----------------------------------------------------------------------

  /// Start recording an enrollment voice sample (5–10 seconds).
  Future<void> startRecording() async {
    if (state.isRecording) return;

    // Ensure model is initialised before recording
    if (!_sv.isInitialized) {
      final ok = await _sv.init();
      if (!ok) {
        state = state.copyWith(
          error: 'Voice model not ready — please restart the app',
        );
        return;
      }
    }

    final hasPermission = await _recorder.hasPermission();
    if (!hasPermission) {
      state = state.copyWith(error: 'Microphone permission denied');
      return;
    }

    _audioBuffer.clear();
    state = state.copyWith(isRecording: true, clearError: true);

    final stream = await _recorder.startStream(
      const RecordConfig(
        encoder: AudioEncoder.pcm16bits,
        sampleRate: 16000,
        numChannels: 1,
        autoGain: true,
        echoCancel: true,
        noiseSuppress: true,
      ),
    );

    _audioSub = stream.listen((data) {
      _audioBuffer.addAll(data);
    });
  }

  /// Stop recording and process the captured enrollment sample.
  Future<void> stopRecording() async {
    if (!state.isRecording) return;

    await _audioSub?.cancel();
    _audioSub = null;
    try {
      await _recorder.stop();
    } catch (_) {}

    state = state.copyWith(isRecording: false, isLoading: true);

    // Minimum 3 seconds of audio (16kHz * 2 bytes * 3s = 96000 bytes)
    if (_audioBuffer.length < 96000) {
      state = state.copyWith(
        isLoading: false,
        error: 'Recording too short — please record at least 3 seconds',
      );
      return;
    }

    // Extract embedding
    final pcmBytes = Uint8List.fromList(_audioBuffer);
    final embedding = _sv.extractEmbedding(pcmBytes);

    if (embedding.isEmpty) {
      state = state.copyWith(
        isLoading: false,
        error: 'Could not extract voice features — please try again',
      );
      return;
    }

    // Store this sample's embedding
    _enrollmentEmbeddings.add(embedding.toList());
    final count = _enrollmentEmbeddings.length;

    if (count >= state.targetSamples) {
      // All samples collected — compute average and save
      _enrolledEmbedding =
          SpeakerVerificationService.averageEmbeddings(_enrollmentEmbeddings);
      await EnrollmentStorage.save(
        embedding: _enrolledEmbedding!,
        sampleCount: count,
      );
      // Sync to backend (best-effort)
      _syncToBackend(count);

      state = state.copyWith(
        isLoading: false,
        isEnrolled: true,
        sampleCount: count,
      );
    } else {
      state = state.copyWith(
        isLoading: false,
        sampleCount: count,
      );
    }
  }

  // -----------------------------------------------------------------------
  // Testing the enrollment
  // -----------------------------------------------------------------------

  /// Record a short clip and verify it against the enrolled voice.
  Future<void> startTestRecording() async {
    await startRecording();
  }

  /// Stop the test recording and report the verification result.
  Future<void> stopTestRecording() async {
    if (!state.isRecording) return;

    await _audioSub?.cancel();
    _audioSub = null;
    try {
      await _recorder.stop();
    } catch (_) {}

    state = state.copyWith(
      isRecording: false,
      isLoading: true,
      clearTestResult: true,
    );

    if (_audioBuffer.length < 32000 || _enrolledEmbedding == null) {
      state = state.copyWith(
        isLoading: false,
        error: 'Recording too short for voice test',
      );
      return;
    }

    final pcmBytes = Uint8List.fromList(_audioBuffer);
    final (passed, score) = _sv.verify(pcmBytes, _enrolledEmbedding!);

    state = state.copyWith(
      isLoading: false,
      testResult: (passed: passed, score: score),
    );
  }

  // -----------------------------------------------------------------------
  // Delete enrollment
  // -----------------------------------------------------------------------

  Future<void> deleteEnrollment() async {
    state = state.copyWith(isLoading: true, clearError: true);

    _enrollmentEmbeddings.clear();
    _enrolledEmbedding = null;

    await EnrollmentStorage.clear();

    // Best-effort backend delete
    try {
      await _api.deleteEnrollment();
    } catch (_) {}

    state = const VoiceEnrollmentState(isLoading: false, isEnrolled: false);
  }

  // -----------------------------------------------------------------------
  // Public accessor for the enrolled embedding (used by STT pipeline)
  // -----------------------------------------------------------------------

  /// The current enrolled embedding, or null if not enrolled.
  List<double>? get enrolledEmbedding => _enrolledEmbedding;

  // -----------------------------------------------------------------------
  // Internal helpers
  // -----------------------------------------------------------------------

  void _syncToBackend(int sampleCount) async {
    if (_enrolledEmbedding == null) return;
    try {
      await _api.syncEnrollment(_enrolledEmbedding!, sampleCount);
    } catch (_) {
      // Sync failure is non-critical — the embedding is persisted locally.
    }
  }
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

final voiceEnrollmentProvider =
    NotifierProvider<VoiceEnrollmentNotifier, VoiceEnrollmentState>(
  VoiceEnrollmentNotifier.new,
);
