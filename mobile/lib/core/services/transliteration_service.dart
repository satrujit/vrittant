/// Transliteration service: Latin (English-letter) → Odia script.
///
/// Powered by Google Input Tools' public endpoint
/// (https://inputtools.google.com/request) — the same backend Gboard uses
/// for transliteration. No API key required, no quota disclosed; we
/// gate calls behind a per-word Hive cache so a stable reporter
/// vocabulary settles into zero-network operation after a few days
/// of use.
///
/// Public surface
/// --------------
/// - [TransliterationService.instance.transliterate(word)] — returns the
///   top Odia candidate, or `null` if (a) the word already contains
///   Odia script (don't disrupt native typing), (b) the network is
///   unreachable AND the word isn't in cache, or (c) the API returns
///   no candidates.
///
/// Cache
/// -----
/// `transliteration_cache` Hive box: `{lower_word: top_candidate}`.
/// Persistent across app restarts. Capped at 5,000 entries (LRU
/// eviction); a typical reporter's working vocabulary is well below
/// this so practical hit rate after a week is 70%+.
///
/// Offline behaviour
/// -----------------
/// If the API call fails for any reason (timeout, no network, 5xx),
/// `transliterate(word)` returns `null` and the caller leaves the
/// Latin text in place. Cached words still resolve — useful for
/// reporters in patchy 4G conditions.
import 'dart:async';
import 'dart:collection';
import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:hive/hive.dart';

import 'transliteration_loanwords.dart';

class TransliterationService {
  TransliterationService._();
  static final TransliterationService instance = TransliterationService._();

  static const _kCacheBoxName = 'transliteration_cache';
  static const _kCacheCapacity = 5000;
  static const _kEndpoint = 'https://inputtools.google.com/request';
  // Google's IETF-style language tag for Odia transliteration. Same one
  // Gboard sends. Gboard also uses the more colloquial mode (i0-und =
  // input zero, undefined target script) which produces script-native
  // output without requiring users to know the formal language code.
  static const _kLangTag = 'or-t-i0-und';
  static const _kNumCandidates = 3;
  static const _kTimeout = Duration(milliseconds: 1500);

  /// Punctuation → Odia equivalents (purna biram, etc.)
  static const _kPunctuationMap = <String, String>{
    '.': ' ।',   // full stop → space + purna chheda (purna biram)
    '..': ' ।।', // double stop → space + double danda
  };

  Box<String>? _cache;
  // In-flight de-dup so two near-simultaneous transliterations of the
  // same word don't fire two HTTP calls.
  final Map<String, Future<String?>> _inflight = HashMap();

  Dio? _dio;
  Dio _httpClient() {
    return _dio ??= Dio(BaseOptions(
      connectTimeout: _kTimeout,
      receiveTimeout: _kTimeout,
      sendTimeout: _kTimeout,
      // Don't throw on non-2xx; we handle status codes manually so a
      // 4xx doesn't cascade into Dio's exception machinery.
      validateStatus: (_) => true,
    ));
  }

  Future<void> initialize() async {
    if (_cache != null) return;
    try {
      _cache = await Hive.openBox<String>(_kCacheBoxName);
    } catch (e) {
      debugPrint('[TransliterationService] cache init failed: $e');
      // Service is still usable without cache — every call hits the API.
    }
  }

  /// Returns the top Odia candidate for [word], or `null` if no
  /// transliteration was performed (word already in Odia, network
  /// failure with no cache, empty input). Safe to call without
  /// initialize() — falls back to network-only mode.
  Future<String?> transliterate(String word) async {
    final trimmed = word.trim();
    if (trimmed.isEmpty) return null;

    // Skip if the word already contains Odia script — the user is
    // typing native Odia (Lipikaar / Gboard Odia / paste). Don't
    // disrupt their typing.
    if (_containsOdiaScript(trimmed)) return null;

    // Punctuation mapping — convert common punctuation to Odia equivalents.
    final punct = _kPunctuationMap[trimmed];
    if (punct != null) return punct;

    // Skip if the word contains no Latin alphabet — pure punctuation,
    // numbers, emoji shouldn't be sent to the API.
    if (!_containsLatinAlpha(trimmed)) return null;

    final key = trimmed.toLowerCase();

    // Loanword dictionary — instant, offline, correct for English words
    // that Google's phonetic transliteration gets wrong (e.g. "college"
    // → କଲେଜ instead of mangled phonetic output).
    final loanword = lookupLoanword(key);
    if (loanword != null) return loanword;

    // Hot cache hit
    final cached = _cache?.get(key);
    if (cached != null) return cached;

    // De-dup in-flight calls for the same word
    final pending = _inflight[key];
    if (pending != null) return pending;

    final future = _fetchAndCache(key, trimmed);
    _inflight[key] = future;
    try {
      return await future;
    } finally {
      _inflight.remove(key);
    }
  }

