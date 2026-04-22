import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

/// Local storage for the reporter's voice enrollment embedding.
///
/// Uses SharedPreferences (consistent with the rest of the app) to persist
/// the averaged speaker embedding so it survives app restarts.
///
/// Keys:
///   - `voice_embedding`   → JSON-encoded List<double>
///   - `voice_sample_count` → int (number of enrollment samples recorded)
///   - `voice_enrolled_at`  → ISO-8601 string
class EnrollmentStorage {
  static const _keyEmbedding = 'voice_embedding';
  static const _keySampleCount = 'voice_sample_count';
  static const _keyEnrolledAt = 'voice_enrolled_at';

  /// Save (or overwrite) the enrollment embedding locally.
  static Future<void> save({
    required List<double> embedding,
    required int sampleCount,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyEmbedding, jsonEncode(embedding));
    await prefs.setInt(_keySampleCount, sampleCount);
    await prefs.setString(_keyEnrolledAt, DateTime.now().toIso8601String());
  }

  /// Load the stored enrollment, or `null` if none exists.
  static Future<EnrollmentData?> load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_keyEmbedding);
    if (raw == null) return null;

    try {
      final list = (jsonDecode(raw) as List).cast<num>();
      return EnrollmentData(
        embedding: list.map((n) => n.toDouble()).toList(),
        sampleCount: prefs.getInt(_keySampleCount) ?? 0,
        enrolledAt: DateTime.tryParse(
          prefs.getString(_keyEnrolledAt) ?? '',
        ),
      );
    } catch (_) {
      return null;
    }
  }

  /// Delete enrollment data from local storage.
  static Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_keyEmbedding);
    await prefs.remove(_keySampleCount);
    await prefs.remove(_keyEnrolledAt);
  }

  /// Whether an enrollment exists locally.
  static Future<bool> hasEnrollment() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.containsKey(_keyEmbedding);
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
