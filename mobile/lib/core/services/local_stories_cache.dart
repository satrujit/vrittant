import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive/hive.dart';
import 'package:hive_flutter/hive_flutter.dart';

import 'api_service.dart';

/// On-disk cache for server-fetched stories. Mirrors the StoryDto JSON
/// shape the server returns so we can rehydrate without parsing
/// surprises. Use as a stale-while-revalidate cache: read cache
/// instantly on screen open, then refresh from network in background.
///
/// One Hive box, keyed by story id. We DON'T cache by query (status,
/// search, etc.) — we cache by story id and let the consumer filter
/// in-memory. That keeps the cache small and means a fresh fetch
/// updates one row, not an entire query bucket.
class LocalStoriesCache {
  static const _boxName = 'stories_cache';
  static const _metaKey = '__meta__';

  static Future<void> init() async {
    if (!Hive.isBoxOpen(_boxName)) {
      await Hive.openBox<String>(_boxName);
    }
  }

  Box<String> get _box => Hive.box<String>(_boxName);

  /// Last successful refresh timestamp (millis since epoch). Reads
  /// older than [staleAfter] should still be served from cache, but
  /// the consumer should fire a background refresh.
  DateTime? get lastRefreshedAt {
    final v = _box.get(_metaKey);
    if (v == null) return null;
    return DateTime.fromMillisecondsSinceEpoch(int.parse(v));
  }

  /// All cached stories, deserialised. Returns empty list on a cold cache.
  List<StoryDto> all() {
    final out = <StoryDto>[];
    for (final key in _box.keys) {
      if (key == _metaKey) continue;
      final raw = _box.get(key);
      if (raw == null) continue;
      try {
        out.add(StoryDto.fromJson(jsonDecode(raw) as Map<String, dynamic>));
      } catch (_) {
        // Corrupt entry — drop it.
        _box.delete(key);
      }
    }
    return out;
  }

  /// Replace the entire cache atomically. Used after a fresh
  /// listStories() succeeds.
  Future<void> replaceAll(List<StoryDto> stories) async {
    await _box.clear();
    for (final s in stories) {
      await _box.put(s.id, jsonEncode(_toJson(s)));
    }
    await _box.put(
      _metaKey,
      DateTime.now().millisecondsSinceEpoch.toString(),
    );
  }

  /// Look up a single story by id. Returns null if not in cache or
  /// the entry is corrupt (in which case it's also dropped). Used by
  /// the notepad to hydrate from cache instantly when the reporter
  /// taps a story card, before the network refresh lands.
  StoryDto? find(String id) {
    final raw = _box.get(id);
    if (raw == null) return null;
    try {
      return StoryDto.fromJson(jsonDecode(raw) as Map<String, dynamic>);
    } catch (_) {
      _box.delete(id);
      return null;
    }
  }

  /// Update a single story (e.g. after a per-story fetch / mutation).
  Future<void> upsert(StoryDto story) async {
    await _box.put(story.id, jsonEncode(_toJson(story)));
  }

  /// Drop a story from the cache (e.g. after delete).
  Future<void> remove(String id) async {
    await _box.delete(id);
  }

  /// Clear everything (sign-out cleanup).
  Future<void> clear() async {
    await _box.clear();
  }

  Map<String, dynamic> _toJson(StoryDto s) => {
        'id': s.id,
        'reporter_id': s.reporterId,
        'headline': s.headline,
        'category': s.category,
        'location': s.location,
        'paragraphs': s.paragraphs,
        'status': s.status,
        'submitted_at': s.submittedAt?.toIso8601String(),
        'created_at': s.createdAt.toIso8601String(),
        'updated_at': s.updatedAt.toIso8601String(),
        'display_id': s.displayId,
        'seq_no': s.seqNo,
      };
}

final localStoriesCacheProvider =
    Provider<LocalStoriesCache>((ref) => LocalStoriesCache());
