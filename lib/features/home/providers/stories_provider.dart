import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/services/api_service.dart';

class StoriesState {
  final List<StoryDto> stories;
  final bool isLoading;
  final String? error;

  const StoriesState({
    this.stories = const [],
    this.isLoading = false,
    this.error,
  });

  List<StoryDto> get drafts =>
      stories.where((s) => s.status == 'draft').toList();
  List<StoryDto> get submitted =>
      stories.where((s) => s.status != 'draft').toList();

  StoriesState copyWith({
    List<StoryDto>? stories,
    bool? isLoading,
    String? error,
    bool clearError = false,
  }) {
    return StoriesState(
      stories: stories ?? this.stories,
      isLoading: isLoading ?? this.isLoading,
      error: clearError ? null : (error ?? this.error),
    );
  }
}

class StoriesNotifier extends Notifier<StoriesState> {
  @override
  StoriesState build() => const StoriesState();

  ApiService get _api => ref.read(apiServiceProvider);

  Future<void> fetchStories() async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final stories = await _api.listStories();
      state = StoriesState(stories: stories);
    } catch (e) {
      state = state.copyWith(isLoading: false, error: 'Failed to load stories');
    }
  }

  Future<StoryDto?> createStory() async {
    try {
      return await _api.createStory();
    } catch (_) {
      return null;
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
      final updated = state.stories.where((s) => s.id != storyId).toList();
      state = state.copyWith(stories: updated);
      return true;
    } catch (_) {
      return false;
    }
  }
}

final storiesProvider =
    NotifierProvider<StoriesNotifier, StoriesState>(StoriesNotifier.new);
