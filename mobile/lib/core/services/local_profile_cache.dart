import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive/hive.dart';
import 'package:hive_flutter/hive_flutter.dart';

import 'api_service.dart';

/// On-disk cache for the reporter's own profile (the `/me` response).
///
/// Why this exists: the auth provider used to refuse to consider the
/// user "logged in" until `/me` returned. On a flaky-network cold
/// start that meant the user got punted to the login screen even
/// though their token was perfectly valid — and even though we already
/// had their last known profile from the previous session. The image
/// cache keeps the org logo on-device forever; the stories cache keeps
/// their work on-device; only the reporter's name + org metadata was
/// hitting the network on every cold start. Now it doesn't.
///
/// Storage shape: a single Hive box with one key (`__profile__`)
/// holding the raw JSON string returned by `/api/auth/me`. We cache
/// the JSON, not the deserialised object, so a future field added on
/// the server (e.g. another org metadata blob) is preserved through a
/// cold start even if the mobile build doesn't know about it yet — the
/// next app version that does know will deserialise it correctly.
///
/// This box lives outside the secure store on purpose. The token (the
/// actual auth credential) stays in flutter_secure_storage / Keychain;
/// the profile is non-sensitive PII the user already saw on screen.
/// Putting it in Hive lets it be cleared by `Hive.deleteFromDisk` on
/// logout in lockstep with the stories cache.
class LocalProfileCache {
  static const _boxName = 'profile_cache';
  static const _profileKey = '__profile__';

  static Future<void> init() async {
    if (!Hive.isBoxOpen(_boxName)) {
      await Hive.openBox<String>(_boxName);
    }
  }

  Box<String> get _box => Hive.box<String>(_boxName);

  /// Cached reporter, or `null` on a cold cache or corrupt entry.
  ReporterProfile? read() {
    final raw = _box.get(_profileKey);
    if (raw == null) return null;
    try {
      return ReporterProfile.fromJson(
        jsonDecode(raw) as Map<String, dynamic>,
      );
    } catch (_) {
      // Schema drift or truncated write — drop it; next /me will refill.
      _box.delete(_profileKey);
      return null;
    }
  }

  /// Persist the raw `/me` JSON. Pass the un-deserialised map so we
  /// preserve fields the current build doesn't model yet.
  Future<void> writeRaw(Map<String, dynamic> json) async {
    await _box.put(_profileKey, jsonEncode(json));
  }

  /// Clear on logout. The stories cache and the secure-store token
  /// each have their own clear; they're called together by AuthNotifier.
  Future<void> clear() async {
    await _box.clear();
  }
}

final localProfileCacheProvider =
    Provider<LocalProfileCache>((ref) => LocalProfileCache());