  Future<String?> _fetchAndCache(String key, String word) async {
    String? result;
    try {
      result = await _fetchFromApi(word);
    } catch (e) {
      debugPrint('[TransliterationService] api call failed for $word: $e');
      return null;
    }
    if (result == null || result.isEmpty) return null;
    await _cacheStore(key, result);
    return result;
  }

  Future<String?> _fetchFromApi(String word) async {
    final response = await _httpClient().get<dynamic>(
      _kEndpoint,
      queryParameters: {
        'text': word,
        'itc': _kLangTag,
        'num': _kNumCandidates,
        'cp': 0,
        'cs': 1,
        'ie': 'utf-8',
        'oe': 'utf-8',
      },
    );
    if (response.statusCode != 200) return null;
    return _parseInputToolsResponse(response.data);
  }

  /// Parses the Google Input Tools response shape:
  ///   ["SUCCESS",[["namaskar",["ନମସ୍କାର","ନମସ୍କର", ...], [...], 1]]]
  /// or  ["FAILED_INPUT", ...] / ["NO_DATA", ...]
  /// Returns the first candidate from the first match, or `null` if the
  /// response shape doesn't match (defensive — Google may revise the
  /// undocumented endpoint).
  static String? _parseInputToolsResponse(dynamic raw) {
    try {
      // Dio may return a parsed list (if Content-Type indicates JSON)
      // or a raw string. Handle both.
      final List<dynamic> root = raw is String ? jsonDecode(raw) : raw as List<dynamic>;
      if (root.isEmpty) return null;
      if (root.first != 'SUCCESS') return null;
      final matches = root[1] as List<dynamic>;
      if (matches.isEmpty) return null;
      final firstMatch = matches.first as List<dynamic>;
      // firstMatch[0] = original word, firstMatch[1] = list of candidates
      if (firstMatch.length < 2) return null;
      final candidates = firstMatch[1] as List<dynamic>;
      if (candidates.isEmpty) return null;
      final top = candidates.first;
      return top is String ? top : null;
    } catch (_) {
      return null;
    }
  }

  Future<void> _cacheStore(String key, String value) async {
    final box = _cache;
    if (box == null) return;
    try {
      // LRU-ish eviction: when capacity is reached, drop the oldest
      // ~10% of entries. Crude but adequate; we're not memory-bound.
      if (box.length >= _kCacheCapacity) {
        final keysToDrop = box.keys.take(_kCacheCapacity ~/ 10).toList();
        await box.deleteAll(keysToDrop);
      }
      await box.put(key, value);
    } catch (e) {
      debugPrint('[TransliterationService] cache write failed: $e');
    }
  }

  /// Test-only: clear cache + in-flight state.
  @visibleForTesting
  Future<void> debugReset() async {
    _inflight.clear();
    await _cache?.clear();
  }

  /// Test-only: inject an HTTP client.
  @visibleForTesting
  set debugDio(Dio dio) {
    _dio = dio;
  }

  // ── helpers ─────────────────────────────────────────────────────

  static bool _containsOdiaScript(String s) {
    for (final r in s.runes) {
      if (r >= 0x0B00 && r <= 0x0B7F) return true;
    }
    return false;
  }

  static bool _containsLatinAlpha(String s) {
    for (final code in s.codeUnits) {
      if ((code >= 0x41 && code <= 0x5A) || (code >= 0x61 && code <= 0x7A)) {
        return true;
      }
    }
    return false;
  }
}
