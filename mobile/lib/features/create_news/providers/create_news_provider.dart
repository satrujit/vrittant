import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

import 'package:flutter/foundation.dart' show debugPrint, kIsWeb;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';

import '../../../core/services/api_service.dart';
import '../../../core/services/audio_upload_queue.dart';
import '../../../core/services/enrollment_storage.dart';
import '../../../core/services/file_picker_service.dart';
import '../../../core/services/local_drafts_store.dart';
import '../../../core/services/local_stories_cache.dart';
import '../../../core/services/sarvam_api.dart';
import '../../../core/services/stt_service.dart';
import '../../auth/providers/auth_provider.dart';
import '../../../core/l10n/language_provider.dart';

// =============================================================================
// Shared constants
// =============================================================================

/// Global fallback category list, used when the reporter's org hasn't defined
/// its own master list. Kept here (single source of truth) and consumed by
/// both the LLM categoriser and the manual category picker UI.
const kDefaultCategoryKeys = <String>[
  'politics',
  'sports',
  'crime',
  'business',
  'entertainment',
  'education',
  'health',
  'technology',
  'disaster',
  'other',
];

// =============================================================================
// Utility: Roman → Odia numeral conversion
// =============================================================================

/// Converts Roman/Arabic digits (0-9) to Odia digits (୦-୯).
String toOdiaDigits(String text) {
  const map = {
    '0': '\u0B66', // ୦
    '1': '\u0B67', // ୧
    '2': '\u0B68', // ୨
    '3': '\u0B69', // ୩
    '4': '\u0B6A', // ୪
    '5': '\u0B6B', // ୫
    '6': '\u0B6C', // ୬
    '7': '\u0B6D', // ୭
    '8': '\u0B6E', // ୮
    '9': '\u0B6F', // ୯
  };
  return text.replaceAllMapped(
    RegExp(r'[0-9]'),
    (m) => map[m[0]!] ?? m[0]!,
  );
}

// =============================================================================
// Paragraph model
// =============================================================================


/// A content block in the notepad. Can be a text paragraph or a media block.
class Paragraph {
  final String id;
  final String text;
  final String? mediaPath; // null = text paragraph, non-null = media block
  final MediaType? mediaType; // type of attached media
  final String? mediaName; // display name for the attachment
  final List<List<String>>? tableData; // 2D array for table paragraphs
  final DateTime createdAt;

  // ── Transcription metadata (server-side, populated on load) ──
  // Set when the always-upload pipeline saved an audio backup for this
  // paragraph. The Retranscribe action only surfaces when audio exists.
  // `transcriptionStatus` mirrors the server enum: pending | ok | failed.
  final String? transcriptionAudioPath;
  final String? transcriptionStatus;

  const Paragraph({
    required this.id,
    this.text = '',
    this.mediaPath,
    this.mediaType,
    this.mediaName,
    this.tableData,
    required this.createdAt,
    this.transcriptionAudioPath,
    this.transcriptionStatus,
  });

  Paragraph copyWith({
    String? text,
    String? mediaPath,
    MediaType? mediaType,
    String? mediaName,
    List<List<String>>? tableData,
    bool clearTableData = false,
    String? transcriptionAudioPath,
    String? transcriptionStatus,
  }) {
    return Paragraph(
      id: id,
      text: text ?? this.text,
      mediaPath: mediaPath ?? this.mediaPath,
      mediaType: mediaType ?? this.mediaType,
      mediaName: mediaName ?? this.mediaName,
      tableData: clearTableData ? null : (tableData ?? this.tableData),
      createdAt: createdAt,
      transcriptionAudioPath: transcriptionAudioPath ?? this.transcriptionAudioPath,
      transcriptionStatus: transcriptionStatus ?? this.transcriptionStatus,
    );
  }

  /// Re-transcription is meaningful only when we know there's audio on the
  /// server and the live transcript looks broken (empty after some attempt).
  /// We're permissive on what "broken" means — show the option whenever:
  ///   - audio backup exists, AND
  ///   - status is failed OR text is empty/very short (≤3 chars)
  /// Reporters can always tap it; backend re-runs Sarvam against the saved WAV.
  bool get canRetranscribe {
    if (transcriptionAudioPath == null) return false;
    if (transcriptionStatus == 'failed') return true;
    return text.trim().length <= 3;
  }

  /// Whether this paragraph holds a photo (vs. text/audio/etc.).
  bool get isPhoto => mediaPath != null && mediaType == MediaType.photo;

  /// Whether this paragraph has any media attached.
  bool get hasMedia => mediaPath != null;

  /// Whether this paragraph is a table block.
  bool get isTable => tableData != null && tableData!.isNotEmpty;

  /// Serialise to the same shape the backend expects in the
  /// `paragraphs` field of a story payload. Used both for the local
  /// Hive draft store and for the eventual server POST on submit.
  ///
  /// Mirrors the inline serialisation that used to live in
  /// `_syncToServer`; centralised here so local + server payloads stay
  /// identical.
  Map<String, dynamic> toJson() {
    // Never persist base64 data URLs (they bloat both Hive and the
    // server payload and aren't valid file paths anyway).
    final path =
        (mediaPath != null && mediaPath!.startsWith('data:')) ? null : mediaPath;
    return {
      'id': id,
      'text': text,
      'media_path': path,
      'media_type': path != null ? mediaType?.name : null,
      'media_name': path != null ? mediaName : null,
      'table_data': tableData,
      'created_at': createdAt.toIso8601String(),
      if (transcriptionAudioPath != null)
        'transcription_audio_path': transcriptionAudioPath,
      if (transcriptionStatus != null)
        'transcription_status': transcriptionStatus,
    };
  }

  /// Inverse of [toJson] / the server paragraph shape. Used when
  /// rehydrating a draft from Hive or loading a story from the API.
  factory Paragraph.fromMap(Map<String, dynamic> p) {
    final mediaTypeStr = p['media_type'] as String?;
    MediaType? mediaType;
    if (mediaTypeStr != null) {
      mediaType =
          MediaType.values.where((e) => e.name == mediaTypeStr).firstOrNull;
    }
    // Backward compat: read old photo_path field
    final mediaPath =
        p['media_path'] as String? ?? p['photo_path'] as String?;
    if (mediaPath != null && mediaType == null) {
      mediaType = MediaType.photo;
    }

    List<List<String>>? tableData;
    final rawTable = p['table_data'];
    if (rawTable is List) {
      tableData = rawTable
          .map((row) => (row as List).map((c) => c.toString()).toList())
          .toList();
    }

    return Paragraph(
      id: p['id'] as String? ??
          DateTime.now().millisecondsSinceEpoch.toString(),
      text: p['text'] as String? ?? '',
      mediaPath: mediaPath,
      mediaType: mediaType,
      mediaName: p['media_name'] as String?,
      tableData: tableData,
      createdAt: p['created_at'] != null
          ? DateTime.tryParse(p['created_at'] as String) ?? DateTime.now()
          : DateTime.now(),
      transcriptionAudioPath: p['transcription_audio_path'] as String?,
      transcriptionStatus: p['transcription_status'] as String?,
    );
  }
}

// =============================================================================
// State
// =============================================================================

class NotepadState {
  final String headline; // AI auto-generated, editable
  final String? displayId; // server-computed "PNS-26-1234"; null for new drafts
  final String? category; // AI auto-inferred (String, not enum)
  final String? location; // AI auto-inferred
  final List<Paragraph> paragraphs;
  final bool isRecording;
  final String liveTranscript; // current recording session
  final Duration recordingDuration;
  final int? editingParagraphIndex; // which paragraph is selected for edit
  final int? insertAtIndex; // where to insert next recording (null = append)
  final int? cursorInsertParagraphIndex; // insert into existing paragraph at cursor
  final int? cursorInsertPosition; // cursor offset within that paragraph
  final bool isGeneratingTitle;
  final bool isProcessing;
  final String? error;
  final bool isSpeechEditing;
  final String speechEditTranscript;
  final bool isOcrProcessing;
  final double ocrProgress;
  final int? improvingParagraphIndex; // which paragraph is being AI-improved
  final int? improvingSelStart; // selection start within paragraph (null = whole)
  final int? improvingSelEnd;   // selection end within paragraph
  /// IDs (not indices) of paragraphs currently being auto-polished by the LLM.
  /// Keyed by ID so reorders/deletes during the in-flight polish don't mis-attribute
  /// the result to the wrong paragraph.
  final Set<String> polishingParagraphIds;
  final bool isAudioSaveMode; // long-press: also save audio file
  final bool isNoisyEnvironment; // ambient noise is high
  final bool speakerFilterActive; // speaker verification is filtering audio
  final bool isSpeakerVerified; // current speaker matches enrolled voice
  /// Snapshot of the reporter's raw input (paragraphs joined) at the moment
  /// they tap Generate Story. Preserved as the "User Notes" provenance trail
  /// so reviewers can see exactly what the reporter said before AI rewrote it.
  final String? userNotes;
  final bool isGeneratingStory;
  /// Set when the parent screen wants the body editor to grab keyboard
  /// focus on a specific paragraph (e.g. after the user taps "Type" in
  /// the empty state, which adds an empty paragraph and then needs the
  /// keyboard to come up). The body clears this after requesting focus
  /// so it only fires once per signal.
  final int? pendingFocusParagraphIndex;

  /// Canonical text of the article body immediately after the last
  /// successful AI Refine. Used by the FAB to disable itself when the
  /// reporter hasn't changed anything since the last refine — re-running
  /// the LLM on identical input wastes a server round-trip and cents,
  /// and produces an output that's almost always indistinguishable
  /// from the previous one. The moment the reporter edits anything,
  /// the canonical text drifts from this snapshot and the button
  /// re-enables. Cleared on draft load (paragraphs reset → mismatch).
  final String? lastRefineSnapshot;

  const NotepadState({
    this.headline = '',
    this.displayId,
    this.category,
    this.location,
    this.paragraphs = const [],
    this.isRecording = false,
    this.liveTranscript = '',
    this.recordingDuration = Duration.zero,
    this.editingParagraphIndex,
    this.insertAtIndex,
    this.cursorInsertParagraphIndex,
    this.cursorInsertPosition,
    this.isGeneratingTitle = false,
    this.isProcessing = false,
    this.error,
    this.isSpeechEditing = false,
    this.speechEditTranscript = '',
    this.isOcrProcessing = false,
    this.ocrProgress = 0.0,
    this.improvingParagraphIndex,
    this.improvingSelStart,
    this.improvingSelEnd,
    this.polishingParagraphIds = const {},
    this.isAudioSaveMode = false,
    this.isNoisyEnvironment = false,
    this.speakerFilterActive = false,
    this.isSpeakerVerified = true,
    this.userNotes,
    this.isGeneratingStory = false,
    this.pendingFocusParagraphIndex,
    this.lastRefineSnapshot,
  });

