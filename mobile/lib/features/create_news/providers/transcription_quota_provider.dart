/// Per-reporter monthly STT quota state.
///
/// Mirrors the server's `/auth/me/transcription-usage` endpoint. The
/// notepad UI consumes this to:
///   - render a "X min left" badge near the mic button when remaining
///     drops below 30 min,
///   - disable the mic button when remaining = 0 (server will refuse
///     the WS anyway, but the local block is faster + clearer UX),
///   - show a "less than 5 min left" snackbar before starting a
///     dictation that's about to clip.
///
/// Refresh triggers (caller-driven, not on a timer):
///   - app resume / login
///   - notepad screen entry
///   - immediately after a session ends (so the badge updates
///     without the user having to leave + re-enter the screen).
library;

import 'dart:developer' as developer;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/services/api_service.dart';

class TranscriptionQuotaState {
  const TranscriptionQuotaState({
    required this.usedSeconds,
    required this.limitSeconds,
    required this.remainingSeconds,
    required this.isOverQuota,
    required this.yearMonth,
    required this.lastFetchedAt,
    this.error,
  });

  final int usedSeconds;
  final int limitSeconds;
  final int remainingSeconds;
  final bool isOverQuota;
  final String yearMonth;
  final DateTime lastFetchedAt;
  final String? error;

  /// Initial / never-fetched state. Treats the user as having full
  /// budget so we don't accidentally block dictation before the first
  /// fetch lands. Server-side check is the real gate.
  factory TranscriptionQuotaState.unknown() => TranscriptionQuotaState(
        usedSeconds: 0,
        limitSeconds: 3 * 3600,
        remainingSeconds: 3 * 3600,
        isOverQuota: false,
        yearMonth: '',
        lastFetchedAt: DateTime.fromMillisecondsSinceEpoch(0),
      );

  /// Whether to show the warning badge (≤ 30 min remaining).
  bool get showBadge => remainingSeconds <= 30 * 60;

  /// Whether to escalate badge to coral / show pre-session warning
  /// (≤ 5 min remaining and not yet exhausted).
  bool get isNearLimit => !isOverQuota && remainingSeconds <= 5 * 60;

  /// Whole minutes remaining, rounded down. Used by the UI badge so
  /// "0 min" appears slightly before the actual cutoff (i.e. when
  /// only 30 seconds are left); reporters won't be surprised by an
  /// abrupt block.
  int get remainingMinutes => remainingSeconds ~/ 60;

  TranscriptionQuotaState copyWith({String? error}) => TranscriptionQuotaState(
        usedSeconds: usedSeconds,
        limitSeconds: limitSeconds,
        remainingSeconds: remainingSeconds,
        isOverQuota: isOverQuota,
        yearMonth: yearMonth,
        lastFetchedAt: lastFetchedAt,
        error: error,
      );
}

class TranscriptionQuotaNotifier extends Notifier<TranscriptionQuotaState> {
  @override
  TranscriptionQuotaState build() => TranscriptionQuotaState.unknown();

  /// Fetch the latest quota status. No-op if the last fetch is < 5s
  /// old — collapses bursty calls (e.g. notepad enter + post-session
  /// refresh firing back-to-back). Pass `force: true` to bypass.
  Future<void> refresh({bool force = false}) async {
    final age = DateTime.now().difference(state.lastFetchedAt);
    if (!force && age < const Duration(seconds: 5)) return;
    try {
      final raw = await ref.read(apiServiceProvider).getTranscriptionUsage();
      state = TranscriptionQuotaState(
        usedSeconds: (raw['used_seconds'] as num?)?.toInt() ?? 0,
        limitSeconds: (raw['limit_seconds'] as num?)?.toInt() ?? 3 * 3600,
        remainingSeconds: (raw['remaining_seconds'] as num?)?.toInt() ?? 3 * 3600,
        isOverQuota: raw['is_over_quota'] as bool? ?? false,
        yearMonth: raw['year_month'] as String? ?? '',
        lastFetchedAt: DateTime.now(),
      );
    } catch (e, st) {
      developer.log(
        'quota refresh failed: $e',
        name: 'transcription_quota',
        error: e,
        stackTrace: st,
      );
      // Keep prior values but mark error. We deliberately do NOT block
      // dictation on a fetch failure — the server is still the source
      // of truth and will refuse if quota is exhausted.
      state = state.copyWith(error: '$e');
    }
  }
}

final transcriptionQuotaProvider =
    NotifierProvider<TranscriptionQuotaNotifier, TranscriptionQuotaState>(
  TranscriptionQuotaNotifier.new,
);
