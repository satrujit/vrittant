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

  /// True while a "next page" fetch is in flight. The home / all-news
  /// list shows a footer spinner during this state. Distinct from
  /// [isLoading], which is the cold-start full-list spinner.
  final bool isLoadingMore;

  /// True when the server reported a full page on the most recent
  /// fetch — there are likely more rows. Goes false the moment a
  /// fetch returns fewer than [pageSize] stories. The list footer
  /// hides itself when this is false so reporters know they've
  /// reached the end.
  final bool hasMoreStories;

  final String? error;

  const StoriesState({
    this.serverStories = const [],
    this.localDrafts = const [],
    this.isLoading = false,
    this.isLoadingMore = false,
    this.hasMoreStories = false,
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
    bool? isLoadingMore,
    bool? hasMoreStories,
    String? error,
    bool clearError = false,
  }) {
    return StoriesState(
      serverStories: serverStories ?? this.serverStories,
      localDrafts: localDrafts ?? this.localDrafts,
      isLoading: isLoading ?? this.isLoading,
      isLoadingMore: isLoadingMore ?? this.isLoadingMore,
      hasMoreStories: hasMoreStories ?? this.hasMoreStories,
      error: clearError ? null : (error ?? this.error),
    );
  }
}

class StoriesNotifier extends Notifier<StoriesState> {
  StreamSubscription? _draftsSub;

  /// Server pagination — page size matches the backend's default
  /// (50, max 100). Smaller pages = snappier first paint; bigger
  /// pages = fewer round-trips for power users scrolling deep.
  /// 50 is a good balance for our typical reporter (a few dozen
  /// stories per month).
  static const int _pageSize = 50;

  /// Total raw rows fetched from /stories so far (including any
  /// legacy drafts we filter out client-side). Used as the offset
  /// for the next page so pagination math stays correct even when
  /// the visible list is shorter due to filtering.
  int _serverFetchedCount = 0;

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
      // First page only. Pull-to-refresh and cold-start both reset
      // pagination here; loadMoreStories appends subsequent pages.
      // We filter drafts client-side so legacy server-side drafts
      // (pre-local-first refactor) don't double-show under both
      // localDrafts and serverStories.
      final stories = await _api.listStories(offset: 0, limit: _pageSize);
      // Cache the full server response (including any server-side
      // drafts) so a re-seed on next launch matches what we'd fetch.
      await _cache.replaceAll(stories);
      _serverFetchedCount = stories.length;
      state = state.copyWith(
        serverStories: stories.where((s) => s.status != 'draft').toList(),
        // Got a full page → there's likely more to fetch. If the
        // first page was short the list ends here.
        hasMoreStories: stories.length == _pageSize,
        isLoading: false,
        isLoadingMore: false,
      );
    } catch (e) {
      // Keep cache contents in state on failure; surface error to UI.
      state = state.copyWith(isLoading: false, error: 'Failed to load stories');
    }
  }

  /// Fetch the next page of server stories and append to the list.
  /// Called by the home / all-news scroll listener when the reporter
  /// scrolls within ~400px of the bottom of an unbounded list.
  ///
  /// No-ops when:
  ///   - we already know there are no more pages ([hasMoreStories] false)
  ///   - a previous loadMore is still in flight
  ///   - the cold-start fetch hasn't completed yet
  ///
  /// On failure we just stop offering more pages this session — the
  /// reporter can pull-to-refresh to reset pagination from the top.
  Future<void> loadMoreStories() async {
    if (!state.hasMoreStories) return;
    if (state.isLoadingMore) return;
    if (state.isLoading) return;

    state = state.copyWith(isLoadingMore: true, clearError: true);
    try {
      final more = await _api.listStories(
        offset: _serverFetchedCount,
        limit: _pageSize,
      );
      _serverFetchedCount += more.length;
      // Upsert the new rows into cache so the next cold-start has a
      // longer pre-fetched list to render instantly. We don't replace
      // — that would clobber page 1.
      for (final s in more) {
        await _cache.upsert(s);
      }
      final newVisible =
          more.where((s) => s.status != 'draft').toList(growable: false);
      state = state.copyWith(
        serverStories: [...state.serverStories, ...newVisible],
        hasMoreStories: more.length == _pageSize,
        isLoadingMore: false,
      );
    } catch (_) {
      // Don't surface as an error toast — failing a "load more" is a
      // soft failure compared to a cold-start fetch. Just stop offering
      // more pages so the user knows the bottom-of-list spinner shouldn't
      // keep spinning.
      state = state.copyWith(
        isLoadingMore: false,
        hasMoreStories: false,
      );
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