  /// The reporter's current article body as a single canonical string
  /// (paragraphs joined by blank lines, media/table rows excluded).
  /// Used both as the input to AI Refine AND as the snapshot we compare
  /// against [lastRefineSnapshot] to decide whether the FAB is stale.
  String get canonicalBodyText => paragraphs
      .where((p) => !p.hasMedia && !p.isTable && p.text.trim().isNotEmpty)
      .map((p) => p.text.trim())
      .join('\n\n');

  /// True when the reporter has edited the body since the last AI
  /// Refine ran (or has never refined yet). When false, the FAB is
  /// disabled — running again on identical input would just waste an
  /// LLM call. The comparison is on the canonical text so paragraph
  /// reorders / whitespace tweaks that change rendering but not
  /// content don't accidentally re-enable the button (and conversely,
  /// genuine edits always do).
  bool get isRefineStale {
    final snapshot = lastRefineSnapshot;
    if (snapshot == null) return true; // never refined → always enabled
    return canonicalBodyText != snapshot;
  }

  NotepadState copyWith({
    String? headline,
    String? displayId,
    String? category,
    bool clearCategory = false,
    String? location,
    bool clearLocation = false,
    List<Paragraph>? paragraphs,
    bool? isRecording,
    String? liveTranscript,
    Duration? recordingDuration,
    int? editingParagraphIndex,
    bool clearEditingParagraphIndex = false,
    int? insertAtIndex,
    bool clearInsertAtIndex = false,
    int? cursorInsertParagraphIndex,
    int? cursorInsertPosition,
    bool clearCursorInsert = false,
    bool? isGeneratingTitle,
    bool? isProcessing,
    String? error,
    bool clearError = false,
    bool? isSpeechEditing,
    String? speechEditTranscript,
    bool? isOcrProcessing,
    double? ocrProgress,
    int? improvingParagraphIndex,
    bool clearImprovingParagraphIndex = false,
    int? improvingSelStart,
    int? improvingSelEnd,
    Set<String>? polishingParagraphIds,
    bool? isAudioSaveMode,
    bool? isNoisyEnvironment,
    bool? speakerFilterActive,
    bool? isSpeakerVerified,
    String? userNotes,
    bool clearUserNotes = false,
    bool? isGeneratingStory,
    int? pendingFocusParagraphIndex,
    bool clearPendingFocus = false,
    String? lastRefineSnapshot,
    bool clearLastRefineSnapshot = false,
  }) {
    return NotepadState(
      headline: headline ?? this.headline,
      displayId: displayId ?? this.displayId,
      category: clearCategory ? null : (category ?? this.category),
      location: clearLocation ? null : (location ?? this.location),
      paragraphs: paragraphs ?? this.paragraphs,
      isRecording: isRecording ?? this.isRecording,
      liveTranscript: liveTranscript ?? this.liveTranscript,
      recordingDuration: recordingDuration ?? this.recordingDuration,
      editingParagraphIndex: clearEditingParagraphIndex
          ? null
          : (editingParagraphIndex ?? this.editingParagraphIndex),
      insertAtIndex: clearInsertAtIndex
          ? null
          : (insertAtIndex ?? this.insertAtIndex),
      cursorInsertParagraphIndex: clearCursorInsert
          ? null
          : (cursorInsertParagraphIndex ?? this.cursorInsertParagraphIndex),
      cursorInsertPosition: clearCursorInsert
          ? null
          : (cursorInsertPosition ?? this.cursorInsertPosition),
      isGeneratingTitle: isGeneratingTitle ?? this.isGeneratingTitle,
      isProcessing: isProcessing ?? this.isProcessing,
      error: clearError ? null : (error ?? this.error),
      isSpeechEditing: isSpeechEditing ?? this.isSpeechEditing,
      speechEditTranscript: speechEditTranscript ?? this.speechEditTranscript,
      isOcrProcessing: isOcrProcessing ?? this.isOcrProcessing,
      ocrProgress: ocrProgress ?? this.ocrProgress,
      improvingParagraphIndex: clearImprovingParagraphIndex
          ? null
          : (improvingParagraphIndex ?? this.improvingParagraphIndex),
      improvingSelStart: clearImprovingParagraphIndex
          ? null
          : (improvingSelStart ?? this.improvingSelStart),
      improvingSelEnd: clearImprovingParagraphIndex
          ? null
          : (improvingSelEnd ?? this.improvingSelEnd),
      polishingParagraphIds: polishingParagraphIds ?? this.polishingParagraphIds,
      isAudioSaveMode: isAudioSaveMode ?? this.isAudioSaveMode,
      isNoisyEnvironment: isNoisyEnvironment ?? this.isNoisyEnvironment,
      speakerFilterActive: speakerFilterActive ?? this.speakerFilterActive,
      isSpeakerVerified: isSpeakerVerified ?? this.isSpeakerVerified,
      userNotes: clearUserNotes ? null : (userNotes ?? this.userNotes),
      isGeneratingStory: isGeneratingStory ?? this.isGeneratingStory,
      pendingFocusParagraphIndex: clearPendingFocus
          ? null
          : (pendingFocusParagraphIndex ?? this.pendingFocusParagraphIndex),
      lastRefineSnapshot: clearLastRefineSnapshot
          ? null
          : (lastRefineSnapshot ?? this.lastRefineSnapshot),
    );
  }

  /// Formatted recording duration as MM:SS.
  String get formattedDuration {
    final minutes =
        recordingDuration.inMinutes.remainder(60).toString().padLeft(2, '0');
    final seconds =
        recordingDuration.inSeconds.remainder(60).toString().padLeft(2, '0');
    return '$minutes:$seconds';
  }
}

// =============================================================================
// Notifier
// =============================================================================

class NotepadNotifier extends Notifier<NotepadState> {
  StreamingSttService? _streamingStt;
  StreamSubscription<SttSegment>? _transcriptSubscription;
  Timer? _recordingTimer;
  final OcrService _ocrService = OcrService();

  /// Server-side story ID (null until the reporter taps Submit and the
  /// story is created on the server).
  String? _serverStoryId;

  /// Local-only id for the in-progress draft. Generated client-side when
  /// the reporter taps + on the home screen, so we can persist to Hive
  /// without any server round-trip. Cleared after a successful submit
  /// (the draft is then represented purely by [_serverStoryId]).
  String? _localId;

  /// Timestamp the local draft was first opened. Persisted in the Hive
  /// payload so re-hydration preserves the original "createdAt" rather
  /// than rewriting it on every save.
  DateTime _localCreatedAt = DateTime.now();

  /// The status of the story on the server (draft, submitted, etc.).
  String _storyStatus = 'draft';

  /// Public accessor for the current server story ID.
  String? get serverStoryId => _serverStoryId;

  /// Public accessor for the local draft id (null when the editor was
  /// opened on a server-side / already-submitted story).
  String? get localId => _localId;

  /// Public accessor for the story status.
  String get storyStatus => _storyStatus;

  /// Generates a fresh local draft id. Format: `<ms>-<rand-hex>` — unique
  /// enough for a single device, no extra dependency required.
  String _newLocalId() {
    final ts = DateTime.now().millisecondsSinceEpoch;
    final rand = Random().nextInt(1 << 32).toRadixString(16);
    return '$ts-$rand';
  }

  /// Pick the right copy for the current UI language. Used for user-facing
  /// error toasts that originate inside the provider (away from any widget).
  String _err(String en, String od) =>
      ref.read(languageProvider) == AppLanguage.odia ? od : en;

  /// Debounce timer for auto-saving to server.
  Timer? _autoSaveTimer;

  /// In-flight title/metadata generation. Tracked so saveBeforeClose can wait
  /// for the LLM to finish before persisting — otherwise the user closes the
  /// screen, the save fires without the headline, and the LLM result lands on
  /// a disposed notifier and is silently lost ("processing in background but
  /// the title never came").
  Future<void>? _titleGenInflight;

  /// Index of the paragraph being re-recorded (null if creating new).
  int? _reRecordingIndex;

  // --- Auto-stop support ---
  /// Last transcript snapshot used for silence detection.
  String _lastTranscriptCheck = '';

  /// When the transcript last changed (for silence timeout).
  DateTime _lastTranscriptChangeTime = DateTime.now();

  // --- Auto-paragraph support ---
  Timer? _autoParagraphTimer;

  // --- Speech edit support ---
  StreamingSttService? _speechEditStt;
  StreamSubscription<SttSegment>? _speechEditSub;

  // --- Undo / Redo support ---
  final List<List<Paragraph>> _undoStack = [];
  final List<List<Paragraph>> _redoStack = [];
  static const int _maxUndoHistory = 30;

  bool get canUndo => _undoStack.isNotEmpty;
  bool get canRedo => _redoStack.isNotEmpty;

  /// Push current paragraphs snapshot onto undo stack before a mutation.
  void _pushUndo() {
    _undoStack.add(List<Paragraph>.from(state.paragraphs));
    if (_undoStack.length > _maxUndoHistory) {
      _undoStack.removeAt(0);
    }
    _redoStack.clear(); // new action invalidates redo history
  }

  void undo() {
    if (!canUndo) return;
    // Push current state onto redo stack
    _redoStack.add(List<Paragraph>.from(state.paragraphs));
    final previous = _undoStack.removeLast();
    state = state.copyWith(
      paragraphs: previous,
      clearEditingParagraphIndex: true,
    );
    _scheduleAutoSave();
  }

  void redo() {
    if (!canRedo) return;
    // Push current state onto undo stack (without clearing redo)
    _undoStack.add(List<Paragraph>.from(state.paragraphs));
    final next = _redoStack.removeLast();
    state = state.copyWith(
      paragraphs: next,
      clearEditingParagraphIndex: true,
    );
    _scheduleAutoSave();
  }

  @override
  NotepadState build() => const NotepadState();

