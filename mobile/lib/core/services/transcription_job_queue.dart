/// Persistent background transcription job queue.
///
/// Ensures transcription continues even if the reporter navigates away
/// or closes the app. Jobs are persisted to SharedPreferences + local
/// files. On app reopen, pending jobs are automatically resumed.
///
/// Flow:
///   1. After recording stops, caller saves WAV to a temp file and
///      enqueues a job (paragraph ID + file path + story context).
///   2. Worker processes the job: uploads WAV → gets transcript.
///   3. On success, calls the provided callback to insert the transcript
///      into the story's paragraph list.
///   4. On repeated failure (3 attempts), marks the job as failed so the
///      UI can show a retry option.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart' show debugPrint;
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_service.dart';

/// Status of a transcription job.
enum TranscriptionJobStatus { pending, inProgress, completed, failed }

/// A single transcription job persisted to disk.
class TranscriptionJob {
  final String id;
  final String paragraphId;
  final String wavFilePath;
  final String? storyId;
  final String languageCode;
  final int createdAtMs;
  int attempts;
  TranscriptionJobStatus status;
  String? transcript; // populated on success

  TranscriptionJob({
    required this.id,
    required this.paragraphId,
    required this.wavFilePath,
    this.storyId,
    this.languageCode = 'od-IN',
    required this.createdAtMs,
    this.attempts = 0,
    this.status = TranscriptionJobStatus.pending,
    this.transcript,
  });

  Map<String, dynamic> toJson() => {
        'id': id,
        'paragraph_id': paragraphId,
        'wav_file_path': wavFilePath,
        'story_id': storyId,
        'language_code': languageCode,
        'created_at_ms': createdAtMs,
        'attempts': attempts,
        'status': status.name,
        'transcript': transcript,
      };

  factory TranscriptionJob.fromJson(Map<String, dynamic> j) =>
      TranscriptionJob(
        id: j['id'] as String,
        paragraphId: j['paragraph_id'] as String,
        wavFilePath: j['wav_file_path'] as String,
        storyId: j['story_id'] as String?,
        languageCode: (j['language_code'] as String?) ?? 'od-IN',
        createdAtMs: j['created_at_ms'] as int,
        attempts: (j['attempts'] as int?) ?? 0,
        status: TranscriptionJobStatus.values.firstWhere(
          (s) => s.name == j['status'],
          orElse: () => TranscriptionJobStatus.pending,
        ),
        transcript: j['transcript'] as String?,
      );
}

/// Callback signature for delivering completed transcripts.
typedef TranscriptDeliveryCallback = void Function(
  String paragraphId,
  String transcript,
  String? storyId,
);

class TranscriptionJobQueue {
  TranscriptionJobQueue._(this._apiService);

  static TranscriptionJobQueue? _instance;

  /// Singleton accessor.
  static TranscriptionJobQueue instance(ApiService apiService) {
    return _instance ??= TranscriptionJobQueue._(apiService);
  }

  /// Reset singleton (for testing).
  static void resetInstance() {
    _instance?._drainTimer?.cancel();
    _instance = null;
  }

  final ApiService _apiService;

  static const String _prefsKey = 'transcription_job_queue_v1';
  static const String _queueSubdir = 'transcription_jobs';
  static const int _maxAttempts = 3;
  static const Duration _retryDelay = Duration(seconds: 5);

  Timer? _drainTimer;
  bool _draining = false;
  final List<TranscriptionJob> _jobs = [];

  /// Callback invoked when a transcription completes successfully.
  /// The provider registers this on startup so completed jobs can
  /// be wired into the story state even after app restart.
  TranscriptDeliveryCallback? onTranscriptReady;

  /// Stream of completed job IDs for UI notifications.
  final _completedController = StreamController<TranscriptionJob>.broadcast();
  Stream<TranscriptionJob> get completedJobs => _completedController.stream;

  /// Whether any jobs are currently in progress or pending.
  bool get hasPendingJobs =>
      _jobs.any((j) =>
          j.status == TranscriptionJobStatus.pending ||
          j.status == TranscriptionJobStatus.inProgress);

  /// Get all pending/in-progress jobs (for UI display).
  List<TranscriptionJob> get pendingJobs => _jobs
      .where((j) =>
          j.status == TranscriptionJobStatus.pending ||
          j.status == TranscriptionJobStatus.inProgress)
      .toList();

  /// Get job by paragraph ID (to check status from provider).
  TranscriptionJob? jobForParagraph(String paragraphId) {
    try {
      return _jobs.firstWhere((j) => j.paragraphId == paragraphId);
    } catch (_) {
      return null;
    }
  }

  // ---------------------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------------------

  /// Enqueue a new transcription job. Saves WAV to a persistent location
  /// and starts processing.
  Future<String> enqueue({
    required String paragraphId,
    required List<int> wavBytes,
    String? storyId,
    String languageCode = 'od-IN',
  }) async {
    final jobId =
        '${DateTime.now().millisecondsSinceEpoch}_${paragraphId.hashCode.abs()}';

    // Save WAV to persistent queue directory
    final queueDir = await _ensureQueueDir();
    final wavPath = '${queueDir.path}/$jobId.wav';
    await File(wavPath).writeAsBytes(wavBytes);

    final job = TranscriptionJob(
      id: jobId,
      paragraphId: paragraphId,
      wavFilePath: wavPath,
      storyId: storyId,
      languageCode: languageCode,
      createdAtMs: DateTime.now().millisecondsSinceEpoch,
    );

    _jobs.add(job);
    await _persist();
    _scheduleDrain();

    debugPrint('[TranscriptionQueue] Enqueued job $jobId for paragraph $paragraphId');
    return jobId;
  }

