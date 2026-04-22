import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_service.dart';

/// Persistent fire-and-forget upload queue for audio recordings.
///
/// Why this exists: the realtime transcript path (live WebSocket → Sarvam)
/// is for the user. This queue is the silent safety net — every recording's
/// raw audio is uploaded to the server so that if the live path returned
/// nothing (bad network, Sarvam latency, mid-stream cancel) the server can
/// re-transcribe in the background. Reporter never sees this happen.
///
/// Behaviour:
///   * Caller hands over a temp WAV/M4A file path + metadata; queue takes
///     ownership of the file (moves it into a private queue dir so the
///     OS doesn't clean it up before upload finishes).
///   * Worker drains the queue with exponential backoff. Each entry is
///     retried up to [_maxAttempts] times — after that we drop it on the
///     floor (the server-side sweep won't have anything to retry, but the
///     user already has the live transcript so nothing is lost from their
///     perspective).
///   * Queue state is persisted to SharedPreferences so kills / crashes
///     don't lose pending uploads.
///
/// Backward compat: this class is *additive*. If the API endpoint is
/// missing (404 against an old backend) the entry is dropped — the user's
/// live transcript is unaffected.
class AudioUploadQueue {
  AudioUploadQueue._(this._apiService);

  static AudioUploadQueue? _instance;

  /// Singleton accessor — wired up once with the API service.
  static AudioUploadQueue instance(ApiService apiService) {
    return _instance ??= AudioUploadQueue._(apiService);
  }

  final ApiService _apiService;

  static const String _prefsKey = 'audio_upload_queue_v1';
  static const String _queueSubdir = 'audio_upload_queue';
  static const int _maxAttempts = 5;

  /// Min delay between worker passes when there are entries to send.
  static const Duration _minBackoff = Duration(seconds: 2);
  static const Duration _maxBackoff = Duration(minutes: 5);

  Timer? _drainTimer;
  bool _draining = false;

  // ---------------------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------------------

  /// Enqueue a recording for upload.
  ///
  /// [sourceFilePath] is moved into the queue's private dir so the caller
  /// can stop worrying about it. If the move fails (file gone, permission
  /// denied) the entry is silently dropped.
  Future<void> enqueue({
    required String sourceFilePath,
    required String storyId,
    required String paragraphId,
    required bool isAttachment,
    String languageCode = 'od-IN',
  }) async {
    final queueDir = await _ensureQueueDir();
    final filename = _filenameFromPath(sourceFilePath);
    final destPath = '${queueDir.path}/${DateTime.now().millisecondsSinceEpoch}_$filename';

    try {
      // Try a rename first (instant if same filesystem); fall back to copy.
      try {
        await File(sourceFilePath).rename(destPath);
      } on FileSystemException {
        await File(sourceFilePath).copy(destPath);
        try { await File(sourceFilePath).delete(); } catch (_) {}
      }
    } catch (e) {
      debugPrint('[AudioUploadQueue] failed to move source file: $e');
      return;
    }

    final entry = _QueueEntry(
      filePath: destPath,
      filename: filename,
      storyId: storyId,
      paragraphId: paragraphId,
      isAttachment: isAttachment,
      languageCode: languageCode,
      attempts: 0,
      enqueuedAt: DateTime.now(),
    );

    await _persistAdd(entry);
    _scheduleDrain(_minBackoff);
  }

  /// Kick the worker on app start so any leftover entries get sent.
  Future<void> resumePendingOnStartup() async {
    final entries = await _loadAll();
    if (entries.isEmpty) return;
    debugPrint('[AudioUploadQueue] resuming with ${entries.length} pending');
    _scheduleDrain(_minBackoff);
  }