  /// Convenience accessor for the backend API service.
  ApiService get _api => ref.read(apiServiceProvider);

  /// Convenience accessor for the Sarvam API service.
  SarvamApiService get _sarvam {
    final sarvam = ref.read(sarvamApiProvider);
    sarvam.setToken(ref.read(apiServiceProvider).token);
    return sarvam;
  }

  // ---------------------------------------------------------------------------
  // Server sync — init, auto-save, submit
  // ---------------------------------------------------------------------------

  /// Initialize with a new local-only draft. No network call: the draft
  /// lives entirely in Hive until the reporter taps Submit.
  Future<void> initWithNewStory() async {
    // Reset any leftover state from a previous story
    _reRecordingIndex = null;
    _autoSaveTimer?.cancel();
    _autoSaveTimer = null;

    _localId = _newLocalId();
    _localCreatedAt = DateTime.now();
    _serverStoryId = null;
    _storyStatus = 'draft';

    // Set initial location from reporter's tagged area
    final auth = ref.read(authProvider);
    final reporterArea = auth.reporter?.areaName;
    state = NotepadState(
      location: (reporterArea != null && reporterArea.isNotEmpty) ? reporterArea : null,
    );
    debugPrint('[create_news] initWithNewStory OK localId=$_localId');
  }

  /// Initialize from an existing local draft (Hive). Used when the
  /// reporter taps a draft card on the home screen.
  Future<void> initWithLocalDraft(String localId) async {
    _reRecordingIndex = null;
    _autoSaveTimer?.cancel();
    _autoSaveTimer = null;

    final payload = ref.read(localDraftsStoreProvider).load(localId);
    if (payload == null) {
      // The draft was deleted out from under us — fall back to a fresh draft.
      debugPrint('[create_news] initWithLocalDraft MISS localId=$localId — starting new');
      return initWithNewStory();
    }

    _localId = localId;
    _serverStoryId = null;
    _storyStatus = 'draft';

    final createdRaw = payload['created_at'] as String?;
    _localCreatedAt =
        (createdRaw != null ? DateTime.tryParse(createdRaw) : null) ??
            DateTime.now();

    final paragraphsRaw = payload['paragraphs'];
    final paragraphs = paragraphsRaw is List
        ? paragraphsRaw
            .whereType<Map>()
            .map((p) => Paragraph.fromMap(Map<String, dynamic>.from(p)))
            .toList()
        : <Paragraph>[];

    state = NotepadState(
      headline: payload['headline'] as String? ?? '',
      category: payload['category'] as String?,
      location: payload['location'] as String?,
      paragraphs: paragraphs,
      userNotes: payload['user_notes'] as String?,
    );
    debugPrint('[create_news] initWithLocalDraft OK localId=$_localId paragraphs=${paragraphs.length}');
  }

  /// Initialize from an existing server-side story. Used when the
  /// reporter taps an already-submitted story on the home screen.
  /// Local-only drafts go through [initWithLocalDraft] instead.
  ///
  /// Stale-while-revalidate: the home / all-news lists already cached
  /// every story they fetched (paragraphs included) into Hive via
  /// [LocalStoriesCache]. We seed the editor from that cache
  /// synchronously so content appears instantly on tap, then refresh
  /// from the server in the background to pick up any reviewer edits
  /// that happened since the last list fetch.
  ///
  /// The server response wins on success — we only fall back to the
  /// "cache only" experience when the network call fails. That covers
  /// offline reporters cleanly: they still see their story (read-only,
  /// effectively) and can re-open it later when online to refresh.
  Future<void> initWithExistingStory(String storyId) async {
    _localId = null;
    _serverStoryId = storyId;

    // ── Cache hydrate (synchronous, instant UI) ─────────────────────
    final cached = ref.read(localStoriesCacheProvider).find(storyId);
    if (cached != null) {
      _storyStatus = cached.status;
      final paragraphs =
          cached.paragraphs.map((p) => Paragraph.fromMap(p)).toList();
      state = NotepadState(
        headline: cached.headline,
        displayId: cached.displayId,
        category: cached.category,
        location: cached.location,
        paragraphs: paragraphs,
      );
    }

    // ── Server refresh (async, replaces cached body on success) ────
    try {
      final story = await _api.getStory(storyId);
      _storyStatus = story.status;

      final paragraphs =
          story.paragraphs.map((p) => Paragraph.fromMap(p)).toList();

      state = NotepadState(
        headline: story.headline,
        displayId: story.displayId,
        category: story.category,
        location: story.location,
        paragraphs: paragraphs,
      );
      // Refresh the cache row so the next cold-open of this story
      // shows the post-edit content even if the home list hasn't
      // been refreshed since.
      await ref.read(localStoriesCacheProvider).upsert(story);
    } catch (_) {
      // If we already hydrated from cache, leave the user inside the
      // story rather than blanking the screen with an error. Only
      // surface the error when we genuinely have nothing to show.
      if (cached == null) {
        state = state.copyWith(error: 'Failed to load story');
      }
    }
  }

  /// Silent backup: hand the raw WAV to the persistent upload queue so the
  /// server can re-transcribe later if the live Sarvam path returned nothing.
  /// Fire-and-forget — every failure path falls back to "do nothing" because
  /// the user already has the live transcript on screen.
  ///
  /// `is_attachment=false` here: tap-dictation audio is silent backup only,
  /// not a playable media block. The long-press path uploads separately via
  /// `/files/upload` (unchanged) and remains the user-visible attachment.
  void _queueSilentBackupAudio(String paragraphId, Uint8List? wavBytes) {
    if (kIsWeb) return;
    if (wavBytes == null || wavBytes.isEmpty) return;
    final storyId = _serverStoryId;
    if (storyId == null) return;

    // Run async without awaiting — the recording-stop path must stay snappy.
    () async {
      try {
        final dir = await getTemporaryDirectory();
        final ts = DateTime.now().millisecondsSinceEpoch;
        final path = '${dir.path}/stt_backup_${ts}_$paragraphId.wav';
        final file = File(path);
        await file.writeAsBytes(wavBytes, flush: true);
        await AudioUploadQueue.instance(_api).enqueue(
          sourceFilePath: path,
          storyId: storyId,
          paragraphId: paragraphId,
          isAttachment: false,
          languageCode: 'od-IN',
        );
      } catch (e) {
        debugPrint('[create_news] silent backup enqueue failed: $e');
      }
    }();
  }

  /// Debounced auto-save to local storage.
  void _scheduleAutoSave() {
    _autoSaveTimer?.cancel();
    _autoSaveTimer = Timer(const Duration(milliseconds: 800), () {
      _persistDraft();
    });
  }

  /// Local-first persistence: write the current editor state to the Hive
  /// drafts box. No network call. The server only learns about the story
  /// when the reporter taps Submit (see [submitStory]).
  Future<void> _persistDraft() async {
    if (_localId == null) {
      // Editor is bound to a server-side / already-submitted story. The
      // PUT-update path lives in [saveBeforeClose] for that case; auto-save
      // is intentionally a no-op here.
      return;
    }
    try {
      final payload = <String, dynamic>{
        'local_id': _localId,
        'headline': state.headline,
        'category': state.category,
        'location': state.location,
        'paragraphs': state.paragraphs.map((p) => p.toJson()).toList(),
        'user_notes': state.userNotes,
        'created_at': _localCreatedAt.toIso8601String(),
        'updated_at': DateTime.now().toIso8601String(),
      };
      await ref.read(localDraftsStoreProvider).save(_localId!, payload);
      debugPrint('[create_news] _persistDraft OK localId=$_localId paragraphs=${state.paragraphs.length}');
    } catch (e) {
      debugPrint('[create_news] _persistDraft FAILED localId=$_localId: $e');
    }
  }

  /// Whether the story has any meaningful content worth saving.
  bool get _hasContent =>
      state.headline.isNotEmpty ||
      state.paragraphs.any((p) => p.text.isNotEmpty || p.hasMedia || p.isTable);

  /// Flushes any pending changes, then resets local state. For local
  /// drafts: writes to Hive (or deletes the draft if empty). For
  /// already-submitted stories opened for edit: PUTs to server (existing
  /// behaviour, kept intact).
  Future<void> saveBeforeClose() async {
    debugPrint('[create_news] saveBeforeClose localId=$_localId serverId=$_serverStoryId hasContent=$_hasContent status=$_storyStatus');
    _autoSaveTimer?.cancel();
    _autoSaveTimer = null;
    // Wait for any in-flight title/metadata generation so the persisted save
    // includes the LLM-generated headline. The dialog the user just saw said
    // "processing in progress — your story will be safe if you leave"; that
    // promise is only true if we actually flush the LLM result.
    final pending = _titleGenInflight;
    if (pending != null) {
      debugPrint('[create_news] saveBeforeClose awaiting in-flight title/metadata gen');
      try {
        await pending;
      } catch (_) {
        // already swallowed inside _generateTitleAndMetadata
      }
      // The completed gen re-armed the auto-save debounce timer. Cancel it
      // again — we're about to flush directly and don't want a stray timer
      // firing on a soon-to-be-disposed notifier.
      _autoSaveTimer?.cancel();
      _autoSaveTimer = null;
    }

    if (_localId != null && !_hasContent && _storyStatus == 'draft') {
      // Empty local draft — discard it without ever touching the server.
      try {
        await ref.read(localDraftsStoreProvider).delete(_localId!);
        debugPrint('[create_news] saveBeforeClose discarded empty local draft');
      } catch (e) {
        debugPrint('[create_news] saveBeforeClose discard FAILED: $e');
      }
      _localId = null;
    } else if (_localId != null) {
      // Local draft with content — flush to Hive.
      await _persistDraft();
    } else if (_serverStoryId != null && _hasContent) {
      // Editing an already-submitted server-side story. Existing PUT
      // path so reviewers see the latest edits. (Local-first refactor
      // doesn't touch this flow.)
      try {
        await _api.updateStory(
          _serverStoryId!,
          headline: state.headline,
          category: state.category,
          location: state.location,
          paragraphs: state.paragraphs.map((p) => p.toJson()).toList(),
        );
        debugPrint('[create_news] saveBeforeClose PUT existing story OK id=$_serverStoryId');
      } catch (e) {
        debugPrint('[create_news] saveBeforeClose PUT existing story FAILED: $e');
      }
    }
  }

