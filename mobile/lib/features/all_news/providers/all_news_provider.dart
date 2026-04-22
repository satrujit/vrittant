import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/services/api_service.dart';

class AllNewsFilters {
  final String? status;
  final String? category;
  final String? search;
  final DateTime? dateFrom;
  final DateTime? dateTo;

  const AllNewsFilters({
    this.status,
    this.category,
    this.search,
    this.dateFrom,
    this.dateTo,
  });

  AllNewsFilters copyWith({
    String? status,
    bool clearStatus = false,
    String? category,
    bool clearCategory = false,
    String? search,
    bool clearSearch = false,
    DateTime? dateFrom,
    bool clearDateFrom = false,
    DateTime? dateTo,
    bool clearDateTo = false,
  }) {
    return AllNewsFilters(
      status: clearStatus ? null : (status ?? this.status),
      category: clearCategory ? null : (category ?? this.category),
      search: clearSearch ? null : (search ?? this.search),
      dateFrom: clearDateFrom ? null : (dateFrom ?? this.dateFrom),
      dateTo: clearDateTo ? null : (dateTo ?? this.dateTo),
    );
  }

  String? get dateFromStr => dateFrom != null
      ? '${dateFrom!.year}-${dateFrom!.month.toString().padLeft(2, '0')}-${dateFrom!.day.toString().padLeft(2, '0')}'
      : null;

  String? get dateToStr => dateTo != null
      ? '${dateTo!.year}-${dateTo!.month.toString().padLeft(2, '0')}-${dateTo!.day.toString().padLeft(2, '0')}'
      : null;

  bool get hasActiveFilters =>
      status != null || category != null || dateFrom != null || dateTo != null;
}

class AllNewsState {
  final List<StoryDto> stories;
  final bool isLoading;
  final bool hasMore;
  final String? error;
  final AllNewsFilters filters;

  const AllNewsState({
    this.stories = const [],
    this.isLoading = false,
    this.hasMore = true,
    this.error,
    this.filters = const AllNewsFilters(),
  });

  AllNewsState copyWith({
    List<StoryDto>? stories,
    bool? isLoading,
    bool? hasMore,
    String? error,
    bool clearError = false,
    AllNewsFilters? filters,
  }) {
    return AllNewsState(
      stories: stories ?? this.stories,
      isLoading: isLoading ?? this.isLoading,
      hasMore: hasMore ?? this.hasMore,
      error: clearError ? null : (error ?? this.error),
      filters: filters ?? this.filters,
    );
  }
}

class AllNewsNotifier extends Notifier<AllNewsState> {
  static const _pageSize = 20;

  Timer? _searchDebounce;

  @override
  AllNewsState build() => const AllNewsState();

  ApiService get _api => ref.read(apiServiceProvider);

  Future<void> fetchStories() async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final f = state.filters;
      final stories = await _api.listStories(
        status: f.status,
        category: f.category,
        search: f.search,
        dateFrom: f.dateFromStr,
        dateTo: f.dateToStr,
        offset: 0,
        limit: _pageSize,
      );
      state = AllNewsState(
        stories: stories,
        hasMore: stories.length >= _pageSize,
        filters: f,
      );
    } catch (e) {
      state = state.copyWith(isLoading: false, error: 'Failed to load stories');
    }
  }

  Future<void> loadMore() async {
    if (state.isLoading || !state.hasMore) return;
    state = state.copyWith(isLoading: true);
    try {
      final f = state.filters;
      final moreStories = await _api.listStories(
        status: f.status,
        category: f.category,
        search: f.search,
        dateFrom: f.dateFromStr,
        dateTo: f.dateToStr,
        offset: state.stories.length,
        limit: _pageSize,
      );
      state = state.copyWith(
        stories: [...state.stories, ...moreStories],
        isLoading: false,
        hasMore: moreStories.length >= _pageSize,
      );
    } catch (_) {
      state = state.copyWith(isLoading: false);
    }
  }

  void setFilters(AllNewsFilters filters) {
    state = state.copyWith(filters: filters);
    fetchStories();
  }

  void setSearch(String query) {
    _searchDebounce?.cancel();
    final newFilters = query.isEmpty
        ? state.filters.copyWith(clearSearch: true)
        : state.filters.copyWith(search: query);
    state = state.copyWith(filters: newFilters);
    _searchDebounce = Timer(const Duration(milliseconds: 500), () {
      fetchStories();
    });
  }

  void setStatus(String? status) {
    setFilters(status == null
        ? state.filters.copyWith(clearStatus: true)
        : state.filters.copyWith(status: status));
  }

  void setCategory(String? category) {
    setFilters(category == null
        ? state.filters.copyWith(clearCategory: true)
        : state.filters.copyWith(category: category));
  }

  void setDateRange(DateTime? from, DateTime? to) {
    setFilters(state.filters.copyWith(
      dateFrom: from,
      clearDateFrom: from == null,
      dateTo: to,
      clearDateTo: to == null,
    ));
  }

  void clearAllFilters() {
    setFilters(const AllNewsFilters());
  }
}

final allNewsProvider =
    NotifierProvider<AllNewsNotifier, AllNewsState>(AllNewsNotifier.new);
