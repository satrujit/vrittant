import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive/hive.dart';

/// Local-first store for unsubmitted story drafts.
///
/// Drafts live entirely on the device until the reporter taps Submit.
/// We persist each draft as a JSON-encoded string keyed by a client-generated
/// local id (uuid-style). Hive's BoxEvent stream lets the home stories list
/// react to drafts being added / removed.
class LocalDraftsStore {
  static const _boxName = 'drafts';

  /// Open the Hive box. Call once at app startup before runApp.
  static Future<void> init() async {
    if (!Hive.isBoxOpen(_boxName)) {
      await Hive.openBox<String>(_boxName);
    }
  }

  Box<String> get _box => Hive.box<String>(_boxName);

  /// Save (overwrite) a draft. Writes the full JSON payload of the editor
  /// state — paragraphs, headline, category, location, etc.
  Future<void> save(String localId, Map<String, dynamic> payload) async {
    await _box.put(localId, jsonEncode(payload));
  }

  /// Load a draft. Returns null if no entry for that id.
  Map<String, dynamic>? load(String localId) {
    final raw = _box.get(localId);
    if (raw == null) return null;
    try {
      final decoded = jsonDecode(raw);
      if (decoded is Map<String, dynamic>) return decoded;
      if (decoded is Map) return Map<String, dynamic>.from(decoded);
      return null;
    } catch (_) {
      // Corrupt entry — drop it from the caller's perspective.
      return null;
    }
  }

  /// All drafts in the box, sorted by updated_at descending. Corrupt entries
  /// are silently skipped.
  List<Map<String, dynamic>> all() {
    final out = <Map<String, dynamic>>[];
    for (final key in _box.keys) {
      final raw = _box.get(key);
      if (raw == null) continue;
      try {
        final decoded = jsonDecode(raw);
        if (decoded is Map) {
          out.add(Map<String, dynamic>.from(decoded));
        }
      } catch (_) {
        // skip
      }
    }
    out.sort((a, b) {
      final aUpdated = a['updated_at'] as String? ?? '';
      final bUpdated = b['updated_at'] as String? ?? '';
      return bUpdated.compareTo(aUpdated);
    });
    return out;
  }

  /// Delete a draft (call after successful submit).
  Future<void> delete(String localId) async {
    await _box.delete(localId);
  }

  /// Stream of changes — for the home stories list to react to drafts being
  /// added / removed.
  Stream<BoxEvent> watch() => _box.watch();
}

final localDraftsStoreProvider = Provider((ref) => LocalDraftsStore());
