// Force-update gate.
//
// On cold start the app fetches GET /version/min-supported and compares its
// own version against the platform-specific minimum. If we're below it, the
// app routes to a non-dismissable "Update required" screen.
//
// Failure modes are deliberately permissive: if the API call fails (offline,
// server down, garbled response) we fall through to "up to date" rather than
// blocking the user. The whole point of this gate is to handle the case where
// the OLD client has a known incompatibility — punishing users for transient
// network issues with a forced "Update Now" screen they can't escape from
// would be worse than the bug we're guarding against.

import 'dart:async';
import 'dart:io' show Platform;

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:package_info_plus/package_info_plus.dart';

import 'api_config.dart';

enum VersionCheckResult {
  /// Current version >= min. Proceed normally.
  upToDate,

  /// Current version < min. Block UI, force update.
  forceUpdate,
}

class VersionCheckOutcome {
  final VersionCheckResult result;

  /// Store deep link for the current platform. Empty if the API didn't
  /// return one (e.g. iOS app ID not yet known) — in that case the
  /// "Update Now" button should be hidden.
  final String storeUrl;

  /// The minimum version the server reports. Useful for telemetry / debug.
  final String minVersion;

  /// The current installed version we compared against.
  final String currentVersion;

  const VersionCheckOutcome({
    required this.result,
    required this.storeUrl,
    required this.minVersion,
    required this.currentVersion,
  });
}

class VersionCheckService {
  final Dio _dio;

  VersionCheckService({Dio? dio})
      : _dio = dio ?? Dio(BaseOptions(
          baseUrl: ApiConfig.baseUrl,
          connectTimeout: const Duration(seconds: 5),
          receiveTimeout: const Duration(seconds: 5),
        ));

  /// Compare the running app against the server's minimum-supported version.
  ///
  /// Returns [VersionCheckResult.upToDate] on any failure (network error,
  /// bad response, missing platform key) — see the file-level comment for
  /// why we fail open.
  Future<VersionCheckOutcome> check() async {
    final info = await PackageInfo.fromPlatform();
    final current = info.version;

    try {
      final res = await _dio.get('/version/min-supported');
      final body = res.data as Map<String, dynamic>;

      final platformKey = Platform.isIOS ? 'ios' : 'android';
      final platformBlock = body[platformKey] as Map<String, dynamic>?;
      if (platformBlock == null) {
        return VersionCheckOutcome(
          result: VersionCheckResult.upToDate,
          storeUrl: '',
          minVersion: '',
          currentVersion: current,
        );
      }

      final minVersion = (platformBlock['min'] as String?) ?? '';
      final storeUrl = (platformBlock['store_url'] as String?) ?? '';

      // Empty min disables the gate (default for dev/UAT). Without this
      // a fresh environment with unset env vars would block all clients.
      if (minVersion.isEmpty) {
        return VersionCheckOutcome(
          result: VersionCheckResult.upToDate,
          storeUrl: storeUrl,
          minVersion: minVersion,
          currentVersion: current,
        );
      }

      final isBelow = _compareSemver(current, minVersion) < 0;
      return VersionCheckOutcome(
        result: isBelow
            ? VersionCheckResult.forceUpdate
            : VersionCheckResult.upToDate,
        storeUrl: storeUrl,
        minVersion: minVersion,
        currentVersion: current,
      );
    } catch (_) {
      // Fail open. See file-level comment.
      return VersionCheckOutcome(
        result: VersionCheckResult.upToDate,
        storeUrl: '',
        minVersion: '',
        currentVersion: current,
      );
    }
  }

  /// Returns -1 if a < b, 0 if a == b, 1 if a > b.
  /// Compares dotted numeric segments; non-numeric segments compare as 0.
  /// Tolerates differing segment counts ("1.0" vs "1.0.0") by zero-padding.
  static int _compareSemver(String a, String b) {
    final aParts = a.split('.').map(_safeInt).toList();
    final bParts = b.split('.').map(_safeInt).toList();
    final n = aParts.length > bParts.length ? aParts.length : bParts.length;
    for (var i = 0; i < n; i++) {
      final av = i < aParts.length ? aParts[i] : 0;
      final bv = i < bParts.length ? bParts[i] : 0;
      if (av < bv) return -1;
      if (av > bv) return 1;
    }
    return 0;
  }

  static int _safeInt(String s) => int.tryParse(s) ?? 0;
}

final versionCheckServiceProvider =
    Provider<VersionCheckService>((_) => VersionCheckService());

/// Async one-shot result of the cold-start version check. Exposed as a
/// FutureProvider so the splash screen / router can `.when()` on it.
final versionCheckProvider = FutureProvider<VersionCheckOutcome>((ref) async {
  return ref.read(versionCheckServiceProvider).check();
});
