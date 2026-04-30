import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/services/api_service.dart';
import '../../../core/services/local_drafts_store.dart';
import '../../../core/services/local_stories_cache.dart';

/// Lightweight summary of a local Hive draft, surfaced to the home screen
/// so it can render a card without rehydrating the full payload.
class DraftSummary {
  final String localId;
  final String headline;
  final String? category;
  final String? location;
  final int paragraphCount;
  final DateTime updatedAt;
  final DateTime createdAt;

  const DraftSummary({
    required this.localId,
    required this.headline,
    this.category,
    this.location,
    required this.paragraphCount,
    required this.updatedAt,
    required this.createdAt,
  });

  factory DraftSummary.fromPayload(Map<String, dynamic> p) {
    final paragraphs = p['paragraphs'];
    final pCount = paragraphs is List ? paragraphs.length : 0;
    DateTime parse(String? raw) =>
        (raw != null ? DateTime.tryParse(raw) : null) ?? DateTime.now();
    return DraftSummary(
      localId: p['local_id'] as String? ?? '',
      headline: p['headline'] as String? ?? '',
      category: p['category'] as String?,
      location: p['location'] as String?,
      paragraphCount: pCount,
      updatedAt: parse(p['updated_at'] as String?),
      createdAt: parse(p['created_at'] as String?),
    );
  }
}

class StoriesState {
  /// Stories already submitted (or further along) — fetched from the
  /// server. By design this list excludes drafts: under the local-first
  /// flow drafts never live on the server until submit.
  final List<StoryDto> serverStories;

  /// Local-only drafts read from Hive.
  final List<DraftSummary> localDrafts;

  final bool isLoading;
  final String? error;

  const StoriesState({
    this.serverStories = const [],
    this.localDrafts = const [],
    this.isLoading = false,
    this.error,
  });

  /// Backwards-compat: existing UI code reads `state.stories` to count or
  /// check emptiness. We surface the union so empty-state logic still
  /// works without needing every caller to know about the split.
  List<dynamic> get stories => [...localDrafts, ...serverStories];

  /// Drafts shown to the reporter (local Hive only).
  List<DraftSummary> get drafts => localDrafts;

  /// Everything that's been submitted or further (in_progress, approved,
  /// rejected, flagged, published).
  List<StoryDto> get submitted => serverStories;

  StoriesState copyWith({
    List<StoryDto>? serverStories,
    List<DraftSummary>? localDrafts,
    bool? isLoading,
    String? error,
    bool clearError = false,
  }) {
    return StoriesState(
      serverStories: serverStories ?? this.serverStories,
      localDrafts: localDrafts ?? this.localDrafts,
      isLoading: isLoading ?? this.isLoading,
      error: clearError ? null : (error ?? this.error),
    );
  }
}

class StoriesNotifier extends Notifier<StoriesState> {
  StreamSubscription? _draftsSub;

  @override
  StoriesState build() {
    // Reactively rebuild when the Hive drafts box mutates so the home
    // list updates immediately after a submit / draft-discard / new-draft.
    final store = ref.read(localDraftsStoreProvider);
    _draftsSub?.cancel();
    _draftsSub = store.watch().listen((_) {
      state = state.copyWith(localDrafts: _readDrafts());
    });
    ref.onDispose(() {
      _draftsSub?.cancel();
      _draftsSub = null;
    });

    // Stale-while-revalidate: seed serverStories synchronously from the
    // on-disk cache so the UI renders instantly. We then kick off a
    // background refresh in a microtask — no spinner unless the cache
    // was empty (cold start).
    final cached = ref
        .read(localStoriesCacheProvider)
        .all()
        .where((s) => s.status != 'draft')
        .toList();
    Future.microtask(() => fetchStories());
    return StoriesState(
      localDrafts: _readDrafts(),
      serverStories: cached,
    );
  }

  ApiService get _api => ref.read(apiServiceProvider);
  LocalStoriesCache get _cache => ref.read(localStoriesCacheProvider);

  List<DraftSummary> _readDrafts() {
    return ref
        .read(localDraftsStoreProvider)
        .all()
        .map(DraftSummary.fromPayload)
        .toList();
  }

  Future<void> fetchStories() async {
    // Only show the spinner on a cold cache — otherwise we already have
    // something on-screen and the refresh runs silently in the background.
    final coldCache = state.serverStories.isEmpty;
    state = state.copyWith(
      isLoading: coldCache,
      clearError: true,
    );
    try {
      // We only need server-side stories that have moved past draft.
      // Server defaults to all statuses for the reporter; we filter
      // client-side so legacy server-side drafts (pre-refactor) still
      // show up under the submitted list rather than vanishing.
      final stories = await _api.listStories();
      // Cache the full server response (including any server-side
      // drafts) so a re-seed on next launch matches what we'd fetch.
      await _cache.replaceAll(stories);
      state = state.copyWith(
        serverStories: stories.where((s) => s.status != 'draft').toList(),
        isLoading: false,
      );
    } catch (e) {
      // Keep cache contents in state on failure; surface error to UI.
      state = state.copyWith(isLoading: false, error: 'Failed to load stories');
    }
  }

  Future<void> submitStory(String storyId) async {
    try {
      await _api.submitStory(storyId);
      await fetchStories(); // Refresh list
    } catch (_) {}
  }

  Future<bool> deleteStory(String storyId) async {
    try {
      await _api.deleteStory(storyId);
      // Remove from local state immediately
      final updated =
          state.serverStories.where((s) => s.id != storyId).toList();
      state = state.copyWith(serverStories: updated);
      await _cache.remove(storyId);
      return true;
    } catch (_) {
      return false;
    }
  }

  /// Discard a local draft without ever touching the server.
  Future<void> deleteLocalDraft(String localId) async {
    await ref.read(localDraftsStoreProvider).delete(localId);
    // The Hive watcher will refresh state.localDrafts.
  }
}

final storiesProvider =
    NotifierProvider<StoriesNotifier, StoriesState>(StoriesNotifier.new);
