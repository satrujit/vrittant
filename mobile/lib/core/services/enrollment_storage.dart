import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Local storage for the reporter's voice enrollment embedding.
///
/// Storage backend
/// ---------------
/// The voice embedding is a numeric vector that uniquely identifies the
/// reporter's vocal characteristics — effectively a biometric. We can't
/// rotate it (the reporter's voice is what it is), and a leak gives an
/// attacker the means to spoof speaker verification offline. So this
/// must NOT live in plaintext SharedPreferences.
///
/// We use [FlutterSecureStorage], which maps to:
///   - iOS:     Keychain (encrypted by the Secure Enclave; survives app
///              reinstall unless device-restored)
///   - Android: EncryptedSharedPreferences (AES via Keystore)
///
/// Same backend as the JWT — see [AuthNotifier] for the migration
/// playbook we follow here.
///
/// Legacy migration
/// ----------------
/// Earlier builds wrote the enrollment to plain SharedPreferences keyed
/// by `voice_embedding` / `voice_sample_count` / `voice_enrolled_at`.
/// On first read after upgrade we check those keys, copy the values
/// into secure storage, then delete the plaintext copies. Reporters who
/// enrolled before this version don't lose their enrollment AND the
/// plaintext residue is cleaned up on first launch.
///
/// Keys (in secure storage):
///   - `voice_embedding`   → JSON-encoded List<double>
///   - `voice_sample_count` → int as string
///   - `voice_enrolled_at`  → ISO-8601 string
class EnrollmentStorage {
  EnrollmentStorage._();

  static const _keyEmbedding = 'voice_embedding';
  static const _keySampleCount = 'voice_sample_count';
  static const _keyEnrolledAt = 'voice_enrolled_at';

  /// Same accessibility settings the JWT uses — first unlock per
  /// device, no iCloud sync. The biometric embedding is per-device by
  /// definition (it's tied to a single enrollment session); syncing it
  /// to other devices via iCloud would expand the threat surface for
  /// no functional benefit.
  static const _secure = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
    iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
  );

  /// Save (or overwrite) the enrollment locally in secure storage.
  static Future<void> save({
    required List<double> embedding,
    required int sampleCount,
  }) async {
    await _secure.write(
      key: _keyEmbedding,
      value: jsonEncode(embedding),
    );
    await _secure.write(
      key: _keySampleCount,
      value: sampleCount.toString(),
    );
    await _secure.write(
      key: _keyEnrolledAt,
      value: DateTime.now().toIso8601String(),
    );
    // Make sure no plaintext copy lingers from a pre-migration build.
    // Cheap to do on every save — keeps the cleanup path covered even
    // if the user re-enrolls without ever hitting [load] first.
    await _wipeLegacy();
  }

  /// Load the stored enrollment, or `null` if none exists.
  ///
  /// Read priority:
  ///   1. Secure storage (current backend).
  ///   2. Legacy SharedPreferences — if found, migrate into secure
  ///      storage and delete the plaintext copy on the same call so
  ///      subsequent reads only touch secure storage.
  static Future<EnrollmentData?> load() async {
    final secureRaw = await _secure.read(key: _keyEmbedding);
    if (secureRaw != null) {
      return _parse(
        rawEmbedding: secureRaw,
        sampleCountStr: await _secure.read(key: _keySampleCount),
        enrolledAtStr: await _secure.read(key: _keyEnrolledAt),
      );
    }

    // Legacy path: migrate transparently on read.
    final prefs = await SharedPreferences.getInstance();
    final legacyRaw = prefs.getString(_keyEmbedding);
    if (legacyRaw == null) return null;

    final legacySamples = prefs.getInt(_keySampleCount) ?? 0;
    final legacyEnrolledAt = prefs.getString(_keyEnrolledAt);

    // Copy into secure storage.
    await _secure.write(key: _keyEmbedding, value: legacyRaw);
    await _secure.write(
      key: _keySampleCount,
      value: legacySamples.toString(),
    );
    if (legacyEnrolledAt != null) {
      await _secure.write(key: _keyEnrolledAt, value: legacyEnrolledAt);
    }
    // Drop the plaintext copies — keeping them around defeats the
    // entire migration.
    await _wipeLegacy();

    return _parse(
      rawEmbedding: legacyRaw,
      sampleCountStr: legacySamples.toString(),
      enrolledAtStr: legacyEnrolledAt,
    );
  }

  /// Delete enrollment data from local storage (both backends).
  static Future<void> clear() async {
    await _secure.delete(key: _keyEmbedding);
    await _secure.delete(key: _keySampleCount);
    await _secure.delete(key: _keyEnrolledAt);
    await _wipeLegacy();
  }

  /// Whether an enrollment exists locally — checks both backends so a
  /// reporter who enrolled pre-migration still reads as enrolled
  /// even before the next [load] migrates them.
  static Future<bool> hasEnrollment() async {
    if (await _secure.containsKey(key: _keyEmbedding)) return true;
    final prefs = await SharedPreferences.getInstance();
    return prefs.containsKey(_keyEmbedding);
  }

  // ── internals ──────────────────────────────────────────────────

  static EnrollmentData? _parse({
    required String rawEmbedding,
    String? sampleCountStr,
    String? enrolledAtStr,
  }) {
    try {
      final list = (jsonDecode(rawEmbedding) as List).cast<num>();
      return EnrollmentData(
        embedding: list.map((n) => n.toDouble()).toList(),
        sampleCount: int.tryParse(sampleCountStr ?? '') ?? 0,
        enrolledAt: enrolledAtStr != null
            ? DateTime.tryParse(enrolledAtStr)
            : null,
      );
    } catch (_) {
      return null;
    }
  }

  static Future<void> _wipeLegacy() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_keyEmbedding);
    await prefs.remove(_keySampleCount);
    await prefs.remove(_keyEnrolledAt);
  }
}

/// Immutable snapshot of the local enrollment.
class EnrollmentData {
  final List<double> embedding;
  final int sampleCount;
  final DateTime? enrolledAt;

  const EnrollmentData({
    required this.embedding,
    required this.sampleCount,
    this.enrolledAt,
  });
}