  /// Re-entrancy guard for submitStory — prevents the user spam-tapping
  /// "Submit" from creating a duplicate submission while the network call
  /// is in flight.
  bool _isSubmitting = false;

  /// Submit the story to the backend. First server interaction in the
  /// new local-first flow: POST /stories with the full payload, then
  /// POST /stories/:id/submit, then drop the local draft.
  Future<bool> submitStory() async {
    if (_isSubmitting) return false;
    _isSubmitting = true;
    try {
      // Flush latest content to Hive first so we don't lose anything if
      // the network call partially succeeds (e.g. createStory OK, submit
      // fails — the local copy is still on disk for the retry).
      await _persistDraft();

      // First server interaction: create the story with full payload.
      final created = await _api.createStory(
        headline: state.headline,
        category: state.category,
        location: state.location,
        paragraphs: state.paragraphs.map((p) => p.toJson()).toList(),
      );
      _serverStoryId = created.id;
      debugPrint('[create_news] submitStory created serverStoryId=$_serverStoryId displayId=${created.displayId}');

      // Flip to submitted.
      await _api.submitStory(created.id);

      // Server has it now — drop the local draft.
      if (_localId != null) {
        try {
          await ref.read(localDraftsStoreProvider).delete(_localId!);
        } catch (e) {
          debugPrint('[create_news] submitStory local delete FAILED: $e');
        }
        _localId = null;
      }
      _storyStatus = 'submitted';
      return true;
    } catch (e) {
      // Network blip / auth blip / server 5xx — keep the local draft
      // intact so the reporter can retry. Surface a UI error.
      debugPrint('[create_news] submitStory FAILED: $e');
      state = state.copyWith(error: 'Failed to submit story');
      return false;
    } finally {
      _isSubmitting = false;
    }
  }

  /// Re-run STT against the saved audio for a paragraph and replace its text.
  ///
  /// Used by the manual "Retranscribe" affordance. Returns true if the text
  /// was updated, false on failure (including no-audio-on-server). Surfaces
  /// errors via state.error so the UI can show a snack.
  Future<bool> retranscribeParagraph(int index) async {
    if (index < 0 || index >= state.paragraphs.length) return false;
    final paragraph = state.paragraphs[index];
    if (_serverStoryId == null) return false;
    if (paragraph.transcriptionAudioPath == null) return false;

    state = state.copyWith(isProcessing: true, clearError: true);
    try {
      final transcript = await _api.retranscribeParagraph(
        storyId: _serverStoryId!,
        paragraphId: paragraph.id,
      );
      if (transcript.trim().isEmpty) {
        state = state.copyWith(
          isProcessing: false,
          error: 'Could not retranscribe — try again later',
        );
        return false;
      }
      final updated = [...state.paragraphs];
      updated[index] = paragraph.copyWith(
        text: transcript,
        transcriptionStatus: 'ok',
      );
      state = state.copyWith(paragraphs: updated, isProcessing: false);
      _scheduleAutoSave();
      return true;
    } catch (e) {
      debugPrint('[create_news] retranscribe failed: $e');
      state = state.copyWith(
        isProcessing: false,
        error: 'Retranscribe failed — try again later',
      );
      return false;
    }
  }

  // ---------------------------------------------------------------------------
  // Computed getters
  // ---------------------------------------------------------------------------

  /// Joins all text paragraphs with double newlines.
  String get fullBodyText =>
      state.paragraphs
          .where((p) => !p.isPhoto && p.text.isNotEmpty)
          .map((p) => p.text)
          .join('\n\n');

  /// Whether the notepad has enough content to submit.
  bool get canSubmit =>
      state.headline.isNotEmpty &&
      state.paragraphs.any((p) => p.text.isNotEmpty);

  // ---------------------------------------------------------------------------
  // Recording toggle
  // ---------------------------------------------------------------------------

  /// Toggles recording on/off.
  /// START: opens streaming WebSocket + mic, transcripts arrive in real-time.
  /// STOP: creates or replaces a Paragraph from liveTranscript.
  /// [saveAudio] — when true (long-press), also saves WAV and inserts an
  /// audio media block below the text paragraph.
  Future<void> toggleRecording({bool saveAudio = false}) async {
    if (state.isRecording) {
      // === STOP recording ===
      _stopTimer();
      final wasAudioSave = state.isAudioSaveMode;
      state = state.copyWith(
        isRecording: false,
        isProcessing: true,
        clearError: true,
        isAudioSaveMode: false,
        isNoisyEnvironment: false,
        speakerFilterActive: false,
        isSpeakerVerified: true,
      );

      try {
        // Grab WAV bytes BEFORE stopping (buffer is cleared on dispose).
        // Always-upload pipeline: we capture the audio for every recording,
        // not just long-press, so the server has it as a silent fallback if
        // the live WS transcript came back empty / wrong. The wasAudioSave
        // flag still controls the *visible* attachment block below.
        final wavBytes = _streamingStt?.getRecordedWavBytes();

        await _streamingStt?.stop();
        _transcriptSubscription?.cancel();
        _transcriptSubscription = null;

        final transcript = toOdiaDigits(state.liveTranscript.trim());

        if (transcript.isEmpty) {
          state = state.copyWith(
            isProcessing: false,
            error: 'Could not detect speech. Please try again.',
          );
          _reRecordingIndex = null;
          _streamingStt?.dispose();
          _streamingStt = null;
          return;
        }

        _pushUndo();

        // Track which paragraph to auto-polish after insertion
        int? polishTargetIndex;

        if (_reRecordingIndex != null) {
          // Re-recording: replace existing paragraph's text
          final idx = _reRecordingIndex!;
          _reRecordingIndex = null;
          if (idx >= 0 && idx < state.paragraphs.length) {
            final updated = List<Paragraph>.from(state.paragraphs);
            updated[idx] = updated[idx].copyWith(text: transcript);
            state = state.copyWith(
              paragraphs: updated,
              isProcessing: false,
              clearEditingParagraphIndex: true,
            );
            polishTargetIndex = idx;
            // Silent-backup audio upload — see comment in "new text paragraph"
            // branch below for why this fires for every recording.
            _queueSilentBackupAudio(updated[idx].id, wavBytes);
          } else {
            state = state.copyWith(isProcessing: false);
          }
        } else if (state.cursorInsertParagraphIndex != null &&
                   state.cursorInsertPosition != null) {
          // Cursor insertion: splice text into existing paragraph
          // Skip auto-polish for cursor splices — it's partial insertion
          final pIdx = state.cursorInsertParagraphIndex!;
          final cursorPos = state.cursorInsertPosition!;
          if (pIdx >= 0 && pIdx < state.paragraphs.length) {
            final existing = state.paragraphs[pIdx].text;
            final clampedPos = cursorPos.clamp(0, existing.length);
            final before = existing.substring(0, clampedPos);
            final after = existing.substring(clampedPos);
            // Add a space separator if needed
            final sep = before.isNotEmpty && !before.endsWith(' ') && !transcript.startsWith(' ') ? ' ' : '';
            final sepAfter = after.isNotEmpty && !after.startsWith(' ') && !transcript.endsWith(' ') ? ' ' : '';
            final newText = '$before$sep$transcript$sepAfter$after';

            final updated = List<Paragraph>.from(state.paragraphs);
            updated[pIdx] = updated[pIdx].copyWith(text: toOdiaDigits(newText));
            state = state.copyWith(
              paragraphs: updated,
              isProcessing: false,
              clearCursorInsert: true,
              clearEditingParagraphIndex: true,
            );
            _queueSilentBackupAudio(updated[pIdx].id, wavBytes);
          } else {
            state = state.copyWith(
              isProcessing: false,
              clearCursorInsert: true,
            );
          }
        } else {
          // New text paragraph
          final paragraph = Paragraph(
            id: DateTime.now().millisecondsSinceEpoch.toString(),
            text: transcript,
            createdAt: DateTime.now(),
          );

          final updated = List<Paragraph>.from(state.paragraphs);
          final insertIdx = state.insertAtIndex;
          int textInsertedAt;
          if (insertIdx != null && insertIdx >= 0 && insertIdx <= updated.length) {
            updated.insert(insertIdx, paragraph);
            textInsertedAt = insertIdx;
          } else {
            textInsertedAt = updated.length;
            updated.add(paragraph);
          }

          // Silent-backup audio for the always-upload pipeline. Every
          // recording's WAV is queued to the server even when the user
          // didn't long-press; if the live WS transcript path returned
          // nothing the server uses this audio to silently re-transcribe.
          // Reporter sees no UI for this.
          _queueSilentBackupAudio(paragraph.id, wavBytes);

          // If audio-save mode, upload WAV and insert audio block below text
          if (wasAudioSave && wavBytes != null && wavBytes.isNotEmpty) {
            try {
              final timestamp = DateTime.now().millisecondsSinceEpoch;
              final filename = 'voice_$timestamp.wav';
              final uploadResult = await ref.read(apiServiceProvider).uploadFile(
                wavBytes.toList(),
                filename,
              );
              final audioPath = uploadResult['url'] as String? ??
                  uploadResult['file_url'] as String? ??
                  '/uploads/$filename';

              final audioBlock = Paragraph(
                id: '${timestamp}_audio',
                mediaPath: audioPath,
                mediaType: MediaType.audio,
                mediaName: filename,
                createdAt: DateTime.now(),
              );
              updated.insert(textInsertedAt + 1, audioBlock);
            } catch (_) {
              // Audio upload failed silently — text paragraph is still there
            }
          }

          state = state.copyWith(
            paragraphs: updated,
            isProcessing: false,
            clearInsertAtIndex: true,
          );
          polishTargetIndex = textInsertedAt;
        }

        _streamingStt?.dispose();
        _streamingStt = null;

        // Save paragraphs to server IMMEDIATELY (don't wait for title/metadata)
        _scheduleAutoSave();

        // Auto-generate headline ONLY for the first paragraph (when headline
        // is still empty). After that the user owns the headline — it should
        // only change via manual edit or voice dictation.
        final body = fullBodyText;
        if (body.isNotEmpty && state.headline.isEmpty) {
          _generateTitleAndMetadata(body);
        } else if (body.isNotEmpty && state.category == null) {
          // Still infer metadata if missing, but skip headline regeneration.
          _autoInferMetadata(body).then((_) => _scheduleAutoSave()).catchError((_) {});
        }
      } on StreamingSttException catch (e) {
        _reRecordingIndex = null;
        state = state.copyWith(
          isProcessing: false,
          error: 'Streaming error: ${e.message}',
        );
        _streamingStt?.dispose();
        _streamingStt = null;
      } catch (e) {
        _reRecordingIndex = null;
        state = state.copyWith(
          isProcessing: false,
          error: 'Transcription failed: $e',
        );
        _streamingStt?.dispose();
        _streamingStt = null;
      }
    } else {
      // === START recording ===
      try {
        state = state.copyWith(
          clearError: true,
          recordingDuration: Duration.zero,
          liveTranscript: '',
          isAudioSaveMode: saveAudio,
        );

        // Check if voice enrollment exists for speaker filtering
        final enrollment = await EnrollmentStorage.load();
        final hasEnrollment = enrollment != null && enrollment.embedding.isNotEmpty;

        _streamingStt = StreamingSttService();
        _streamingStt!.authToken = ref.read(apiServiceProvider).token;
        _streamingStt!.onNoisyChanged = (isNoisy) {
          state = state.copyWith(isNoisyEnvironment: isNoisy);
        };
        if (hasEnrollment) {
          _streamingStt!.onSpeakerStatusChanged = (isVerified, similarity) {
            state = state.copyWith(isSpeakerVerified: isVerified);
          };
        }
        final transcriptStream = await _streamingStt!.start(
          saveAudio: saveAudio,
          verifySpeaker: hasEnrollment,
          enrolledEmbedding: enrollment?.embedding,
        );

        if (hasEnrollment) {
          state = state.copyWith(speakerFilterActive: true);
        }

        _transcriptSubscription = transcriptStream.listen(
          (segment) {
            // The STT service now manages full accumulation internally.
            // segment.text always contains ALL text so far (committed + partial).
            // Convert Roman numerals to Odia numerals for display.
            state = state.copyWith(liveTranscript: toOdiaDigits(segment.text));

            // Auto-paragraph: after a VAD-end with substantial text, wait 3s
            // of silence then commit as a paragraph (only for normal append).
            if (_reRecordingIndex == null &&
                state.cursorInsertParagraphIndex == null) {
              if (segment.isFinal && segment.text.trim().length >= 20) {
                _autoParagraphTimer?.cancel();
                _autoParagraphTimer = Timer(const Duration(seconds: 3), () {
                  _commitAutoParagraph();
                });
              } else if (!segment.isFinal) {
                // New speech arrived — cancel pending auto-paragraph
                _autoParagraphTimer?.cancel();
              }
            }
          },
          onError: (error) {
            if (error is StreamingSttException) {
              state = state.copyWith(error: 'Streaming: ${error.message}');
            }
          },
        );

        _startTimer();
        state = state.copyWith(isRecording: true);
      } on StreamingSttException catch (e) {
        _reRecordingIndex = null;
        state = state.copyWith(
          isRecording: false,
          error: e.message,
        );
        _streamingStt?.dispose();
        _streamingStt = null;
      } catch (e) {
        _reRecordingIndex = null;
        state = state.copyWith(
          isRecording: false,
          error: 'Microphone access denied or not available. '
              'Please allow microphone access in your browser.',
        );
        _streamingStt?.dispose();
        _streamingStt = null;
      }
    }
  }