  /// Load persisted jobs and resume processing. Call on app startup.
  Future<void> resumePendingJobs() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_prefsKey);
    if (raw == null || raw.isEmpty) return;

    try {
      final list = (jsonDecode(raw) as List).cast<Map<String, dynamic>>();
      _jobs.clear();
      for (final j in list) {
        final job = TranscriptionJob.fromJson(j);
        // Only resume pending/in-progress jobs (in-progress was interrupted)
        if (job.status == TranscriptionJobStatus.inProgress) {
          job.status = TranscriptionJobStatus.pending;
        }
        // Verify WAV file still exists
        if (job.status == TranscriptionJobStatus.pending &&
            !await File(job.wavFilePath).exists()) {
          debugPrint('[TranscriptionQueue] WAV missing for ${job.id} — dropping');
          continue;
        }
        _jobs.add(job);
      }
      debugPrint(
          '[TranscriptionQueue] Resumed ${_jobs.where((j) => j.status == TranscriptionJobStatus.pending).length} pending jobs');
    } catch (e) {
      debugPrint('[TranscriptionQueue] Failed to parse persisted jobs: $e');
    }

    if (_jobs.any((j) => j.status == TranscriptionJobStatus.pending)) {
      _scheduleDrain();
    }
  }

  /// Remove completed/failed jobs older than 1 hour.
  Future<void> cleanup() async {
    final cutoff =
        DateTime.now().millisecondsSinceEpoch - const Duration(hours: 1).inMilliseconds;
    _jobs.removeWhere((j) {
      if ((j.status == TranscriptionJobStatus.completed ||
              j.status == TranscriptionJobStatus.failed) &&
          j.createdAtMs < cutoff) {
        // Clean up WAV file
        File(j.wavFilePath).delete().ignore();
        return true;
      }
      return false;
    });
    await _persist();
  }

  void dispose() {
    _drainTimer?.cancel();
    _completedController.close();
  }

  // ---------------------------------------------------------------------------
  // Worker
  // ---------------------------------------------------------------------------

  void _scheduleDrain() {
    if (_drainTimer?.isActive ?? false) return;
    _drainTimer = Timer(const Duration(milliseconds: 100), _drain);
  }

  Future<void> _drain() async {
    if (_draining) return;
    _draining = true;

    try {
      final pending = _jobs
          .where((j) => j.status == TranscriptionJobStatus.pending)
          .toList();

      for (final job in pending) {
        job.status = TranscriptionJobStatus.inProgress;
        job.attempts++;
        await _persist();

        try {
          final wavBytes = await File(job.wavFilePath).readAsBytes();
          final result = await _apiService.transcribeBatch(
            wavBytes: wavBytes.toList(),
            languageCode: job.languageCode,
          );

          final transcript =
              ((result['transcript'] as String?) ?? '').trim();

          if (transcript.isEmpty && result['status'] == 'silence') {
            // Silent recording — mark complete with empty transcript
            job.status = TranscriptionJobStatus.completed;
            job.transcript = '';
          } else {
            job.status = TranscriptionJobStatus.completed;
            job.transcript = transcript;
          }

          await _persist();

          // Deliver transcript
          if (transcript.isNotEmpty) {
            onTranscriptReady?.call(job.paragraphId, transcript, job.storyId);
            _completedController.add(job);
          }

          // Clean up WAV file
          File(job.wavFilePath).delete().ignore();

          debugPrint(
              '[TranscriptionQueue] Job ${job.id} completed '
              '(${transcript.length} chars)');
        } catch (e) {
          debugPrint(
              '[TranscriptionQueue] Job ${job.id} attempt ${job.attempts} '
              'failed: $e');

          if (job.attempts >= _maxAttempts) {
            job.status = TranscriptionJobStatus.failed;
            debugPrint(
                '[TranscriptionQueue] Job ${job.id} permanently failed');
          } else {
            job.status = TranscriptionJobStatus.pending;
            // Delay before retry
            await Future.delayed(_retryDelay);
          }
          await _persist();
        }
      }
    } finally {
      _draining = false;
    }

    // Schedule another pass if there are still pending jobs
    if (_jobs.any((j) => j.status == TranscriptionJobStatus.pending)) {
      _drainTimer = Timer(_retryDelay, _drain);
    }
  }

  // ---------------------------------------------------------------------------
  // Persistence
  // ---------------------------------------------------------------------------

  Future<void> _persist() async {
    final prefs = await SharedPreferences.getInstance();
    final json = _jobs.map((j) => j.toJson()).toList();
    await prefs.setString(_prefsKey, jsonEncode(json));
  }

  Future<Directory> _ensureQueueDir() async {
    final appDir = await getApplicationDocumentsDirectory();
    final dir = Directory('${appDir.path}/$_queueSubdir');
    if (!await dir.exists()) {
      await dir.create(recursive: true);
    }
    return dir;
  }
}
