import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/services/api_service.dart';

// =============================================================================
// State
// =============================================================================

class FilesState {
  final List<Map<String, dynamic>> files;
  final bool isLoading;
  final String? error;

  const FilesState({
    this.files = const [],
    this.isLoading = false,
    this.error,
  });

  FilesState copyWith({
    List<Map<String, dynamic>>? files,
    bool? isLoading,
    String? error,
    bool clearError = false,
  }) {
    return FilesState(
      files: files ?? this.files,
      isLoading: isLoading ?? this.isLoading,
      error: clearError ? null : (error ?? this.error),
    );
  }

  /// Files grouped by media type.
  List<Map<String, dynamic>> get voiceNotes =>
      files.where((f) => f['media_type'] == 'audio').toList();

  List<Map<String, dynamic>> get photos =>
      files.where((f) => f['media_type'] == 'photo').toList();

  List<Map<String, dynamic>> get videos =>
      files.where((f) => f['media_type'] == 'video').toList();

  List<Map<String, dynamic>> get documents =>
      files.where((f) => f['media_type'] == 'document').toList();
}

// =============================================================================
// Notifier
// =============================================================================

class FilesNotifier extends Notifier<FilesState> {
  @override
  FilesState build() => const FilesState();

  Future<void> fetchFiles() async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final api = ref.read(apiServiceProvider);
      final files = await api.listFiles();
      state = state.copyWith(files: files, isLoading: false);
    } catch (_) {
      // No files or API error — show empty state, not an error
      state = state.copyWith(files: [], isLoading: false);
    }
  }
}

// =============================================================================
// Provider
// =============================================================================

final filesProvider =
    NotifierProvider<FilesNotifier, FilesState>(FilesNotifier.new);