  // ---------------------------------------------------------------------------
  // Recording timer
  // ---------------------------------------------------------------------------

  void _startTimer() {
    _recordingTimer?.cancel();
    _lastTranscriptCheck = '';
    _lastTranscriptChangeTime = DateTime.now();
    _recordingTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      final newDuration = state.recordingDuration + const Duration(seconds: 1);
      state = state.copyWith(recordingDuration: newDuration);

      // Track transcript activity for the silence safety net below.
      if (newDuration.inSeconds >= 30) {
        final currentTranscript = state.liveTranscript;
        if (currentTranscript != _lastTranscriptCheck) {
          _lastTranscriptCheck = currentTranscript;
          _lastTranscriptChangeTime = DateTime.now();
        } else {
          // Silence safety net — same 10-minute ceiling as the hard cap.
          // Kept as a separate check so a wedged WS that stops feeding
          // transcripts can't keep the mic open indefinitely; in practice
          // whichever fires first triggers the same auto-stop+save path.
          final silenceDuration =
              DateTime.now().difference(_lastTranscriptChangeTime);
          if (silenceDuration.inSeconds >= 600) {
            toggleRecording();
            return;
          }
        }
      }

      // Hard cap: 10 minutes. toggleRecording() routes to the STOP path,
      // which commits the live transcript as a paragraph and queues the
      // captured WAV for upload — nothing is lost on a timeout.
      if (newDuration.inMinutes >= 10) {
        toggleRecording();
        return;
      }
    });
  }

  void _stopTimer() {
    _recordingTimer?.cancel();
    _recordingTimer = null;
    _lastTranscriptCheck = '';
    _lastTranscriptChangeTime = DateTime.now();
    _autoParagraphTimer?.cancel();
    _autoParagraphTimer = null;
  }

  /// Commits the current live transcript as a paragraph mid-recording,
  /// resets STT accumulation, and continues recording for the next paragraph.
  void _commitAutoParagraph() {
    final transcript = toOdiaDigits(state.liveTranscript.trim());
    if (transcript.isEmpty || !state.isRecording) return;

    _pushUndo();

    final paragraph = Paragraph(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      text: transcript,
      createdAt: DateTime.now(),
    );

    final updated = List<Paragraph>.from(state.paragraphs);
    final insertIdx = state.insertAtIndex;
    int insertedAt;
    if (insertIdx != null && insertIdx >= 0 && insertIdx <= updated.length) {
      updated.insert(insertIdx, paragraph);
      insertedAt = insertIdx;
      // Advance insert position so next auto-para goes below
      state = state.copyWith(
        paragraphs: updated,
        liveTranscript: '',
        insertAtIndex: insertIdx + 1,
      );
    } else {
      insertedAt = updated.length;
      updated.add(paragraph);
      state = state.copyWith(paragraphs: updated, liveTranscript: '');
    }

    // Reset STT accumulation so next speech starts fresh
    _streamingStt?.resetAccumulation();

    _scheduleAutoSave();
  }

  /// Take all current text paragraphs (raw STT + typed input) and ask the
  /// LLM to weave them into a publishable Odia news article. The original
  /// raw text is snapshotted into [NotepadState.userNotes] so reviewers can
  /// always see what the reporter actually said before AI rewrote it.
  ///
  /// On success, paragraphs are replaced with the polished story (split on
  /// blank lines). On failure, state is left unchanged and an error toast
  /// is surfaced via [NotepadState.error].
  Future<void> generateStory() async {
    if (state.isGeneratingStory) return;
    final textParas = state.paragraphs
        .where((p) => !p.hasMedia && !p.isTable && p.text.trim().isNotEmpty)
        .toList(growable: false);
    if (textParas.isEmpty) return;

    final raw = textParas.map((p) => p.text.trim()).join('\n\n');

    // Cheap guard: if the reporter just refined and hasn't changed
    // anything since, the FAB should already be disabled — but the
    // public API of this method gets called from menus and shortcut
    // intents too, so re-check at the source. Avoids a wasted server
    // round-trip + LLM call on identical input.
    if (!state.isRefineStale) return;

    _pushUndo();
    state = state.copyWith(
      isGeneratingStory: true,
      userNotes: raw,
      clearError: true,
    );

    try {
      // Server-owned endpoint. The system prompt (Pragativadi
      // editorial standards + legal safeguards), the model choice
      // (Gemini 2.5 Flash → Sarvam fallback), and post-processing
      // (Odia digit normalization, purna-virama spacing) all live on
      // the backend so prompt edits ship as a Cloud Run deploy, not
      // an APK release. Mobile passes only the raw notes plus the
      // story id (when we have one) for cost attribution.
      final body = await _api.generateStory(
        notes: raw,
        storyId: _serverStoryId,
      );
      if (body.isEmpty) {
        state = state.copyWith(isGeneratingStory: false);
        return;
      }

      // Split on blank lines into paragraphs. Preserve any existing
      // media / table paragraphs in their original order, appended
      // after the new text body so reporters don't lose attached
      // photos when AI Refine runs.
      final newTextParas = body
          .split(RegExp(r'\n\s*\n'))
          .map((s) => s.trim())
          .where((s) => s.isNotEmpty)
          .map((s) => Paragraph(
                id: '${DateTime.now().millisecondsSinceEpoch}_${s.hashCode}',
                text: s,
                createdAt: DateTime.now(),
              ))
          .toList();

      final mediaParas = state.paragraphs
          .where((p) => p.hasMedia || p.isTable)
          .toList();

      // Snapshot the canonical text of the polished body. The FAB
      // compares state.canonicalBodyText against this snapshot via
      // isRefineStale; while they match, the button is disabled to
      // stop the reporter from hammering the LLM with no-op refines.
      // The snapshot must be derived from the SAME paragraphs we put
      // into state below, otherwise the comparison races against
      // ordering / id differences. We compute it from the new text +
      // existing media in identical order to canonicalBodyText.
      final refinedSnapshot =
          newTextParas.map((p) => p.text.trim()).join('\n\n');

      state = state.copyWith(
        paragraphs: [...newTextParas, ...mediaParas],
        isGeneratingStory: false,
        lastRefineSnapshot: refinedSnapshot,
      );
      _scheduleAutoSave();
    } catch (_) {
      state = state.copyWith(
        isGeneratingStory: false,
        error: _err('Story generation failed', 'କାହାଣୀ ତିଆରି ବିଫଳ ହେଲା'),
      );
    }
  }

  /// Add an empty paragraph (typically for direct typing). Returns the
  /// insertion index so the UI can immediately enter inline edit mode.
  int addEmptyParagraph() {
    final paragraph = Paragraph(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      text: '',
      createdAt: DateTime.now(),
    );
    final updated = List<Paragraph>.from(state.paragraphs);
    final insertIdx = state.insertAtIndex;
    int insertedAt;
    if (insertIdx != null && insertIdx >= 0 && insertIdx <= updated.length) {
      updated.insert(insertIdx, paragraph);
      insertedAt = insertIdx;
      state = state.copyWith(
        paragraphs: updated,
        insertAtIndex: insertIdx + 1,
      );
    } else {
      insertedAt = updated.length;
      updated.add(paragraph);
      state = state.copyWith(paragraphs: updated);
    }
    _scheduleAutoSave();
    return insertedAt;
  }

  /// Tell the body editor to grab keyboard focus on a specific paragraph.
  /// Used by the empty-state "Type" CTA: it adds an empty paragraph and
  /// then needs the keyboard to come up on it. The body clears the flag
  /// after requesting focus (via [clearPendingFocus]).
  void requestFocusOnParagraph(int index) {
    state = state.copyWith(pendingFocusParagraphIndex: index);
  }

  /// Called by the body editor after it actually requests focus, so the
  /// signal doesn't keep firing on every subsequent state change.
  void clearPendingFocus() {
    if (state.pendingFocusParagraphIndex == null) return;
    state = state.copyWith(clearPendingFocus: true);
  }

  // ---------------------------------------------------------------------------
  // Fire-and-forget title + metadata generation (non-blocking)
  // ---------------------------------------------------------------------------

  /// Generates title and metadata in the background without blocking recording.
  /// Each step triggers its own auto-save when it updates state.
  void _generateTitleAndMetadata(String body) {
    // Track the in-flight future so saveBeforeClose() can await it. Without
    // this, the user often taps "Keep in background" before the LLM returns,
    // saveBeforeClose flushes without the headline, the notifier disposes,
    // and the eventual headline state update is lost on the floor.
    final future = _generateTitleFromTranscript(body).then((_) {
      _scheduleAutoSave(); // save headline change
      return _autoInferMetadata(body);
    }).then((_) {
      _scheduleAutoSave(); // save metadata change
    }).catchError((_) {
      // Ignore — title/metadata are optional
    });
    _titleGenInflight = future;
    future.whenComplete(() {
      if (identical(_titleGenInflight, future)) {
        _titleGenInflight = null;
      }
    });
  }

  // ---------------------------------------------------------------------------
  // Auto-generate title from transcript using Sarvam LLM
  // ---------------------------------------------------------------------------

  Future<void> _generateTitleFromTranscript(String transcript) async {
    state = state.copyWith(isGeneratingTitle: true);

    try {
      final messages = [
        const ChatMessage(
          role: 'system',
          content:
              'You are an Odia news headline writer. Given a news transcript in Odia, '
              'generate a short, catchy news headline in Odia (max 40 characters). '
              'Use ONLY Odia script. No Roman/English letters or digits — use Odia numerals (୦-୯). '
              'Return ONLY the headline text, nothing else. No quotes, no explanation.',
        ),
        ChatMessage(
          role: 'user',
          content: transcript,
        ),
      ];

      final response = await _sarvam.chat(
        messages: messages,
        temperature: 0.3,
        maxTokens: 1024,
      );

      var generatedTitle = toOdiaDigits(response.firstMessageContent.trim());
      if (generatedTitle.length > 40) {
        generatedTitle = generatedTitle.substring(0, 40);
      }

      if (generatedTitle.isNotEmpty) {
        state = state.copyWith(
          isGeneratingTitle: false,
          headline: generatedTitle,
        );
      } else {
        state = state.copyWith(
          isGeneratingTitle: false,
          headline: _extractTitle(transcript),
        );
      }
    } catch (e) {
      state = state.copyWith(
        isGeneratingTitle: false,
        headline: _extractTitle(transcript),
      );
    }
  }

  // ---------------------------------------------------------------------------
  // Auto-infer metadata (category + location) using Sarvam LLM
  // ---------------------------------------------------------------------------

  Future<void> _autoInferMetadata(String fullText) async {
    try {
      // Constrain LLM category choice to the org's master list when set;
      // fall back to the global default list otherwise.
      final orgCats = ref.read(authProvider).reporter?.org?.categories ?? const <String>[];
      final allowed = orgCats.isNotEmpty ? orgCats : kDefaultCategoryKeys;
      final messages = [
        ChatMessage(
          role: 'system',
          content:
              'You are extracting metadata from an Odia news article. '
              'Given the text, return ONLY a JSON object with one field:\n'
              '{"category": "<one of: ${allowed.join(', ')}>"}\n'
              'You MUST pick exactly one of the listed values. '
              'Return ONLY the JSON, nothing else.',
        ),
        ChatMessage(
          role: 'user',
          content: fullText,
        ),
      ];

      final response = await _sarvam.chat(
        messages: messages,
        temperature: 0.1,
        maxTokens: 256,
      );

      final raw = response.firstMessageContent.trim();

      // Try to parse JSON from the response
      try {
        final json = jsonDecode(raw) as Map<String, dynamic>;
        final category = json['category'] as String?;
        // Only accept category values that are in the allowed list.
        // Location is set from the reporter's tagged area at story init time
        // and must not be overwritten by LLM inference.
        if (category != null && allowed.contains(category)) {
          state = state.copyWith(category: category);
        }
      } catch (_) {
        // If JSON parsing fails, silently ignore — metadata is optional
      }
    } catch (_) {
      // If LLM call fails, silently ignore — metadata is optional
    }
  }

  // ---------------------------------------------------------------------------
  // Paragraph management
  // ---------------------------------------------------------------------------

  /// Selects a paragraph for editing.
  void selectParagraph(int index) {
    if (index >= 0 && index < state.paragraphs.length) {
      state = state.copyWith(editingParagraphIndex: index);
    }
  }

  /// Clears the editing selection.
  void deselectParagraph() {
    state = state.copyWith(clearEditingParagraphIndex: true);
  }

  /// Starts re-recording a specific paragraph. On stop, replaces that
  /// paragraph's text instead of creating a new one.
  Future<void> reRecordParagraph(int index) async {
    if (index < 0 || index >= state.paragraphs.length) return;

    _reRecordingIndex = index;
    state = state.copyWith(editingParagraphIndex: index);

    // Start recording (toggleRecording handles the rest)
    if (!state.isRecording) {
      await toggleRecording();
    }
  }

  /// Moves a paragraph from [oldIndex] to [newIndex].
  void moveParagraph(int oldIndex, int newIndex) {
    if (oldIndex < 0 || oldIndex >= state.paragraphs.length) return;
    if (newIndex < 0 || newIndex >= state.paragraphs.length) return;
    if (oldIndex == newIndex) return;
    _pushUndo();

    final updated = List<Paragraph>.from(state.paragraphs);
    final item = updated.removeAt(oldIndex);
    updated.insert(newIndex, item);
    state = state.copyWith(
      paragraphs: updated,
      clearEditingParagraphIndex: true,
    );
    _scheduleAutoSave();
  }

  /// Uses AI to rephrase / improve a paragraph's text in Odia.
  /// If [instruction] is provided, the user's spoken instruction guides the rewrite.
  Future<void> improveParagraphWithAI(int index, {String? instruction}) async {
    if (index < 0 || index >= state.paragraphs.length) return;
    _pushUndo();

    final paragraph = state.paragraphs[index];
    if (paragraph.text.trim().isEmpty) return;

    state = state.copyWith(
      improvingParagraphIndex: index,
      clearEditingParagraphIndex: true,
    );

    try {
      final systemPrompt = instruction != null && instruction.trim().isNotEmpty
          ? 'You are an expert Odia news editor. The user will give you a paragraph of Odia news text '
            'and a spoken instruction about how to change it. Apply the instruction to the paragraph. '
            'Keep the facts accurate. Use ONLY Odia script — no Roman/English letters or digits. '
            'Use Odia numerals (୦-୯). Return ONLY the rewritten paragraph, nothing else.'
          : 'You are an expert Odia news editor. Given a paragraph of Odia news text, '
            'rewrite it to be clearer, more professional, and publication-ready. '
            'Keep the same meaning and facts. Use ONLY Odia script — no Roman/English letters or digits. '
            'Use Odia numerals (୦-୯). Return ONLY the improved paragraph, nothing else.';

      final userContent = instruction != null && instruction.trim().isNotEmpty
          ? 'ଅନୁଚ୍ଛେଦ:\n${paragraph.text}\n\nନିର୍ଦ୍ଦେଶ:\n$instruction'
          : paragraph.text;

      final messages = [
        ChatMessage(role: 'system', content: systemPrompt),
        ChatMessage(role: 'user', content: userContent),
      ];

      final response = await _sarvam.chat(
        messages: messages,
        temperature: 0.4,
        maxTokens: 2048,
      );

      final improved = toOdiaDigits(response.firstMessageContent.trim());
      if (improved.isNotEmpty) {
        final updated = List<Paragraph>.from(state.paragraphs);
        updated[index] = updated[index].copyWith(text: improved);
        state = state.copyWith(
          paragraphs: updated,
          clearImprovingParagraphIndex: true,
        );
        _scheduleAutoSave();
      } else {
        state = state.copyWith(clearImprovingParagraphIndex: true);
      }
    } catch (e) {
      state = state.copyWith(
        clearImprovingParagraphIndex: true,
        error: _err('AI polish failed: $e', 'AI ସୁଧାର ବିଫଳ: $e'),
      );
    }
  }

  /// Auto-polishes a freshly transcribed paragraph using LLM.
  /// Fixes: Roman→Odia script, Arabic→Odia numerals, duplicate phrases,
  /// punctuation, misplaced purna virama, grammar — without changing meaning.
  Future<void> polishTranscriptWithAI(int index) async {
    if (index < 0 || index >= state.paragraphs.length) return;
    final paragraph = state.paragraphs[index];
    if (paragraph.text.trim().length < 5) return;

    // Pin to the paragraph's ID — by the time the LLM responds the user may
    // have reordered or inserted around it, so trusting the original index
    // would clobber the wrong paragraph.
    final pid = paragraph.id;

    state = state.copyWith(
      polishingParagraphIds: {...state.polishingParagraphIds, pid},
    );

    try {
      const systemPrompt =
          'You are an Odia text polisher for raw speech-to-text output. Clean up the text:\n'
          '1. Convert any Roman/English letters to equivalent Odia script\n'
          '2. Convert Arabic numerals (0-9) to Odia numerals (୦-୯)\n'
          '3. Remove duplicate words/phrases caused by STT stuttering\n'
          '4. Add proper Odia punctuation (commas, purna virama ।)\n'
          '5. Remove misplaced or excessive purna virama (।)\n'
          '6. Fix grammatical errors while keeping natural spoken tone\n'
          '7. Keep the SAME meaning and facts — do NOT add, remove, or embellish content\n'
          '8. PROPER NOUNS: Preserve names of people, places, organizations, '
          'rivers, temples, parties, schemes etc. EXACTLY as a careful Odia '
          'reporter would spell them. The STT often mangles proper nouns into '
          'phonetic approximations or non-words — when you see a token that is '
          'clearly a proper noun (person/place/org), correct the spelling to '
          'the canonical Odia form (e.g. ମୋଦୀ, ନବୀନ ପଟ୍ଟନାୟକ, ଭୁବନେଶ୍ୱର, '
          'କଟକ, ବିଜେଡି, ବିଜେପି). Never invent new names — if unsure, leave the '
          'token unchanged. Do NOT translate Indian names into other languages.\n'
          'Return ONLY the cleaned text. No explanations, no quotes.';

      final messages = [
        const ChatMessage(role: 'system', content: systemPrompt),
        ChatMessage(role: 'user', content: paragraph.text),
      ];

      final response = await _sarvam.chat(
        messages: messages,
        temperature: 0.2,
        maxTokens: 2048,
      );

      var polished = toOdiaDigits(response.firstMessageContent.trim());
      // Ensure space before Odia purnachheda (।) for readability
      polished = polished.replaceAll(RegExp(r'(?<!\s)।'), ' ।');
      // Re-locate the paragraph by ID — its index may have shifted.
      final currentIdx = state.paragraphs.indexWhere((p) => p.id == pid);
      if (polished.isNotEmpty && currentIdx >= 0) {
        final updated = List<Paragraph>.from(state.paragraphs);
        updated[currentIdx] = updated[currentIdx].copyWith(text: polished);
        state = state.copyWith(
          paragraphs: updated,
          polishingParagraphIds: {...state.polishingParagraphIds}..remove(pid),
        );
        _scheduleAutoSave();
      } else {
        state = state.copyWith(
          polishingParagraphIds: {...state.polishingParagraphIds}..remove(pid),
        );
      }
    } catch (_) {
      // Polish failed silently — keep raw text
      state = state.copyWith(
        polishingParagraphIds: {...state.polishingParagraphIds}..remove(pid),
      );
    }
  }

  /// Uses AI to apply a spoken instruction to a selected portion of text.
  /// [index] — paragraph index
  /// [fullParagraphText] — the full paragraph text (with selection in context)
  /// [selectedText] — the selected portion the user wants to change
  /// [selectionStart] / [selectionEnd] — character offsets within the paragraph
  /// [instruction] — the user's spoken instruction (e.g. "make this formal")
  Future<void> instructEditWithAI({
    required int index,
    required String fullParagraphText,
    required String selectedText,
    required int selectionStart,
    required int selectionEnd,
    required String instruction,
  }) async {
    if (index < 0 || index >= state.paragraphs.length) return;
    if (selectedText.trim().isEmpty || instruction.trim().isEmpty) return;
    _pushUndo();

    state = state.copyWith(
      improvingParagraphIndex: index,
      improvingSelStart: selectionStart,
      improvingSelEnd: selectionEnd,
      clearEditingParagraphIndex: true,
    );

    try {
      // Send ONLY the selected text + instruction. The LLM rewrites just that
      // portion and we splice the result back into the paragraph.
      final messages = [
        const ChatMessage(
          role: 'system',
          content:
              'You are an expert Odia text editor. '
              'The user gives you a piece of Odia text and an instruction. '
              'Rewrite the given text according to the instruction. '
              'Return ONLY the rewritten text — nothing else. No explanations, '
              'no quotes, no labels, no prefixes. Just the rewritten Odia text. '
              'Use ONLY Odia script — no Roman/English letters or digits. '
              'Use Odia numerals (୦-୯).',
        ),
        ChatMessage(
          role: 'user',
          content: '$selectedText\n\nନିର୍ଦ୍ଦେଶ: $instruction',
        ),
      ];

      final response = await _sarvam.chat(
        messages: messages,
        temperature: 0.4,
        maxTokens: 2048,
      );

      final replacement = toOdiaDigits(response.firstMessageContent.trim());
      if (replacement.isNotEmpty) {
        // Splice the replacement back into the full paragraph
        final before = fullParagraphText.substring(0, selectionStart);
        final after = fullParagraphText.substring(selectionEnd);
        final newText = '$before$replacement$after';

        final updated = List<Paragraph>.from(state.paragraphs);
        updated[index] = updated[index].copyWith(text: newText);
        state = state.copyWith(
          paragraphs: updated,
          clearImprovingParagraphIndex: true,
        );
        _scheduleAutoSave();
      } else {
        state = state.copyWith(clearImprovingParagraphIndex: true);
      }
    } catch (e) {
      state = state.copyWith(
        clearImprovingParagraphIndex: true,
        error: _err('AI instruction failed: $e', 'AI ନିର୍ଦ୍ଦେଶ ବିଫଳ: $e'),
      );
    }
  }

  /// Removes a paragraph from the list and regenerates the headline.
  Future<void> deleteParagraph(int index) async {
    if (index < 0 || index >= state.paragraphs.length) return;
    _pushUndo();

    final updated = List<Paragraph>.from(state.paragraphs)..removeAt(index);
    state = state.copyWith(
      paragraphs: updated,
      clearEditingParagraphIndex: true,
    );

    // Only clear headline if all paragraphs were deleted.
    // Otherwise keep the user's existing headline intact.
    if (fullBodyText.isEmpty) {
      state = state.copyWith(headline: '');
    }

    _scheduleAutoSave();
  }

  /// Updates a paragraph's text directly (e.g., inline keyboard editing).
  void updateParagraphText(int index, String text) {
    if (index < 0 || index >= state.paragraphs.length) return;
    final sanitized = toOdiaDigits(text);
    // Only push undo if text actually changed
    if (state.paragraphs[index].text != sanitized) {
      _pushUndo();
    }

    final updated = List<Paragraph>.from(state.paragraphs);
    updated[index] = updated[index].copyWith(text: sanitized);
    state = state.copyWith(paragraphs: updated);

    _scheduleAutoSave();
  }

  /// Replaces a contiguous run of text paragraphs with the given texts.
  /// Used by the simplified body editor: the user types into one TextField
  /// spanning multiple text paragraphs, and on debounced commit we split by
  /// '\n\n' and persist. Existing paragraph IDs are reused where possible
  /// so audio/transcription metadata survives.
  ///
  /// `firstIdx`..`lastIdxInclusive` must reference text paragraphs only
  /// (no media/table). Empty entries in [newTexts] are dropped.
  void replaceTextRun(int firstIdx, int lastIdxInclusive, List<String> newTexts) {
    if (firstIdx < 0 ||
        lastIdxInclusive >= state.paragraphs.length ||
        firstIdx > lastIdxInclusive) {
      return;
    }
    for (int i = firstIdx; i <= lastIdxInclusive; i++) {
      final p = state.paragraphs[i];
      if (p.hasMedia || p.isTable) return;
    }

    final sanitized = newTexts
        .map((t) => toOdiaDigits(t).trim())
        .where((s) => s.isNotEmpty)
        .toList();

    final existing = state.paragraphs.sublist(firstIdx, lastIdxInclusive + 1);
    final oldTexts = existing.map((p) => p.text).toList();
    if (sanitized.length == oldTexts.length) {
      bool same = true;
      for (int i = 0; i < sanitized.length; i++) {
        if (sanitized[i] != oldTexts[i]) {
          same = false;
          break;
        }
      }
      if (same) return;
    }

    _pushUndo();

    final newParagraphs = <Paragraph>[];
    for (int i = 0; i < sanitized.length; i++) {
      if (i < existing.length) {
        newParagraphs.add(existing[i].copyWith(text: sanitized[i]));
      } else {
        newParagraphs.add(Paragraph(
          id: '${DateTime.now().millisecondsSinceEpoch}-$i',
          text: sanitized[i],
          createdAt: DateTime.now(),
        ));
      }
    }

    final updated = List<Paragraph>.from(state.paragraphs)
      ..replaceRange(firstIdx, lastIdxInclusive + 1, newParagraphs);
    state = state.copyWith(paragraphs: updated);

    if (fullBodyText.isEmpty) {
      state = state.copyWith(headline: '');
    }

    _scheduleAutoSave();
  }

  /// Updates the table data for a table paragraph at [index].
  void updateParagraphTable(int index, List<List<String>> tableData) {
    if (index < 0 || index >= state.paragraphs.length) return;
    _pushUndo();
    final updated = List<Paragraph>.from(state.paragraphs);
    updated[index] = updated[index].copyWith(tableData: tableData);
    state = state.copyWith(paragraphs: updated);
    _scheduleAutoSave();
  }

  /// Creates a media paragraph and inserts it at the given position.
  void insertMedia(int atIndex, String path, MediaType type, String name) {
    final media = Paragraph(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      mediaPath: path,
      mediaType: type,
      mediaName: name,
      createdAt: DateTime.now(),
    );

    final updated = List<Paragraph>.from(state.paragraphs);
    final clampedIndex = atIndex.clamp(0, updated.length);
    updated.insert(clampedIndex, media);
    state = state.copyWith(paragraphs: updated);

    _scheduleAutoSave();
  }

  /// Backward-compatible alias.
  void insertPhoto(int atIndex, String path) =>
      insertMedia(atIndex, path, MediaType.photo, 'photo');

  /// Removes a media paragraph at the given index.
  void removeMedia(int index) {
    if (index < 0 || index >= state.paragraphs.length) return;
    if (!state.paragraphs[index].hasMedia) return;

    final updated = List<Paragraph>.from(state.paragraphs)..removeAt(index);
    state = state.copyWith(paragraphs: updated);

    _scheduleAutoSave();
  }

  /// Backward-compatible alias.
  void removePhoto(int index) => removeMedia(index);

  /// Run OCR on a photo paragraph at [index]. Inserts extracted text as a new
  /// paragraph right after the image.
  Future<void> runOcrOnParagraph(int index) async {
    if (index < 0 || index >= state.paragraphs.length) return;
    final para = state.paragraphs[index];
    if (para.mediaType != MediaType.photo) return;
    final mediaPath = para.mediaPath ?? '';

    state = state.copyWith(isOcrProcessing: true, ocrProgress: 0.1);
    try {
      // Resolve image bytes from data URL or server URL
      Uint8List? imageBytes;
      if (mediaPath.startsWith('data:')) {
        final commaIdx = mediaPath.indexOf(',');
        if (commaIdx > 0) {
          imageBytes = base64Decode(mediaPath.substring(commaIdx + 1));
        }
      } else if (mediaPath.startsWith('http') || mediaPath.startsWith('/uploads/')) {
        // Download from server
        final url = mediaPath.startsWith('http')
            ? mediaPath
            : '${_api.baseUrl}$mediaPath';
        final response = await _api.downloadBytes(url);
        imageBytes = response;
      }

      if (imageBytes == null) {
        state = state.copyWith(isOcrProcessing: false);
        return;
      }

      state = state.copyWith(ocrProgress: 0.3);
      final ocrResult = await _sarvam.ocrWithSegments(
        imageBytes: imageBytes,
        fileName: para.mediaName ?? 'photo.jpg',
      );

      if (ocrResult.segments.isNotEmpty) {
        final updated = List<Paragraph>.from(state.paragraphs);
        var insertIdx = index + 1;
        for (final seg in ocrResult.segments) {
          final segText = seg.text.trim();
          if (seg.type == 'table' && seg.tableData != null && seg.tableData!.isNotEmpty) {
            updated.insert(
              insertIdx.clamp(0, updated.length),
              Paragraph(
                id: DateTime.now().microsecondsSinceEpoch.toString(),
                tableData: seg.tableData,
                createdAt: DateTime.now(),
              ),
            );
            insertIdx++;
          } else if (segText.isNotEmpty) {
            updated.insert(
              insertIdx.clamp(0, updated.length),
              Paragraph(
                id: DateTime.now().microsecondsSinceEpoch.toString(),
                text: segText,
                createdAt: DateTime.now(),
              ),
            );
            insertIdx++;
          }
        }
        state = state.copyWith(paragraphs: updated);
        _scheduleAutoSave();
      } else if (ocrResult.text.isNotEmpty) {
        // Fallback: no segments, use plain text
        final updated = List<Paragraph>.from(state.paragraphs);
        updated.insert(
          (index + 1).clamp(0, updated.length),
          Paragraph(
            id: DateTime.now().microsecondsSinceEpoch.toString(),
            text: ocrResult.text.trim(),
            createdAt: DateTime.now(),
          ),
        );
        state = state.copyWith(paragraphs: updated);
        _scheduleAutoSave();
      }
    } catch (_) {
      // OCR failed silently
    }
    state = state.copyWith(isOcrProcessing: false);
  }

  /// Picks a file and uploads it to the server, then attaches as media.
  Future<void> pickAndAttachMedia(MediaType type, {bool fromCamera = false}) async {
    state = state.copyWith(isOcrProcessing: true, ocrProgress: 0.0);
    try {
      final result = await _ocrService.pickFile(type, fromCamera: fromCamera);
      if (result == null) {
        state = state.copyWith(isOcrProcessing: false);
        return;
      }

      // Extract raw bytes for upload + OCR
      Uint8List? imageBytes;
      final dataUrl = result.dataUrl;
      final commaIdx = dataUrl.indexOf(',');
      if (commaIdx > 0) {
        imageBytes = base64Decode(dataUrl.substring(commaIdx + 1));
      }

      // Upload to server — retry once on failure before giving up
      String? mediaPath;
      if (imageBytes != null) {
        for (int attempt = 0; attempt < 2 && mediaPath == null; attempt++) {
          try {
            final uploaded = await _api.uploadFile(imageBytes, result.fileName);
            mediaPath = uploaded['url'] as String;
          } catch (_) {
            if (attempt == 0) {
              await Future.delayed(const Duration(seconds: 1));
            }
          }
        }
      }

      // If upload still failed, skip — don't store base64 in paragraphs
      if (mediaPath == null) {
        state = state.copyWith(
          isOcrProcessing: false,
          error: _err(
            'File upload failed. Please try again.',
            '\u0B2B\u0B3E\u0B07\u0B32 \u0B05\u0B2A\u0B32\u0B4B\u0B21 \u0B2C\u0B3F\u0B2B\u0B33 \u0B39\u0B47\u0B32\u0B3E\u0964 \u0B2A\u0B41\u0B23\u0B3F \u0B1A\u0B47\u0B37\u0B4D\u0B1F\u0B3E \u0B15\u0B30\u0B28\u0B4D\u0B24\u0B41\u0964',
          ),
          // File upload failed. Please try again.
        );
        return;
      }

      final insertIdx = state.insertAtIndex ?? state.paragraphs.length;
      // Use the resolved type (e.g., audio files picked from document picker)
      final actualType = result.resolvedType;
      insertMedia(insertIdx, mediaPath, actualType, result.fileName);

      state = state.copyWith(
        clearInsertAtIndex: true,
        isOcrProcessing: false,
      );
    } catch (e) {
      state = state.copyWith(
        isOcrProcessing: false,
        error: _err(
          'File attach failed',
          '\u0B2B\u0B3E\u0B07\u0B32 \u0B2F\u0B4B\u0B21\u0B3C\u0B3F\u0B2C\u0B3E \u0B2C\u0B3F\u0B2B\u0B33 \u0B39\u0B47\u0B32\u0B3E',
        ),
        // File attachment failed
      );
    }
  }

  /// Sets where the next recording will be inserted.
  void setInsertPosition(int index) {
    state = state.copyWith(insertAtIndex: index);
  }

  /// Sets cursor insertion point within an existing paragraph.
  void setCursorInsert(int paragraphIndex, int cursorPosition) {
    state = state.copyWith(
      cursorInsertParagraphIndex: paragraphIndex,
      cursorInsertPosition: cursorPosition,
    );
  }

  /// Manually edit the headline (max 40 chars).
  void setHeadline(String value) {
    var h = toOdiaDigits(value);
    if (h.length > 40) h = h.substring(0, 40);
    state = state.copyWith(headline: h);

    _scheduleAutoSave();
  }

  /// Manually set the category (overrides auto-inference).
  void setCategory(String? category) {
    state = state.copyWith(
      category: category,
      clearCategory: category == null,
    );
    _scheduleAutoSave();
  }

  /// Manually set the location.
  void setLocation(String? location) {
    state = state.copyWith(
      location: location,
      clearLocation: location == null,
    );
    _scheduleAutoSave();
  }

  // ---------------------------------------------------------------------------
  // Headline voice dictation
  // ---------------------------------------------------------------------------

  StreamingSttService? _headlineStt;
  StreamSubscription<SttSegment>? _headlineSttSub;

  /// Whether the user is currently voice-dictating the headline.
  bool get isDictatingHeadline => _headlineStt != null;

  /// Start voice dictation for the headline.
  Future<void> startHeadlineDictation() async {
    _headlineStt = StreamingSttService();
    _headlineStt!.authToken = ref.read(apiServiceProvider).token;
    final stream = await _headlineStt!.start();
    _headlineSttSub = stream.listen(
      (segment) {
        state = state.copyWith(headline: toOdiaDigits(segment.text));
      },
      onError: (_) {},
    );
  }

  /// Stop voice dictation for the headline and return the final text.
  Future<String> stopHeadlineDictation() async {
    final headline = state.headline;
    _headlineSttSub?.cancel();
    _headlineSttSub = null;
    await _headlineStt?.stop();
    _headlineStt?.dispose();
    _headlineStt = null;
    _scheduleAutoSave();
    return headline;
  }

  // ---------------------------------------------------------------------------
  // Speech edit
  // ---------------------------------------------------------------------------

  /// Start a short speech-edit recording. The live text is exposed via
  /// state.speechEditTranscript so the UI can show it.
  Future<void> startSpeechEdit() async {
    _speechEditStt = StreamingSttService();
    _speechEditStt!.authToken = ref.read(apiServiceProvider).token;
    final stream = await _speechEditStt!.start();
    state = state.copyWith(isSpeechEditing: true, speechEditTranscript: '');
    _speechEditSub = stream.listen(
      (segment) {
        state = state.copyWith(speechEditTranscript: toOdiaDigits(segment.text));
      },
      onError: (_) {},
    );
  }

  /// Stop speech-edit and return the transcript.
  Future<String> stopSpeechEdit() async {
    final transcript = state.speechEditTranscript;
    _speechEditSub?.cancel();
    _speechEditSub = null;
    await _speechEditStt?.stop();
    _speechEditStt?.dispose();
    _speechEditStt = null;
    state = state.copyWith(isSpeechEditing: false, speechEditTranscript: '');
    return transcript;
  }

  // ---------------------------------------------------------------------------
  // Error & reset
  // ---------------------------------------------------------------------------

  void clearError() => state = state.copyWith(clearError: true);

  void reset() {
    _stopTimer();
    _autoSaveTimer?.cancel();
    _autoSaveTimer = null;
    _transcriptSubscription?.cancel();
    _transcriptSubscription = null;
    _streamingStt?.dispose();
    _streamingStt = null;
    _reRecordingIndex = null;
    _lastTranscriptCheck = '';
    _lastTranscriptChangeTime = DateTime.now();
    _serverStoryId = null;
    _localId = null;
    _storyStatus = 'draft';
    // Clean up speech-edit resources
    _speechEditSub?.cancel();
    _speechEditSub = null;
    _speechEditStt?.dispose();
    _speechEditStt = null;
    // Clean up headline dictation resources
    _headlineSttSub?.cancel();
    _headlineSttSub = null;
    _headlineStt?.dispose();
    _headlineStt = null;
    state = const NotepadState();
  }

  // ---------------------------------------------------------------------------
  // Private helpers
  // ---------------------------------------------------------------------------

  /// Extracts a short title from the beginning of a transcript.
  String _extractTitle(String transcript) {
    if (transcript.isEmpty) return '';

    // Look for Odia danda (purna viram) or period as sentence boundary.
    final sentenceEnd = RegExp(r'[।.]');
    final match = sentenceEnd.firstMatch(transcript);

    if (match != null && match.start < 60) {
      return transcript.substring(0, match.start).trim();
    }

    if (transcript.length <= 60) return transcript.trim();
    return '${transcript.substring(0, 60).trim()}...';
  }
}

// =============================================================================
// Provider
// =============================================================================

final notepadProvider =
    NotifierProvider<NotepadNotifier, NotepadState>(NotepadNotifier.new);

/// Backward-compatible alias during migration.
final createNewsProvider = notepadProvider;