  /// Drop all queued audio files & metadata. For tests / debugging.
  Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_prefsKey);
    final dir = await _ensureQueueDir();
    if (await dir.exists()) {
      await for (final f in dir.list()) {
        try { await f.delete(); } catch (_) {}
      }
    }
  }

  // ---------------------------------------------------------------------------
  // Worker
  // ---------------------------------------------------------------------------

  void _scheduleDrain(Duration delay) {
    _drainTimer?.cancel();
    _drainTimer = Timer(delay, _drainOnce);
  }

  Future<void> _drainOnce() async {
    if (_draining) return;
    _draining = true;
    try {
      while (true) {
        final entries = await _loadAll();
        if (entries.isEmpty) return;

        final entry = entries.first;
        final ok = await _trySend(entry);
        if (ok) {
          await _persistRemove(entry);
          await _deleteFileQuiet(entry.filePath);
          continue;
        }

        // Failed: increment attempts; either drop or reschedule with backoff.
        final next = entry.copyWith(attempts: entry.attempts + 1);
        if (next.attempts >= _maxAttempts) {
          debugPrint(
            '[AudioUploadQueue] giving up on ${next.filename} after ${next.attempts} attempts',
          );
          await _persistRemove(entry);
          await _deleteFileQuiet(entry.filePath);
          continue;
        }

        await _persistReplace(entry, next);

        final backoff = _backoffFor(next.attempts);
        debugPrint(
          '[AudioUploadQueue] retry #${next.attempts} for ${next.filename} in ${backoff.inSeconds}s',
        );
        _scheduleDrain(backoff);
        return;
      }
    } finally {
      _draining = false;
    }
  }

  Future<bool> _trySend(_QueueEntry entry) async {
    final file = File(entry.filePath);
    if (!await file.exists()) {
      debugPrint('[AudioUploadQueue] file missing, dropping: ${entry.filePath}');
      return true; // treat as success — nothing to retry
    }

    try {
      final bytes = await file.readAsBytes();
      await _apiService.uploadStoryAudio(
        bytes: bytes,
        filename: entry.filename,
        storyId: entry.storyId,
        paragraphId: entry.paragraphId,
        isAttachment: entry.isAttachment,
        languageCode: entry.languageCode,
      );
      return true;
    } catch (e) {
      // 4xx other than 404/408/429 are non-retryable terminal failures
      // (file too large, validation, auth). 404 is treated as retryable
      // because the most common cause is the autosave race — the paragraph
      // exists locally but hasn't been pushed to the server yet. After
      // _maxAttempts of backoff this still gets dropped, which also covers
      // the edge case of an old backend deployment that lacks the endpoint.
      final s = e.toString();
      final m = RegExp(r'\b(4\d\d)\b').firstMatch(s);
      if (m != null) {
        final code = int.tryParse(m.group(1)!) ?? 0;
        if (code != 404 && code != 408 && code != 429) {
          debugPrint('[AudioUploadQueue] non-retryable $code: $e');
          return true;
        }
      }
      debugPrint('[AudioUploadQueue] upload failed (will retry): $e');
      return false;
    }
  }

  Duration _backoffFor(int attempt) {
    // Exponential: 4s, 8s, 16s, 32s, capped at _maxBackoff.
    final secs = (1 << attempt) * 2;
    final d = Duration(seconds: secs);
    return d > _maxBackoff ? _maxBackoff : d;
  }

  // ---------------------------------------------------------------------------
  // Persistence
  // ---------------------------------------------------------------------------

  Future<List<_QueueEntry>> _loadAll() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_prefsKey);
    if (raw == null || raw.isEmpty) return const [];
    try {
      final list = (jsonDecode(raw) as List).cast<Map<String, dynamic>>();
      return list.map(_QueueEntry.fromJson).toList();
    } catch (_) {
      // Corrupt prefs: nuke and start over.
      await prefs.remove(_prefsKey);
      return const [];
    }
  }

  Future<void> _saveAll(List<_QueueEntry> entries) async {
    final prefs = await SharedPreferences.getInstance();
    if (entries.isEmpty) {
      await prefs.remove(_prefsKey);
      return;
    }
    final encoded = jsonEncode(entries.map((e) => e.toJson()).toList());
    await prefs.setString(_prefsKey, encoded);
  }

  Future<void> _persistAdd(_QueueEntry entry) async {
    final entries = await _loadAll();
    entries.add(entry);
    await _saveAll(entries);
  }

  Future<void> _persistRemove(_QueueEntry entry) async {
    final entries = await _loadAll();
    entries.removeWhere((e) => e.filePath == entry.filePath);
    await _saveAll(entries);
  }

  Future<void> _persistReplace(_QueueEntry oldEntry, _QueueEntry newEntry) async {
    final entries = await _loadAll();
    final idx = entries.indexWhere((e) => e.filePath == oldEntry.filePath);
    if (idx >= 0) {
      entries[idx] = newEntry;
      await _saveAll(entries);
    }
  }

  Future<Directory> _ensureQueueDir() async {
    final docs = await getApplicationDocumentsDirectory();
    final dir = Directory('${docs.path}/$_queueSubdir');
    if (!await dir.exists()) await dir.create(recursive: true);
    return dir;
  }

  Future<void> _deleteFileQuiet(String path) async {
    try {
      final f = File(path);
      if (await f.exists()) await f.delete();
    } catch (_) {}
  }

  String _filenameFromPath(String path) {
    final i = path.lastIndexOf(Platform.pathSeparator);
    return i >= 0 ? path.substring(i + 1) : path;
  }
}

@immutable
class _QueueEntry {
  final String filePath;
  final String filename;
  final String storyId;
  final String paragraphId;
  final bool isAttachment;
  final String languageCode;
  final int attempts;
  final DateTime enqueuedAt;

  const _QueueEntry({
    required this.filePath,
    required this.filename,
    required this.storyId,
    required this.paragraphId,
    required this.isAttachment,
    required this.languageCode,
    required this.attempts,
    required this.enqueuedAt,
  });

  _QueueEntry copyWith({int? attempts}) => _QueueEntry(
        filePath: filePath,
        filename: filename,
        storyId: storyId,
        paragraphId: paragraphId,
        isAttachment: isAttachment,
        languageCode: languageCode,
        attempts: attempts ?? this.attempts,
        enqueuedAt: enqueuedAt,
      );

  Map<String, dynamic> toJson() => {
        'filePath': filePath,
        'filename': filename,
        'storyId': storyId,
        'paragraphId': paragraphId,
        'isAttachment': isAttachment,
        'languageCode': languageCode,
        'attempts': attempts,
        'enqueuedAt': enqueuedAt.toIso8601String(),
      };

  static _QueueEntry fromJson(Map<String, dynamic> j) => _QueueEntry(
        filePath: j['filePath'] as String,
        filename: j['filename'] as String,
        storyId: j['storyId'] as String,
        paragraphId: j['paragraphId'] as String,
        isAttachment: j['isAttachment'] as bool? ?? false,
        languageCode: j['languageCode'] as String? ?? 'od-IN',
        attempts: j['attempts'] as int? ?? 0,
        enqueuedAt: DateTime.tryParse(j['enqueuedAt'] as String? ?? '') ?? DateTime.now(),
      );
}
