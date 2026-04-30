import 'dart:convert';
import 'dart:math' as math;

import 'package:audioplayers/audioplayers.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:lucide_icons/lucide_icons.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

import '../../../core/services/api_config.dart';
import '../../../core/services/mic_permission_ui.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_gradients.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/theme/theme_extensions.dart';
import '../../../core/l10n/app_strings.dart';
import '../../../core/providers/connectivity_provider.dart';
import '../../../core/providers/phone_call_provider.dart';
import '../../../core/widgets/status_banner.dart';
import '../providers/create_news_provider.dart';
import '../../../core/services/file_picker_service.dart';
import '../../home/providers/stories_provider.dart';
import '../../auth/providers/auth_provider.dart';

// =============================================================================
// NotepadScreen — single-screen voice notepad that replaces the old wizard
// =============================================================================

class NotepadScreen extends ConsumerStatefulWidget {
  final String? storyId;

  const NotepadScreen({super.key, this.storyId});

  @override
  ConsumerState<NotepadScreen> createState() => _NotepadScreenState();
}

class _NotepadScreenState extends ConsumerState<NotepadScreen>
    with TickerProviderStateMixin, WidgetsBindingObserver {
  AppStrings get s => AppStrings.of(ref);

  /// Gate any "start recording" action behind microphone permission. Returns
  /// true if recording can proceed, false otherwise (rationale or Settings
  /// dialog will already have been shown). Skip when [isRecording] is already
  /// true — that path is a stop, not a start.
  Future<bool> _gateMic({required bool isStart}) async {
    if (!isStart) return true;
    return ensureMicPermission(context, ref);
  }

  // Controllers for inline text editing.
  TextEditingController? _inlineEditController;
  int? _inlineEditingIndex;
  bool _hasTextSelection = false;

  // New simple-body editor state. The focused paragraph + cursor is what
  // the bottom bar's Record button targets when inserting transcripts at
  // the user's caret. Updated by _SimpleNotepadBody via onFocusedCursorChanged.
  int? _focusedParagraphIndex;
  int? _focusedCursorOffset;

  // Selection from SelectableText (single-tap selected mode)
  int? _selectableSelectionParaIndex;
  TextSelection? _selectableSelection;

  // Guard to prevent double-save when closing
  bool _isClosing = false;

  // AI instruction recording: which paragraph is being instructed
  int? _instructingParagraphIndex;

  // Captured text selection when starting AI instruction
  String? _instructSelectedText;
  int? _instructSelectionStart;
  int? _instructSelectionEnd;
  String? _instructFullText;

  // Controller for headline editing
  final _headlineController = TextEditingController();
  bool _isEditingHeadline = false;
  bool _isDictatingHeadline = false;

  // Animation controllers
  late AnimationController _waveformController;
  late AnimationController _typingDotsController;
  late AnimationController _pulseController;
  late AnimationController _polishGlowController;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);

    _waveformController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    );

    _typingDotsController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    );

    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);

    _polishGlowController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2500),
    )..repeat();

    // Initialize story. Three branches:
    //   - "local-<localId>" → hydrate from Hive (local-first draft)
    //   - "<serverUuid>"    → load existing server-side story
    //   - null              → brand-new local draft (no server call)
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final notifier = ref.read(notepadProvider.notifier);
      final id = widget.storyId;
      if (id == null) {
        notifier.initWithNewStory();
      } else if (id.startsWith('local-')) {
        notifier.initWithLocalDraft(id.substring('local-'.length));
      } else {
        notifier.initWithExistingStory(id);
      }
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _inlineEditController?.removeListener(_onSelectionChanged);
    _inlineEditController?.dispose();
    _headlineController.dispose();
    _waveformController.dispose();
    _typingDotsController.dispose();
    _pulseController.dispose();
    _polishGlowController.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Stop any in-flight recording when the app is backgrounded. The OS may
    // suspend our mic stream anyway; doing it explicitly keeps the notifier
    // state consistent (isRecording flips to false, transcript is committed)
    // and avoids the iOS red recording bar lingering after the user switches
    // away.
    if (state == AppLifecycleState.resumed) return;
    final notepad = ref.read(notepadProvider);
    if (notepad.isRecording) {
      ref.read(notepadProvider.notifier).toggleRecording();
    }
  }

  // --- Close-talking hint (shown once on first recording) ---
  static const _kCloseTalkHintShown = 'close_talk_hint_shown';

  Future<void> _maybeShowCloseTalkHint() async {
    final prefs = await SharedPreferences.getInstance();
    if (prefs.getBool(_kCloseTalkHintShown) == true) return;
    await prefs.setBool(_kCloseTalkHintShown, true);
    if (!mounted) return;
    final s = AppStrings.of(ref);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(LucideIcons.mic, color: Colors.white, size: 18),
            const SizedBox(width: 8),
            Expanded(child: Text(s.closeTalkHint)),
          ],
        ),
        duration: const Duration(seconds: 4),
        behavior: SnackBarBehavior.floating,
        backgroundColor: AppColors.vrCoral,
      ),
    );
  }

  void _startInlineEdit(int index, String text) {
    _inlineEditController?.removeListener(_onSelectionChanged);
    _inlineEditController?.dispose();
    _inlineEditController = TextEditingController(text: text);
    _inlineEditController!.addListener(_onSelectionChanged);
    setState(() {
      _inlineEditingIndex = index;
      _hasTextSelection = false;
    });
  }

  void _onSelectionChanged() {
    if (_inlineEditController == null) return;
    final sel = _inlineEditController!.selection;
    final hasSelection = sel.isValid && !sel.isCollapsed && sel.start >= 0;
    if (hasSelection != _hasTextSelection) {
      setState(() => _hasTextSelection = hasSelection);
    }
  }

  void _commitInlineEdit(int index, {bool keepSelected = false}) {
    if (_inlineEditController != null) {
      final newText = _inlineEditController!.text.trim();
      if (newText.isNotEmpty) {
        ref.read(notepadProvider.notifier).updateParagraphText(index, newText);
      }
    }
    setState(() {
      _inlineEditingIndex = null;
      _hasTextSelection = false;
    });
    _inlineEditController?.removeListener(_onSelectionChanged);
    _inlineEditController?.dispose();
    _inlineEditController = null;
    if (!keepSelected) {
      ref.read(notepadProvider.notifier).deselectParagraph();
    }
  }

  /// Start recording a spoken instruction for AI rewrite.
  /// Captures the current text selection so we can rewrite only that part.
  Future<void> _startAIInstruction(int paragraphIndex) async {
    // Capture text selection BEFORE committing/dismissing the TextField
    String? selectedText;
    int? selStart;
    int? selEnd;
    String? fullText;

    if (_inlineEditController != null) {
      // Selection from inline edit mode (TextField)
      final sel = _inlineEditController!.selection;
      fullText = _inlineEditController!.text;
      if (sel.isValid && !sel.isCollapsed && sel.start >= 0) {
        selStart = sel.start;
        selEnd = sel.end;
        selectedText = fullText.substring(selStart, selEnd);
      }
    } else if (_selectableSelection != null &&
        _selectableSelectionParaIndex == paragraphIndex) {
      // Selection from single-tap selected mode (SelectableText)
      final sel = _selectableSelection!;
      final state = ref.read(notepadProvider);
      if (paragraphIndex < state.paragraphs.length) {
        fullText = state.paragraphs[paragraphIndex].text;
        if (sel.isValid && !sel.isCollapsed && sel.start >= 0 &&
            sel.end <= fullText.length) {
          selStart = sel.start;
          selEnd = sel.end;
          selectedText = fullText.substring(selStart, selEnd);
        }
      }
    }

    // Save any pending inline edit but keep paragraph selected
    if (_inlineEditController != null && _inlineEditingIndex != null) {
      _commitInlineEdit(_inlineEditingIndex!, keepSelected: true);
    }

    setState(() {
      _instructingParagraphIndex = paragraphIndex;
      _instructSelectedText = selectedText;
      _instructSelectionStart = selStart;
      _instructSelectionEnd = selEnd;
      _instructFullText = fullText;
    });
    if (!await _gateMic(isStart: true)) return;
    await ref.read(notepadProvider.notifier).startSpeechEdit();
  }

  /// Stop recording and apply the spoken instruction via AI.
  /// If text was selected, rewrites only the selection; otherwise the whole paragraph.
  Future<void> _stopAIInstruction() async {
    final notifier = ref.read(notepadProvider.notifier);
    final instruction = await notifier.stopSpeechEdit();
    final idx = _instructingParagraphIndex;
    final selectedText = _instructSelectedText;
    final selStart = _instructSelectionStart;
    final selEnd = _instructSelectionEnd;
    final fullText = _instructFullText;

    setState(() {
      _instructingParagraphIndex = null;
      _instructSelectedText = null;
      _instructSelectionStart = null;
      _instructSelectionEnd = null;
      _instructFullText = null;
    });

    if (idx == null) return;
    if (instruction.isEmpty) {
      // STT didn't capture any instruction — notify user
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(s.instructionNotHeard),
            backgroundColor: AppColors.vrCoral,
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          ),
        );
      }
      return;
    }

    // If user had text selected, rewrite only that portion
    if (selectedText != null &&
        selectedText.isNotEmpty &&
        selStart != null &&
        selEnd != null &&
        fullText != null) {
      await notifier.instructEditWithAI(
        index: idx,
        fullParagraphText: fullText,
        selectedText: selectedText,
        selectionStart: selStart,
        selectionEnd: selEnd,
        instruction: instruction,
      );
    } else {
      // No selection — rewrite the whole paragraph
      await notifier.improveParagraphWithAI(idx, instruction: instruction);
    }
  }

  /// Cancel AI instruction without applying
  Future<void> _cancelAIInstruction() async {
    await ref.read(notepadProvider.notifier).stopSpeechEdit();
    setState(() {
      _instructingParagraphIndex = null;
      _instructSelectedText = null;
      _instructSelectionStart = null;
      _instructSelectionEnd = null;
      _instructFullText = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(notepadProvider);
    final notifier = ref.read(notepadProvider.notifier);
    final isConnected = ref.watch(connectivityProvider);
    final isInCall = ref.watch(phoneCallProvider);
    final isReadOnly = notifier.storyStatus != 'draft';

    // Pop a snackbar whenever a fresh error appears. The inline _ErrorBanner
    // below stays as the persistent surface (user can re-read / dismiss it),
    // but the snackbar gives an immediate visual cue — without it a user who
    // tapped Generate and looked away would never notice the failure.
    ref.listen<String?>(
      notepadProvider.select((s) => s.error),
      (prev, next) {
        if (next == null || next == prev || !mounted) return;
        ScaffoldMessenger.of(context)
          ..hideCurrentSnackBar()
          ..showSnackBar(
            SnackBar(
              content: Text(next),
              behavior: SnackBarBehavior.floating,
              backgroundColor: AppColors.error,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              duration: const Duration(seconds: 4),
            ),
          );
      },
    );

    // Hold the screen awake while recording. Reporters often dictate long
    // stories without touching the screen; without this the OS sleeps mid-
    // recording, killing the mic stream and the WS connection.
    ref.listen<bool>(
      notepadProvider.select((s) => s.isRecording),
      (prev, next) {
        if (next == true) {
          WakelockPlus.enable();
        } else {
          WakelockPlus.disable();
        }
      },
    );

    // Auto-stop recording when the OS reports an active phone call. The
    // mic stream is owned by the call once it connects, so anything we
    // record after that point is silent garbage. Stop, commit whatever
    // partial transcript we have, and tell the user.
    //
    // Note: phoneCallProvider only polls Android telephony state. On iOS
    // we'd need to wire AVAudioSession interruption notifications via a
    // method channel — tracked as a follow-up.
    ref.listen<bool>(
      phoneCallProvider,
      (prev, next) {
        if (next == true && ref.read(notepadProvider).isRecording) {
          ref.read(notepadProvider.notifier).toggleRecording();
          if (mounted) {
            ScaffoldMessenger.of(context)
              ..hideCurrentSnackBar()
              ..showSnackBar(
                SnackBar(
                  content: Text(s.recordingStoppedCall),
                  behavior: SnackBarBehavior.floating,
                  backgroundColor: AppColors.vrCoral,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  duration: const Duration(seconds: 4),
                ),
              );
          }
        }
      },
    );

    // Manage animation state based on recording
    if (state.isRecording) {
      if (!_waveformController.isAnimating) {
        _waveformController.repeat();
      }
      if (!_typingDotsController.isAnimating) {
        _typingDotsController.repeat();
      }
    } else {
      if (_waveformController.isAnimating) {
        _waveformController.stop();
      }
      if (_typingDotsController.isAnimating) {
        _typingDotsController.stop();
      }
    }

    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) async {
        if (didPop || _isClosing) return;
        // No confirm dialog. Back press just pops — any in-flight work (live
        // STT, AI polish, title gen, WAV upload) keeps running on the
        // notifier in the background until it completes. We do NOT call
        // reset() here, because reset() tears down the recording timer, the
        // STT subscription and the streaming WS, which would silently drop
        // exactly the work the user expects to finish.
        //
        // saveBeforeClose() is safe to await: it only awaits in-flight title
        // generation and pushes the current snapshot to the server. It does
        // not touch the recording pipeline. Headline dictation is the one
        // thing we explicitly stop, since it's a UI-bound text field on this
        // screen and there's nothing meaningful to keep running for it.
        _isClosing = true;
        if (_isDictatingHeadline) {
          await notifier.stopHeadlineDictation();
          if (mounted) setState(() => _isDictatingHeadline = false);
        }
        await notifier.saveBeforeClose();
        ref.read(storiesProvider.notifier).fetchStories();
        if (context.mounted) {
          // Prefer go_router's pop (it knows about its own match stack).
          // If nothing to pop back to (e.g. notepad is the only page on the
          // stack because the user deep-linked or refreshed), fall back to
          // /home — calling Navigator.pop on an empty stack crashes with
          // "popped the last page off of the stack".
          if (Navigator.of(context).canPop()) {
            context.pop();
          } else {
            context.go('/home');
          }
        }
      },
      child: Stack(
      children: [
        Scaffold(
          backgroundColor: AppColors.vrWarmBg,
          body: Column(
            children: [
              // === Status banners ===
              if (!isConnected) StatusBanner.noInternet(),
              if (isInCall) StatusBanner.micBusy(),
              // === Zone 1: Header ===
              _NotepadHeader(
                state: state,
                storyStatus: notifier.storyStatus,
                headlineController: _headlineController,
                isEditingHeadline: _isEditingHeadline,
                isDictatingHeadline: _isDictatingHeadline,
                canUndo: notifier.canUndo,
                canRedo: notifier.canRedo,
                onUndo: () => notifier.undo(),
                onRedo: () => notifier.redo(),
                onBack: () {
                  // Delegate to PopScope (save, pop, reset)
                  Navigator.of(context).maybePop();
                },
                onEditHeadline: () {
                  _headlineController.text = state.headline;
                  setState(() => _isEditingHeadline = true);
                },
                onSubmitHeadline: (value) {
                  notifier.setHeadline(value.trim());
                  setState(() => _isEditingHeadline = false);
                },
                onCancelHeadlineEdit: () {
                  setState(() => _isEditingHeadline = false);
                },
                onToggleHeadlineDictation: () async {
                  if (_isDictatingHeadline) {
                    await notifier.stopHeadlineDictation();
                    setState(() => _isDictatingHeadline = false);
                  } else {
                    if (!await _gateMic(isStart: true)) return;
                    setState(() => _isDictatingHeadline = true);
                    await notifier.startHeadlineDictation();
                  }
                },
                onCategoryTap: () => _showAdvancedSettings(context),
                onDeleteStory: notifier.storyStatus == 'draft'
                    ? () => _confirmDeleteStory(context, notifier)
                    : null,
              ),

              // === Zone 2: Notepad body ===
              Expanded(
                child: state.paragraphs.isEmpty && !state.isRecording
                    ? _EmptyState(
                        onTapRecord: () async {
                          if (!await _gateMic(isStart: true)) return;
                          _maybeShowCloseTalkHint();
                          // Pre-create an empty paragraph and target its
                          // start so the body widget mounts immediately and
                          // streaming has a TextField to splice into from
                          // the very first transcript chunk. Without this,
                          // the very first recording finishes before the
                          // body is even rendered.
                          final idx = notifier.addEmptyParagraph();
                          notifier.setCursorInsert(idx, 0);
                          notifier.toggleRecording();
                        },
                        onLongPressRecord: () async {
                          if (!await _gateMic(isStart: true)) return;
                          _maybeShowCloseTalkHint();
                          final idx = notifier.addEmptyParagraph();
                          notifier.setCursorInsert(idx, 0);
                          notifier.toggleRecording(saveAudio: true);
                        },
                        onTapType: isReadOnly
                            ? null
                            : () {
                                final idx = notifier.addEmptyParagraph();
                                // The new Evernote-style _SimpleNotepadBody
                                // owns its own per-run TextEditingControllers
                                // and FocusNodes — the legacy _startInlineEdit
                                // path was a no-op there. Signal the body to
                                // request focus on the freshly-added paragraph
                                // so the keyboard pops up immediately.
                                notifier.requestFocusOnParagraph(idx);
                              },
                        tapMicLabel: s.startSpeaking,
                        subtitle: s.speakYourNews,
                      )
                    : _SimpleNotepadBody(
                        state: state,
                        isReadOnly: isReadOnly,
                        onTextRunCommitted: (firstIdx, lastIdx, pieces) {
                          notifier.replaceTextRun(firstIdx, lastIdx, pieces);
                        },
                        onFocusedCursorChanged: (paraIdx, cursorOffset) {
                          if (!mounted) return;
                          if (_focusedParagraphIndex == paraIdx &&
                              _focusedCursorOffset == cursorOffset) {
                            return;
                          }
                          // Defer to after the current build — this
                          // callback fires during didUpdateWidget when
                          // _SimpleNotepadBody syncs controllers from
                          // state, which is mid-build for NotepadScreen.
                          // setState there throws a "setState during build"
                          // assertion; post-frame schedules the rebuild
                          // for the very next frame instead.
                          WidgetsBinding.instance.addPostFrameCallback((_) {
                            if (!mounted) return;
                            if (_focusedParagraphIndex == paraIdx &&
                                _focusedCursorOffset == cursorOffset) {
                              return;
                            }
                            setState(() {
                              _focusedParagraphIndex = paraIdx;
                              _focusedCursorOffset = cursorOffset;
                            });
                          });
                        },
                        onTextSelectionChanged: (hasSelection) {
                          if (_hasTextSelection == hasSelection) return;
                          // Same post-frame deferral as onCursorChanged —
                          // selection-change notifications also originate
                          // from the controller-sync path during build.
                          WidgetsBinding.instance.addPostFrameCallback((_) {
                            if (!mounted) return;
                            if (_hasTextSelection == hasSelection) return;
                            setState(() => _hasTextSelection = hasSelection);
                          });
                        },
                        onPendingFocusHandled: () =>
                            notifier.clearPendingFocus(),
                        onRemoveMedia: (index) {
                          final para = state.paragraphs[index];
                          if (!para.hasMedia) return;
                          String titleText;
                          String contentText;
                          switch (para.mediaType) {
                            case MediaType.audio:
                              titleText = s.deleteAudioTitle;
                              contentText = s.deleteAudioMsg;
                              break;
                            case MediaType.photo:
                              titleText = s.deletePhotoTitle;
                              contentText = s.deletePhotoMsg;
                              break;
                            case MediaType.video:
                              titleText = s.deleteVideoTitle;
                              contentText = s.deleteVideoMsg;
                              break;
                            case MediaType.document:
                              titleText = s.deleteDocTitle;
                              contentText = s.deleteDocMsg;
                              break;
                            default:
                              titleText = s.deleteFileTitle;
                              contentText = s.deleteFileMsg;
                          }
                          showDialog<bool>(
                            context: context,
                            builder: (ctx) => AlertDialog(
                              title: Text(
                                titleText,
                                style: AppTypography.odiaTitleLarge.copyWith(
                                  fontSize: 18,
                                ),
                              ),
                              content: Text(
                                contentText,
                                style: AppTypography.odiaBodyMedium,
                              ),
                              actions: [
                                TextButton(
                                  onPressed: () => Navigator.pop(ctx, false),
                                  child: Text(
                                    s.cancel,
                                    style: TextStyle(
                                      color: context.t.bodyColor,
                                    ),
                                  ),
                                ),
                                TextButton(
                                  onPressed: () => Navigator.pop(ctx, true),
                                  child: Text(
                                    s.deleteBtn,
                                    style: const TextStyle(
                                      color: AppColors.vrCoral,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ).then((confirmed) {
                            if (confirmed == true) {
                              notifier.removeMedia(index);
                            }
                          });
                        },
                        onOcrPhoto: (index) =>
                            notifier.runOcrOnParagraph(index),
                        onUpdateTable: (index, data) =>
                            notifier.updateParagraphTable(index, data),
                        onTapEmptySpace: () {
                          // Drop focus from any TextField, dismissing the
                          // keyboard. Provider-level "selection" state isn't
                          // used in the new editor.
                          FocusManager.instance.primaryFocus?.unfocus();
                        },
                      ),
              ),

              // === Error banner ===
              if (state.error != null)
                _ErrorBanner(
                  message: state.error!,
                  onDismiss: () => notifier.clearError(),
                ),

              // Advanced Settings row removed — pending a redesign of
              // what actually goes there. AI Refine now lives as the
              // floating gradient FAB in the outer Stack (see
              // _AiRefineFab below); the Settings entry point will be
              // re-added once we know where it should live.

              // === File attachment progress indicator ===
              if (state.isOcrProcessing)
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.lg,
                    vertical: AppSpacing.sm,
                  ),
                  color: context.t.cardBg,
                  child: Row(
                    children: [
                      SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: context.t.primary,
                        ),
                      ),
                      const SizedBox(width: AppSpacing.md),
                      Text(
                        s.attachingFile,
                        style: AppTypography.odiaBodySmall.copyWith(
                          color: context.t.primary,
                        ),
                      ),
                    ],
                  ),
                ),

              // === Zone 3: Bottom bar ===
              TextFieldTapRegion(
                child: isReadOnly
                    // Read-only mode: only show attachment button
                    ? _IdleBottomBar(
                        canSubmit: false,
                        isProcessing: false,
                        hasTextSelection: false,
                        isReadOnly: true,
                        onAttach: () => _showAttachMenu(context),
                        onRecord: () {},
                        onLongPressRecord: () {},
                        onRewrite: () {},
                        onSubmit: () {},
                      )
                    : state.isSpeechEditing && _instructingParagraphIndex != null
                        ? _AIInstructionBottomBar(
                            transcript: state.speechEditTranscript,
                            onApply: _stopAIInstruction,
                            onCancel: _cancelAIInstruction,
                          )
                        : state.isRecording
                            ? _RecordingBottomBar(
                                formattedDuration: state.formattedDuration,
                                waveformController: _waveformController,
                                isAudioSaveMode: state.isAudioSaveMode,
                                isNoisy: state.isNoisyEnvironment,
                                moveCloserLabel: s.moveCloserHint,
                                speakerFilterActive: state.speakerFilterActive,
                                isSpeakerVerified: state.isSpeakerVerified,
                                onStop: () => notifier.toggleRecording(),
                              )
                            : _IdleBottomBar(
                                canSubmit: notifier.canSubmit,
                                isProcessing: state.isProcessing,
                                hasTextSelection: _hasTextSelection,
                                onAttach: () => _showAttachMenu(context),
                                onRecord: () async {
                                  if (!await _gateMic(isStart: true)) return;
                                  _maybeShowCloseTalkHint();
                                  // Decide where the live transcript should
                                  // splice in. Priority:
                                  //   1. The currently focused TextField's
                                  //      caret (user explicitly placed it).
                                  //   2. End of the last text paragraph
                                  //      (default append-style flow).
                                  // Streaming requires cursor-insert mode,
                                  // so we always pick a target if any text
                                  // paragraph exists.
                                  int? paraIdx = _focusedParagraphIndex;
                                  int? cursorPos = _focusedCursorOffset;
                                  if (paraIdx == null || cursorPos == null) {
                                    final paras = state.paragraphs;
                                    for (int i = paras.length - 1; i >= 0; i--) {
                                      final p = paras[i];
                                      if (!p.hasMedia && !p.isTable) {
                                        paraIdx = i;
                                        cursorPos = p.text.length;
                                        break;
                                      }
                                    }
                                  }
                                  if (paraIdx != null && cursorPos != null) {
                                    notifier.setCursorInsert(paraIdx, cursorPos);
                                  }
                                  notifier.toggleRecording();
                                },
                                onLongPressRecord: () async {
                                  if (!await _gateMic(isStart: true)) return;
                                  _maybeShowCloseTalkHint();
                                  notifier.toggleRecording(saveAudio: true);
                                },
                                onRewrite: () {
                                  // AI rewrite operates on the focused
                                  // paragraph (whole-paragraph rewrite). The
                                  // legacy selection-aware path is dropped
                                  // for simplicity in the new editor.
                                  final idx = _focusedParagraphIndex;
                                  if (idx != null) {
                                    _startAIInstruction(idx);
                                  }
                                },
                                onSubmit: () {
                                  if (notifier.canSubmit) {
                                    _confirmSubmit(notifier);
                                  }
                                },
                              ),
              ),
            ],
          ),
        ),
        // ── Floating AI Refine FAB ─────────────────────────────────────
        // Visible only when there's text content to refine and the
        // reporter isn't actively recording / dictating. Bottom-right,
        // pushed well above the action row (~140px clears Attach +
        // recording mic + Submit + safe area) so it never overlaps.
        // Adds the device's safe-area inset on top so it stays in the
        // same visual position across notch/home-indicator phones.
        if (!state.isRecording &&
            !isReadOnly &&
            state.paragraphs
                .where((p) =>
                    !p.hasMedia && !p.isTable && p.text.trim().isNotEmpty)
                .isNotEmpty)
          Positioned(
            right: AppSpacing.base,
            bottom: 140 + MediaQuery.of(context).padding.bottom,
            child: _AiRefineFab(
              onTap: () => notifier.generateStory(),
              isGenerating: state.isGeneratingStory,
            ),
          ),
      ],
    ),
    );
  }

  Future<void> _confirmSubmit(NotepadNotifier notifier) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(s.submitStoryTitle),
        content: Text(s.submitStoryConfirm),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: Text(s.no),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: Text(s.yes),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      final success = await notifier.submitStory();
      if (mounted) {
        if (success) {
          await _showSubmitSuccessOverlay();
          if (mounted) {
            notifier.reset();
            context.go('/home');
          }
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(s.storySubmitFailed),
              backgroundColor: AppColors.error,
              behavior: SnackBarBehavior.floating,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
              ),
            ),
          );
        }
      }
    }
  }

  Future<void> _showSubmitSuccessOverlay() async {
    final overlay = Overlay.of(context);
    final entry = OverlayEntry(builder: (_) => const _SubmitSuccessOverlay());
    overlay.insert(entry);
    await Future.delayed(const Duration(milliseconds: 1800));
    entry.remove();
  }

  Future<void> _confirmDeleteStory(BuildContext context, NotepadNotifier notifier) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(s.deleteThisDraft),
        content: Text(
          ref.read(notepadProvider).headline.isNotEmpty
            ? ref.read(notepadProvider).headline
            : s.untitledDraft,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: Text(s.no),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: Text(
              s.remove,
              style: const TextStyle(color: AppColors.coral500),
            ),
          ),
        ],
      ),
    );
    if (confirmed == true && context.mounted) {
      // Delete the story on the server
      final storyId = notifier.serverStoryId;
      if (storyId != null) {
        await ref.read(storiesProvider.notifier).deleteStory(storyId);
      }
      ref.read(storiesProvider.notifier).fetchStories();
      if (context.mounted) {
        context.pop();
      }
      notifier.reset();
    }
  }

  void _showAdvancedSettings(BuildContext context) {
    final state = ref.read(notepadProvider);
    final notifier = ref.read(notepadProvider.notifier);

    // Prefer the org's master list of categories when provided; fall back to
    // the global default list otherwise. Reporters from constrained orgs only
    // see categories their newsroom has approved.
    final orgCats = ref.read(authProvider).reporter?.org?.categories ?? const <String>[];
    final categoryKeys = orgCats.isNotEmpty ? orgCats : kDefaultCategoryKeys;

    showModalBottomSheet(
      context: context,
      backgroundColor: context.t.cardBg,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(
          top: Radius.circular(AppSpacing.radiusLg),
        ),
      ),
      builder: (ctx) {
        String? selectedCategory = state.category;

        return StatefulBuilder(
          builder: (ctx, setModalState) {
            return SafeArea(
              child: Padding(
                padding: const EdgeInsets.all(AppSpacing.lg),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Drag handle
                    Center(
                      child: Container(
                        width: 40,
                        height: 4,
                        decoration: BoxDecoration(
                          color: context.t.dividerColor,
                          borderRadius: BorderRadius.circular(2),
                        ),
                      ),
                    ),
                    const SizedBox(height: AppSpacing.lg),

                    // Title
                    Text(
                      s.advancedSettings,
                      style: AppTypography.odiaTitleLarge,
                    ),
                    const SizedBox(height: AppSpacing.lg),

                    // Category label
                    Text(
                      s.categoryFilter,
                      style: AppTypography.odiaBodyMedium.copyWith(
                        fontWeight: FontWeight.w600,
                        color: context.t.mutedColor,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.sm),

                    // "Auto" chip + category chips
                    Wrap(
                      spacing: AppSpacing.sm,
                      runSpacing: AppSpacing.sm,
                      children: [
                        // Auto (default) chip
                        GestureDetector(
                          onTap: () {
                            setModalState(() => selectedCategory = null);
                            notifier.setCategory(null);
                          },
                          child: Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: AppSpacing.md,
                              vertical: AppSpacing.sm,
                            ),
                            decoration: BoxDecoration(
                              color: selectedCategory == null
                                  ? context.t.primary
                                  : context.t.actionChipBg,
                              borderRadius:
                                  BorderRadius.circular(AppSpacing.radiusFull),
                            ),
                            child: Text(
                              s.autoCategory,
                              style: AppTypography.odiaBodySmall.copyWith(
                                color: selectedCategory == null
                                    ? context.t.onPrimary
                                    : context.t.bodyColor,
                                fontWeight: selectedCategory == null
                                    ? FontWeight.w600
                                    : FontWeight.w400,
                              ),
                            ),
                          ),
                        ),
                        // Category chips
                        ...categoryKeys.map((key) {
                          final isActive = selectedCategory == key;
                          return GestureDetector(
                            onTap: () {
                              setModalState(
                                  () => selectedCategory = key);
                              notifier.setCategory(key);
                            },
                            child: Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: AppSpacing.md,
                                vertical: AppSpacing.sm,
                              ),
                              decoration: BoxDecoration(
                                color: isActive
                                    ? context.t.primary
                                    : context.t.actionChipBg,
                                borderRadius: BorderRadius.circular(
                                    AppSpacing.radiusFull),
                              ),
                              child: Text(
                                s.categoryLabel(key),
                                style: AppTypography.odiaBodySmall.copyWith(
                                  color: isActive
                                      ? context.t.onPrimary
                                      : context.t.bodyColor,
                                  fontWeight: isActive
                                      ? FontWeight.w600
                                      : FontWeight.w400,
                                ),
                              ),
                            ),
                          );
                        }),
                      ],
                    ),

                    const SizedBox(height: AppSpacing.xl),

                    // Done button
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        onPressed: () => Navigator.pop(ctx),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: context.t.primary,
                          foregroundColor: context.t.onPrimary,
                          shape: RoundedRectangleBorder(
                            borderRadius:
                                BorderRadius.circular(AppSpacing.radiusMd),
                          ),
                          padding: const EdgeInsets.symmetric(
                              vertical: AppSpacing.md),
                        ),
                        child: Text(
                          s.done,
                          style: AppTypography.odiaTitleLarge
                              .copyWith(color: context.t.onPrimary),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }

  void _showAttachMenu(BuildContext context) {
    final notifier = ref.read(notepadProvider.notifier);
    showModalBottomSheet(
      context: context,
      backgroundColor: context.t.cardBg,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(
          top: Radius.circular(AppSpacing.radiusLg),
        ),
      ),
      builder: (ctx) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.lg),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: context.t.dividerColor,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                const SizedBox(height: AppSpacing.lg),
                Text(
                  s.attachFile,
                  style: AppTypography.odiaTitleLarge,
                ),
                const SizedBox(height: AppSpacing.lg),
                _AttachOption(
                  icon: LucideIcons.camera,
                  iconColor: context.t.primary,
                  bgColor: context.t.primaryLight,
                  label: s.camera,
                  subtitle: s.takeAPhoto,
                  onTap: () {
                    Navigator.pop(ctx);
                    notifier.pickAndAttachMedia(MediaType.photo, fromCamera: true);
                  },
                ),
                const SizedBox(height: AppSpacing.sm),
                _AttachOption(
                  icon: LucideIcons.image,
                  iconColor: AppColors.teal500,
                  bgColor: AppColors.teal50,
                  label: s.gallery,
                  subtitle: s.pickAPhoto,
                  onTap: () {
                    Navigator.pop(ctx);
                    notifier.pickAndAttachMedia(MediaType.photo);
                  },
                ),
                const SizedBox(height: AppSpacing.sm),
                _AttachOption(
                  icon: LucideIcons.fileText,
                  iconColor: AppColors.gold600,
                  bgColor: AppColors.gold50,
                  label: s.document,
                  subtitle: 'PDF, DOCX, PPTX, Audio',
                  onTap: () {
                    Navigator.pop(ctx);
                    notifier.pickAndAttachMedia(MediaType.document);
                  },
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

// =============================================================================
// Zone 1: Header
// =============================================================================

class _NotepadHeader extends ConsumerWidget {
  final NotepadState state;
  final String storyStatus;
  final TextEditingController headlineController;
  final bool isEditingHeadline;
  final bool isDictatingHeadline;
  final bool canUndo;
  final bool canRedo;
  final VoidCallback onBack;
  final VoidCallback onEditHeadline;
  final ValueChanged<String> onSubmitHeadline;
  final VoidCallback onCancelHeadlineEdit;
  final VoidCallback onToggleHeadlineDictation;
  final VoidCallback onUndo;
  final VoidCallback onRedo;
  final VoidCallback? onCategoryTap;
  final VoidCallback? onDeleteStory;

  const _NotepadHeader({
    required this.state,
    this.storyStatus = 'draft',
    required this.headlineController,
    required this.isEditingHeadline,
    required this.isDictatingHeadline,
    required this.canUndo,
    required this.canRedo,
    required this.onBack,
    required this.onEditHeadline,
    required this.onSubmitHeadline,
    required this.onCancelHeadlineEdit,
    required this.onToggleHeadlineDictation,
    required this.onUndo,
    required this.onRedo,
    this.onCategoryTap,
    this.onDeleteStory,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = context.t;
    final s = AppStrings.of(ref);
    return Container(
      decoration: BoxDecoration(
        color: t.cardBg,
        border: Border(
          bottom: BorderSide(
            color: t.dividerColor,
          ),
        ),
      ),
      child: SafeArea(
        bottom: false,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Top row: back + draft badge + more
            Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.sm,
                vertical: AppSpacing.xs,
              ),
              child: Row(
                children: [
                  IconButton(
                    icon: Icon(
                      LucideIcons.arrowLeft,
                      size: 20,
                      color: t.bodyColor,
                    ),
                    onPressed: onBack,
                    tooltip: s.tooltipBack,
                  ),
                  const Spacer(),
                  // Undo / Redo (only for draft stories)
                  if (storyStatus == 'draft') ...[
                    IconButton(
                      icon: Icon(
                        LucideIcons.undo2,
                        size: 18,
                        color: canUndo ? t.bodyColor : t.dividerColor,
                      ),
                      onPressed: canUndo ? onUndo : null,
                      tooltip: s.tooltipUndo,
                      visualDensity: VisualDensity.compact,
                    ),
                    IconButton(
                      icon: Icon(
                        LucideIcons.redo2,
                        size: 18,
                        color: canRedo ? t.bodyColor : t.dividerColor,
                      ),
                      onPressed: canRedo ? onRedo : null,
                      tooltip: s.tooltipRedo,
                      visualDensity: VisualDensity.compact,
                    ),
                  ],
                  const SizedBox(width: AppSpacing.xs),
                  if (onDeleteStory != null)
                    PopupMenuButton<String>(
                      icon: Icon(
                        LucideIcons.moreVertical,
                        size: 20,
                        color: t.mutedColor,
                      ),
                      onSelected: (value) {
                        if (value == 'delete') {
                          onDeleteStory!();
                        }
                      },
                      itemBuilder: (_) => [
                        PopupMenuItem(
                          value: 'delete',
                          child: Row(
                            children: [
                              const Icon(LucideIcons.trash2, size: 16,
                                  color: AppColors.coral500),
                              const SizedBox(width: AppSpacing.sm),
                              Text(
                                s.deleteDraft,
                                style: TextStyle(color: AppColors.coral500),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                ],
              ),
            ),

            // Server-assigned display id (e.g. "PNS-26-1234"). Sits as a
            // small mono label above the headline so reviewers and
            // reporters can refer to a specific story by a short
            // human-readable id without copying a UUID.
            if (state.displayId != null && state.displayId!.isNotEmpty)
              Padding(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.base,
                  0,
                  AppSpacing.base,
                  AppSpacing.xs,
                ),
                child: Text(
                  state.displayId!,
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 11,
                    fontWeight: FontWeight.w500,
                    letterSpacing: 0.6,
                    color: t.mutedColor,
                  ),
                ),
              ),

            // Headline
            Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.base,
              ),
              child: isEditingHeadline
                  ? TextField(
                      controller: headlineController,
                      autofocus: true,
                      maxLines: 2,
                      maxLength: 40,
                      style: AppTypography.odiaHeadlineMedium.copyWith(
                        fontSize: 18,
                      ),
                      keyboardType: TextInputType.text,
                      decoration: InputDecoration(
                        hintText: s.titleHintWrite,
                        hintStyle: AppTypography.odiaHeadlineMedium.copyWith(
                          fontSize: 18,
                          color: t.mutedColor,
                        ),
                        border: InputBorder.none,
                        enabledBorder: InputBorder.none,
                        focusedBorder: InputBorder.none,
                        isDense: true,
                        contentPadding: EdgeInsets.zero,
                        counterText: '',
                      ),
                      onSubmitted: onSubmitHeadline,
                      onTapOutside: (_) {
                        onSubmitHeadline(headlineController.text);
                      },
                    )
                  : isDictatingHeadline
                    // Voice dictation mode — show live headline with stop button
                    ? Row(
                        children: [
                          Expanded(
                            child: Text(
                              state.headline.isNotEmpty
                                  ? state.headline
                                  : s.titleHintSpeak,
                              style: AppTypography.odiaHeadlineMedium.copyWith(
                                fontSize: 18,
                                color: AppColors.coral500,
                              ),
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          const SizedBox(width: AppSpacing.sm),
                          GestureDetector(
                            onTap: onToggleHeadlineDictation,
                            child: Container(
                              width: 28,
                              height: 28,
                              decoration: const BoxDecoration(
                                color: AppColors.coral500,
                                shape: BoxShape.circle,
                              ),
                              child: const Icon(
                                LucideIcons.square,
                                size: 12,
                                color: Colors.white,
                              ),
                            ),
                          ),
                        ],
                      )
                    : GestureDetector(
                      onDoubleTap: storyStatus == 'draft' ? onEditHeadline : null,
                      child: Row(
                        children: [
                          Expanded(
                            child: Text(
                              state.headline.isNotEmpty
                                  ? state.headline
                                  : s.titleHintWrite,
                              style: AppTypography.odiaHeadlineMedium.copyWith(
                                fontSize: 18,
                                color: state.headline.isNotEmpty
                                    ? t.headingColor
                                    : t.mutedColor,
                              ),
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          if (!state.isGeneratingTitle && storyStatus == 'draft') ...[
                            const SizedBox(width: AppSpacing.xs),
                            GestureDetector(
                              onTap: onToggleHeadlineDictation,
                              child: Container(
                                width: 28,
                                height: 28,
                                decoration: BoxDecoration(
                                  color: t.primaryLight,
                                  shape: BoxShape.circle,
                                ),
                                child: Icon(
                                  LucideIcons.mic,
                                  size: 14,
                                  color: t.primary,
                                ),
                              ),
                            ),
                          ],
                          if (state.isGeneratingTitle) ...[
                            const SizedBox(width: AppSpacing.sm),
                            SizedBox(
                              width: 14,
                              height: 14,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: t.primary,
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
            ),

            // Status + Category + Location chips row
            Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.base,
                AppSpacing.sm,
                AppSpacing.base,
                0,
              ),
              child: Wrap(
                spacing: AppSpacing.sm,
                runSpacing: AppSpacing.xs,
                children: [
                  // Status badge (dynamic based on actual story status)
                  Builder(builder: (_) {
                    final Color badgeBg;
                    final Color badgeText;
                    final String label;
                    switch (storyStatus) {
                      case 'submitted':
                        badgeBg = AppColors.success.withValues(alpha: 0.12);
                        badgeText = AppColors.success;
                        label = s.statusSubmitted;
                      case 'published':
                        badgeBg = AppColors.success.withValues(alpha: 0.12);
                        badgeText = AppColors.success;
                        label = s.statusPublished;
                      case 'review':
                        badgeBg = AppColors.info.withValues(alpha: 0.12);
                        badgeText = AppColors.info;
                        label = s.statusReview;
                      default:
                        badgeBg = t.draftBg;
                        badgeText = t.draftText;
                        label = s.statusDraft;
                    }
                    return Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: AppSpacing.sm,
                        vertical: AppSpacing.xs,
                      ),
                      decoration: BoxDecoration(
                        color: badgeBg,
                        borderRadius: BorderRadius.circular(AppSpacing.radiusFull),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Container(
                            width: 6,
                            height: 6,
                            decoration: BoxDecoration(
                              color: badgeText,
                              shape: BoxShape.circle,
                            ),
                          ),
                          const SizedBox(width: 4),
                          Text(
                            label,
                            style: AppTypography.caption.copyWith(
                              color: badgeText,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                    );
                  }),
                  if (state.category != null)
                    GestureDetector(
                      onTap: onCategoryTap,
                      child: _MetadataChip(
                        icon: LucideIcons.tag,
                        label: s.categoryLabel(state.category),
                        bgColor: t.primaryLight,
                        iconColor: t.primary,
                        textColor: t.primary,
                      ),
                    ),
                  if (state.location != null)
                    _MetadataChip(
                      icon: LucideIcons.mapPin,
                      label: state.location!,
                      bgColor: AppColors.teal50,
                      iconColor: AppColors.teal500,
                      textColor: AppColors.teal600,
                    ),
                ],
              ),
            ),

            const SizedBox(height: AppSpacing.md),
          ],
        ),
      ),
    );
  }
}

class _MetadataChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color bgColor;
  final Color iconColor;
  final Color textColor;

  const _MetadataChip({
    required this.icon,
    required this.label,
    required this.bgColor,
    required this.iconColor,
    required this.textColor,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm,
        vertical: AppSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(AppSpacing.radiusFull),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: iconColor),
          const SizedBox(width: AppSpacing.xs),
          Text(
            label,
            style: AppTypography.caption.copyWith(
              color: textColor,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

// =============================================================================
// Zone 2: Empty state
// =============================================================================

class _EmptyState extends ConsumerWidget {
  final VoidCallback onTapRecord;
  final VoidCallback onLongPressRecord;
  final VoidCallback? onTapType;
  final String tapMicLabel;
  final String subtitle;

  const _EmptyState({
    required this.onTapRecord,
    required this.onLongPressRecord,
    this.onTapType,
    required this.tapMicLabel,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = context.t;
    final s = AppStrings.of(ref);
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Big mic circle
          Tooltip(
            message: s.tooltipMic,
            child: Semantics(
              label: s.tooltipMic,
              button: true,
              child: GestureDetector(
                onTap: onTapRecord,
                onLongPress: () {
                  HapticFeedback.mediumImpact();
                  onLongPressRecord();
                },
                child: Container(
                  width: 56,
                  height: 56,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: t.primaryGradient,
                    boxShadow: [
                      BoxShadow(
                        color: t.primary.withValues(alpha: 0.3),
                        blurRadius: 24,
                        offset: const Offset(0, 8),
                      ),
                    ],
                  ),
                  child: Icon(
                    LucideIcons.mic,
                    color: t.onPrimary,
                    size: 24,
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.lg),
          Text(
            tapMicLabel,
            style: AppTypography.odiaTitleLarge.copyWith(
              color: t.bodyColor,
            ),
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            subtitle,
            style: AppTypography.odiaBodyMedium.copyWith(
              color: t.mutedColor,
            ),
          ),
          if (onTapType != null) ...[
            const SizedBox(height: AppSpacing.lg),
            // Divider with "or" label
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(width: 40, height: 1, color: t.dividerColor),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
                  child: Text(
                    s.isOdia ? 'କିମ୍ୱା' : 'or',
                    style: AppTypography.odiaBodySmall.copyWith(color: t.mutedColor),
                  ),
                ),
                Container(width: 40, height: 1, color: t.dividerColor),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
            // Type-instead button
            OutlinedButton.icon(
              onPressed: onTapType,
              icon: const Icon(LucideIcons.keyboard, size: 16),
              label: Text(s.typeText),
              style: OutlinedButton.styleFrom(
                foregroundColor: t.bodyColor,
                side: BorderSide(color: t.dividerColor),
                padding: const EdgeInsets.symmetric(
                  horizontal: AppSpacing.lg,
                  vertical: AppSpacing.sm,
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(20),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

// =============================================================================
// Zone 2: Simple notepad body
//
// Single editable surface per text-run, with media/tables interleaved.
// Reporters get one continuous TextField for typing — no per-paragraph chips,
// no scroll-to-focus jumping, no accidental delete. Media and table blocks
// render between text runs as standalone widgets with their own remove
// confirms.
// =============================================================================

/// A "run" of consecutive paragraphs in the notepad: either one or more
/// text paragraphs grouped into one editable surface, or a single media /
/// table paragraph rendered as a standalone widget.
class _Run {
  final bool isText;
  final int firstIdx; // inclusive
  final int lastIdx;  // inclusive (== firstIdx for media/table)
  const _Run.text(this.firstIdx, this.lastIdx) : isText = true;
  const _Run.atomic(int idx)
      : isText = false,
        firstIdx = idx,
        lastIdx = idx;
  String runId(List<Paragraph> paras) => paras[firstIdx].id;
}

List<_Run> _groupRuns(List<Paragraph> paras) {
  final runs = <_Run>[];
  int i = 0;
  while (i < paras.length) {
    final p = paras[i];
    if (p.hasMedia || p.isTable) {
      runs.add(_Run.atomic(i));
      i++;
      continue;
    }
    int j = i;
    while (j + 1 < paras.length &&
        !paras[j + 1].hasMedia &&
        !paras[j + 1].isTable) {
      j++;
    }
    runs.add(_Run.text(i, j));
    i = j + 1;
  }
  return runs;
}

class _SimpleNotepadBody extends StatefulWidget {
  final NotepadState state;
  final bool isReadOnly;
  final ValueChanged<int>? onRemoveMedia;
  final ValueChanged<int>? onOcrPhoto;
  final void Function(int index, List<List<String>> data)? onUpdateTable;
  final void Function(int firstIdx, int lastIdx, List<String> newTexts) onTextRunCommitted;
  /// Reports which paragraph index + cursor offset is currently focused.
  /// Used by the bottom bar's Record button to insert transcripts at the
  /// right spot. Null offset means no run is focused.
  final void Function(int? paragraphIndex, int? cursorOffset)? onFocusedCursorChanged;
  final ValueChanged<bool>? onTextSelectionChanged;
  /// Called after the body has actually requested focus on the paragraph
  /// referenced by `state.pendingFocusParagraphIndex`. The parent should
  /// clear the flag so the same signal doesn't re-fire on subsequent
  /// state changes.
  final VoidCallback? onPendingFocusHandled;
  final VoidCallback onTapEmptySpace;

  const _SimpleNotepadBody({
    required this.state,
    required this.isReadOnly,
    required this.onTextRunCommitted,
    required this.onTapEmptySpace,
    this.onRemoveMedia,
    this.onOcrPhoto,
    this.onUpdateTable,
    this.onFocusedCursorChanged,
    this.onTextSelectionChanged,
    this.onPendingFocusHandled,
  });

  @override
  State<_SimpleNotepadBody> createState() => _SimpleNotepadBodyState();
}

class _SimpleNotepadBodyState extends State<_SimpleNotepadBody> {
  /// Per text-run controllers, keyed by the run's first paragraph id.
  final Map<String, TextEditingController> _controllers = {};
  final Map<String, FocusNode> _focusNodes = {};
  /// What text we last saw from the provider for each run. Used to detect
  /// external updates (voice/AI/undo) so we know when to refresh the
  /// controller — vs. echoing back our own typing.
  final Map<String, String> _lastSyncedText = {};
  /// Currently focused text-run id, or null.
  String? _focusedRunId;
  /// Per-run debounce timers for committing typing back to the provider.
  final Map<String, Future<void>> _commitDebounces = {};
  static const _commitDelay = Duration(milliseconds: 500);

  // While a cursor-insert recording is active, [_streamingRunId] points
  // at the text-run whose TextField should display the live transcript
  // preview underneath it. The preview is a separate coral-colored Text
  // widget rendered inline (see build()), not a splice into the
  // controller — that path was unreliable across cold WS connections.
  String? _streamingRunId;

  @override
  void didUpdateWidget(covariant _SimpleNotepadBody oldWidget) {
    super.didUpdateWidget(oldWidget);
    _syncControllersFromState();
    _syncLiveStreaming(widget.state);
    _maybeHandlePendingFocus();
  }

  /// Honour `state.pendingFocusParagraphIndex` — find the FocusNode for
  /// the run containing that paragraph and request focus. Schedules the
  /// actual focus + flag-clear in a post-frame callback so we don't
  /// touch FocusNodes mid-build.
  void _maybeHandlePendingFocus() {
    final pending = widget.state.pendingFocusParagraphIndex;
    if (pending == null) return;
    final paras = widget.state.paragraphs;
    if (pending < 0 || pending >= paras.length) {
      widget.onPendingFocusHandled?.call();
      return;
    }
    String? targetRunId;
    for (final run in _groupRuns(paras)) {
      if (run.isText && pending >= run.firstIdx && pending <= run.lastIdx) {
        targetRunId = paras[run.firstIdx].id;
        break;
      }
    }
    if (targetRunId == null) {
      widget.onPendingFocusHandled?.call();
      return;
    }
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final node = _focusNodes[targetRunId];
      node?.requestFocus();
      widget.onPendingFocusHandled?.call();
    });
  }

  /// Track which text-run is the streaming target. We don't splice the
  /// live transcript into the TextField controller anymore — that path
  /// proved flaky on cold WS connections. Instead the build method
  /// renders an inline coral Text widget right after the target run's
  /// TextField while recording, showing `state.liveTranscript`. On
  /// commit, the provider stamps the final text into the paragraph and
  /// we explicitly refresh the controller from it; the coral preview
  /// disappears because cursorInsertParagraphIndex is cleared.
  void _syncLiveStreaming(NotepadState newState) {
    final isStreamingNow = newState.cursorInsertParagraphIndex != null;

    if (isStreamingNow && _streamingRunId == null) {
      _enterStreamingFromState(newState);
    }
    if (!isStreamingNow && _streamingRunId != null) {
      // Recording committed. Force-refresh the controller from the
      // committed paragraph text — this sync skipped the streaming run
      // earlier, so the run-level controller is still showing pre-record
      // text. We bypass the "ctrl.text == lastSynced" guard because the
      // controller may differ from lastSynced if anything (e.g. ghost
      // setState chains) wrote to it during recording.
      final runId = _streamingRunId!;
      final ctrl = _controllers[runId];
      final paras = newState.paragraphs;
      _Run? run;
      for (final r in _groupRuns(paras)) {
        if (r.isText && paras[r.firstIdx].id == runId) {
          run = r;
          break;
        }
      }
      if (run != null && ctrl != null) {
        final joined = paras
            .sublist(run.firstIdx, run.lastIdx + 1)
            .map((p) => p.text)
            .join('\n\n');
        if (ctrl.text != joined) {
          ctrl.value = TextEditingValue(
            text: joined,
            selection: TextSelection.collapsed(offset: joined.length),
          );
        }
        _lastSyncedText[runId] = joined;
      }
      _streamingRunId = null;
    }
  }

  void _enterStreamingFromState(NotepadState st) {
    final pi = st.cursorInsertParagraphIndex;
    if (pi == null) {
      debugPrint('[BODY] _enterStreaming: cursorInsert=null, skip');
      return;
    }
    final paras = st.paragraphs;
    if (pi < 0 || pi >= paras.length) {
      debugPrint('[BODY] _enterStreaming: pi=$pi out of range (paras=${paras.length})');
      return;
    }

    for (final run in _groupRuns(paras)) {
      if (run.isText && pi >= run.firstIdx && pi <= run.lastIdx) {
        _streamingRunId = paras[run.firstIdx].id;
        debugPrint('[BODY] _enterStreaming: _streamingRunId=$_streamingRunId pi=$pi');
        return;
      }
    }
    debugPrint('[BODY] _enterStreaming: no text run contains pi=$pi');
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _syncControllersFromState();
      // Pick up an already-active recording (e.g. user tapped Record from
      // _EmptyState, which created the first paragraph and mounted us
      // mid-recording).
      _syncLiveStreaming(widget.state);
      // Same pickup for the "Type" CTA path: the parent set
      // pendingFocusParagraphIndex BEFORE we mounted, so didUpdateWidget
      // will never fire for it. Honour the signal here on first mount.
      _maybeHandlePendingFocus();
    });
  }

  @override
  void dispose() {
    for (final c in _controllers.values) {
      c.dispose();
    }
    for (final f in _focusNodes.values) {
      f.dispose();
    }
    _controllers.clear();
    _focusNodes.clear();
    super.dispose();
  }

  void _syncControllersFromState() {
    final paras = widget.state.paragraphs;
    final runs = _groupRuns(paras).where((r) => r.isText).toList();
    final liveIds = <String>{};

    for (final run in runs) {
      final id = run.runId(paras);
      liveIds.add(id);
      final joined = paras
          .sublist(run.firstIdx, run.lastIdx + 1)
          .map((p) => p.text)
          .join('\n\n');

      var ctrl = _controllers[id];
      if (ctrl == null) {
        ctrl = TextEditingController(text: joined);
        _controllers[id] = ctrl;
        _lastSyncedText[id] = joined;
        final focus = FocusNode();
        focus.addListener(() => _onFocusChanged(id, focus));
        _focusNodes[id] = focus;
        ctrl.addListener(() => _onTextChanged(id));
      } else {
        // Skip controller updates while we're actively driving it from a
        // live STT stream — _syncLiveStreaming owns the controller text
        // until recording stops.
        if (_streamingRunId == id) continue;
        // Sync controller from provider when the joined text differs and
        // the controller text matches what we last pushed (i.e. the user
        // hasn't typed anything new since last commit). This catches
        // voice-committed text, AI rewrites, and undo/redo even while the
        // TextField is focused.
        final lastSynced = _lastSyncedText[id] ?? '';
        if (joined != ctrl.text && ctrl.text == lastSynced) {
          final newCursor = joined.length;
          ctrl.value = TextEditingValue(
            text: joined,
            selection: TextSelection.collapsed(offset: newCursor),
          );
          _lastSyncedText[id] = joined;
        }
      }
    }

    // Dispose controllers for runs that are no longer present (e.g. user
    // deleted all text in a run, or media/table was inserted that split a
    // run — first paragraph id changed).
    final toRemove = _controllers.keys.where((k) => !liveIds.contains(k)).toList();
    for (final k in toRemove) {
      _controllers.remove(k)?.dispose();
      _focusNodes.remove(k)?.dispose();
      _lastSyncedText.remove(k);
      _commitDebounces.remove(k);
      if (_focusedRunId == k) _focusedRunId = null;
    }
  }

  void _onFocusChanged(String runId, FocusNode focus) {
    if (focus.hasFocus) {
      _focusedRunId = runId;
      _reportFocusedCursor();
    } else if (_focusedRunId == runId) {
      // Only clear if no other run picks up focus immediately
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        if (!_focusNodes.values.any((f) => f.hasFocus)) {
          _focusedRunId = null;
          widget.onFocusedCursorChanged?.call(null, null);
        }
      });
    }
    // Commit typing immediately when focus leaves so a subsequent record/
    // attach action sees the latest paragraph text.
    if (!focus.hasFocus) {
      _commitNow(runId);
    }
  }

  void _onTextChanged(String runId) {
    final ctrl = _controllers[runId];
    if (ctrl == null) return;
    _reportFocusedCursor();
    final sel = ctrl.selection;
    final hasSelection = sel.isValid && !sel.isCollapsed && sel.start >= 0;
    widget.onTextSelectionChanged?.call(hasSelection);
    // Debounced commit. The latest call wins because _commitNow is a no-op
    // when the controller text matches what we last pushed; intervening
    // typing keeps changing the text so the eventual commit reflects the
    // most recent state.
    _commitDebounces[runId] = Future.delayed(_commitDelay, () {
      if (!mounted) return;
      _commitNow(runId);
    });
  }

  void _commitNow(String runId) {
    // While streaming live STT into this run, the controller text is a
    // transient preview; the provider commits the final text on stop.
    if (_streamingRunId == runId) return;
    final ctrl = _controllers[runId];
    if (ctrl == null) return;
    final text = ctrl.text;
    if (_lastSyncedText[runId] == text) return;
    _lastSyncedText[runId] = text;

    final paras = widget.state.paragraphs;
    final run = _groupRuns(paras).firstWhere(
      (r) => r.isText && paras[r.firstIdx].id == runId,
      orElse: () => const _Run.text(-1, -1),
    );
    if (run.firstIdx < 0) return;

    final pieces = text.split(RegExp(r'\n\s*\n'));
    widget.onTextRunCommitted(run.firstIdx, run.lastIdx, pieces);
  }

  void _reportFocusedCursor() {
    final id = _focusedRunId;
    if (id == null) {
      widget.onFocusedCursorChanged?.call(null, null);
      return;
    }
    final ctrl = _controllers[id];
    if (ctrl == null) return;
    final paras = widget.state.paragraphs;
    final run = _groupRuns(paras).firstWhere(
      (r) => r.isText && paras[r.firstIdx].id == id,
      orElse: () => const _Run.text(-1, -1),
    );
    if (run.firstIdx < 0) return;
    final offset = ctrl.selection.baseOffset.clamp(0, ctrl.text.length);
    // Map the (run, offset) to (paragraph index, in-paragraph offset) so the
    // provider's cursor-insert can target the right paragraph.
    var remaining = offset;
    for (int i = run.firstIdx; i <= run.lastIdx; i++) {
      final pText = paras[i].text;
      if (remaining <= pText.length) {
        widget.onFocusedCursorChanged?.call(i, remaining);
        return;
      }
      remaining -= pText.length;
      // The '\n\n' separator between paragraphs in the merged text.
      remaining -= 2;
      if (remaining < 0) {
        widget.onFocusedCursorChanged?.call(i, pText.length);
        return;
      }
    }
    // Fallback: cursor past end → last paragraph end
    widget.onFocusedCursorChanged?.call(run.lastIdx, paras[run.lastIdx].text.length);
  }

  @override
  Widget build(BuildContext context) {
    final paras = widget.state.paragraphs;
    final runs = _groupRuns(paras);

    // Live transcript preview is shown right after the streaming-target
    // run (the run containing cursorInsertParagraphIndex). When recording
    // starts on an empty story, the target is the freshly-created empty
    // paragraph, so the preview appears immediately at the top.
    final liveTranscript = widget.state.liveTranscript;
    final showLivePreview = widget.state.cursorInsertParagraphIndex != null &&
        liveTranscript.isNotEmpty;

    final children = <Widget>[];
    for (final run in runs) {
      if (run.isText) {
        final id = run.runId(paras);
        final ctrl = _controllers[id];
        final focus = _focusNodes[id];
        if (ctrl == null || focus == null) continue;
        children.add(_TextRunField(
          controller: ctrl,
          focusNode: focus,
          readOnly: widget.isReadOnly,
        ));
        if (showLivePreview && id == _streamingRunId) {
          children.add(_LiveTranscriptPreview(text: liveTranscript));
        }
      } else {
        final p = paras[run.firstIdx];
        if (p.hasMedia) {
          children.add(_MediaBlock(
            paragraph: p,
            onRemove: widget.isReadOnly
                ? null
                : () => widget.onRemoveMedia?.call(run.firstIdx),
            onOcr: widget.isReadOnly
                ? null
                : () => widget.onOcrPhoto?.call(run.firstIdx),
          ));
        } else if (p.isTable) {
          children.add(_EditableTableBlock(
            paragraph: p,
            isSelected: false,
            onTableChanged: widget.isReadOnly
                ? null
                : (data) => widget.onUpdateTable?.call(run.firstIdx, data),
          ));
        }
      }
    }

    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: widget.onTapEmptySpace,
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.lg,
          AppSpacing.md,
          AppSpacing.lg,
          AppSpacing.huge,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            ...children,
            // Tail tap zone so users can dismiss focus by tapping below text.
            const SizedBox(height: 200),
          ],
        ),
      ),
    );
  }
}

/// Coral-colored live transcript preview shown inline next to the
/// streaming-target text run while recording. The text content updates
/// as the WS streams partial transcripts. On stop, the provider commits
/// the final transcript into the underlying paragraph and this widget
/// disappears (its parent removes it from the tree because
/// cursorInsertParagraphIndex is cleared).
class _LiveTranscriptPreview extends StatelessWidget {
  final String text;

  const _LiveTranscriptPreview({required this.text});

  @override
  Widget build(BuildContext context) {
    final style = AppTypography.odiaBodyLarge.copyWith(
      color: AppColors.vrCoral,
      height: 1.7,
      fontWeight: FontWeight.w500,
    );
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
      child: Text(text, style: style),
    );
  }
}

/// Borderless multi-line TextField for one text run. No chrome, no
/// per-paragraph chips, no auto-scroll. Uses Odia body typography to match
/// the previous block editor.
class _TextRunField extends StatelessWidget {
  final TextEditingController controller;
  final FocusNode focusNode;
  final bool readOnly;

  const _TextRunField({
    required this.controller,
    required this.focusNode,
    required this.readOnly,
  });

  @override
  Widget build(BuildContext context) {
    final t = context.t;
    final style = AppTypography.odiaBodyLarge.copyWith(
      color: t.bodyColor,
      height: 1.7,
    );
    return TextField(
      controller: controller,
      focusNode: focusNode,
      readOnly: readOnly,
      maxLines: null,
      keyboardType: TextInputType.multiline,
      textCapitalization: TextCapitalization.sentences,
      style: style,
      cursorColor: AppColors.vrCoral,
      decoration: const InputDecoration(
        filled: false,
        fillColor: Colors.transparent,
        border: InputBorder.none,
        enabledBorder: InputBorder.none,
        focusedBorder: InputBorder.none,
        disabledBorder: InputBorder.none,
        errorBorder: InputBorder.none,
        focusedErrorBorder: InputBorder.none,
        isCollapsed: true,
        contentPadding: EdgeInsets.symmetric(vertical: AppSpacing.sm),
      ),
    );
  }
}

// =============================================================================
// Editable table block
// =============================================================================

class _EditableTableBlock extends StatefulWidget {
  final Paragraph paragraph;
  final bool isSelected;
  final void Function(List<List<String>> data)? onTableChanged;

  const _EditableTableBlock({
    required this.paragraph,
    required this.isSelected,
    this.onTableChanged,
  });

  @override
  State<_EditableTableBlock> createState() => _EditableTableBlockState();
}

class _EditableTableBlockState extends State<_EditableTableBlock> {
  late List<List<String>> _data;
  final Map<String, TextEditingController> _controllers = {};

  @override
  void initState() {
    super.initState();
    _data = widget.paragraph.tableData!
        .map((row) => List<String>.from(row))
        .toList();
  }

  @override
  void didUpdateWidget(_EditableTableBlock oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.paragraph.id != widget.paragraph.id) {
      _disposeControllers();
      _data = widget.paragraph.tableData!
          .map((row) => List<String>.from(row))
          .toList();
    }
  }

  void _disposeControllers() {
    for (final c in _controllers.values) {
      c.dispose();
    }
    _controllers.clear();
  }

  @override
  void dispose() {
    _disposeControllers();
    super.dispose();
  }

  TextEditingController _getController(int row, int col) {
    final key = '$row-$col';
    if (!_controllers.containsKey(key)) {
      _controllers[key] = TextEditingController(text: _data[row][col]);
    }
    return _controllers[key]!;
  }

  void _onCellChanged(int row, int col, String value) {
    _data[row][col] = value;
    widget.onTableChanged?.call(_data);
  }

  @override
  Widget build(BuildContext context) {
    final t = context.t;
    if (_data.isEmpty) return const SizedBox.shrink();

    final maxCols = _data.fold<int>(0, (m, row) => row.length > m ? row.length : m);

    return Container(
      margin: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: widget.isSelected
            ? AppColors.vrCoral.withValues(alpha: 0.05)
            : t.cardBg,
        borderRadius: BorderRadius.circular(AppSpacing.radiusSm),
        border: Border.all(
          color: widget.isSelected
              ? AppColors.vrCoral.withValues(alpha: 0.3)
              : t.dividerColor.withValues(alpha: 0.2),
        ),
      ),
      clipBehavior: Clip.antiAlias,
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: DataTable(
          headingRowHeight: 40,
          dataRowMinHeight: 36,
          dataRowMaxHeight: 56,
          horizontalMargin: 12,
          columnSpacing: 16,
          headingRowColor: WidgetStateProperty.all(
            t.dividerColor.withValues(alpha: 0.08),
          ),
          border: TableBorder.all(
            color: t.dividerColor.withValues(alpha: 0.15),
            width: 0.5,
          ),
          columns: List.generate(maxCols, (col) {
            final headerText = _data.isNotEmpty && col < _data[0].length
                ? _data[0][col]
                : '';
            return DataColumn(
              label: widget.isSelected
                  ? SizedBox(
                      width: 120,
                      child: TextField(
                        controller: _getController(0, col),
                        onChanged: (v) => _onCellChanged(0, col, v),
                        style: AppTypography.odiaBodyMedium.copyWith(
                          fontWeight: FontWeight.w600,
                          color: t.bodyColor,
                        ),
                        decoration: const InputDecoration(
                          isDense: true,
                          border: InputBorder.none,
                          contentPadding: EdgeInsets.zero,
                        ),
                      ),
                    )
                  : Text(
                      headerText,
                      style: AppTypography.odiaBodyMedium.copyWith(
                        fontWeight: FontWeight.w600,
                        color: t.bodyColor,
                      ),
                    ),
            );
          }),
          rows: List.generate(_data.length - 1, (rowIdx) {
            final row = rowIdx + 1; // skip header
            return DataRow(
              cells: List.generate(maxCols, (col) {
                final cellText = col < _data[row].length ? _data[row][col] : '';
                return DataCell(
                  widget.isSelected
                      ? SizedBox(
                          width: 120,
                          child: TextField(
                            controller: _getController(row, col),
                            onChanged: (v) => _onCellChanged(row, col, v),
                            style: AppTypography.odiaBodyMedium.copyWith(
                              color: t.bodyColor,
                            ),
                            decoration: const InputDecoration(
                              isDense: true,
                              border: InputBorder.none,
                              contentPadding: EdgeInsets.zero,
                            ),
                          ),
                        )
                      : Text(
                          cellText,
                          style: AppTypography.odiaBodyMedium.copyWith(
                            color: t.bodyColor,
                          ),
                        ),
                );
              }),
            );
          }),
        ),
      ),
    );
  }
}

// =============================================================================
// Photo block
// =============================================================================

class _MediaBlock extends ConsumerStatefulWidget {
  final Paragraph paragraph;
  final VoidCallback? onRemove;
  final VoidCallback? onOcr;

  const _MediaBlock({
    required this.paragraph,
    this.onRemove,
    this.onOcr,
  });

  @override
  ConsumerState<_MediaBlock> createState() => _MediaBlockState();
}

class _MediaBlockState extends ConsumerState<_MediaBlock> {
  AppStrings get s => AppStrings.of(ref);
  AudioPlayer? _audioPlayer;
  bool _isPlaying = false;
  Duration _duration = Duration.zero;
  Duration _position = Duration.zero;

  Paragraph get paragraph => widget.paragraph;

  @override
  void dispose() {
    _audioPlayer?.dispose();
    super.dispose();
  }

  String _resolveUrl(String path) {
    if (path.startsWith('http')) return path;
    return '${ApiConfig.baseUrl}$path';
  }

  Future<void> _toggleAudioPlayback() async {
    final mediaPath = paragraph.mediaPath ?? '';
    if (mediaPath.isEmpty) return;

    if (_audioPlayer == null) {
      _audioPlayer = AudioPlayer();
      _audioPlayer!.onPlayerStateChanged.listen((state) {
        if (mounted) {
          setState(() => _isPlaying = state == PlayerState.playing);
        }
      });
      _audioPlayer!.onDurationChanged.listen((d) {
        if (mounted) setState(() => _duration = d);
      });
      _audioPlayer!.onPositionChanged.listen((p) {
        if (mounted) setState(() => _position = p);
      });
      _audioPlayer!.onPlayerComplete.listen((_) {
        if (mounted) setState(() {
          _isPlaying = false;
          _position = Duration.zero;
        });
      });
    }

    if (_isPlaying) {
      await _audioPlayer!.pause();
    } else {
      final url = _resolveUrl(mediaPath);
      if (_position > Duration.zero && _position < _duration) {
        await _audioPlayer!.resume();
      } else {
        await _audioPlayer!.play(UrlSource(url));
      }
    }
  }

  void _openPhotoFullScreen() {
    final mediaPath = paragraph.mediaPath ?? '';
    if (mediaPath.isEmpty) return;

    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => _FullScreenImageViewer(
          mediaPath: mediaPath,
          title: paragraph.mediaName ?? s.photo,
        ),
      ),
    );
  }

  Future<void> _openFileExternally() async {
    final mediaPath = paragraph.mediaPath ?? '';
    if (mediaPath.isEmpty) return;
    final url = _resolveUrl(mediaPath);
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  void _handleTap() {
    final type = paragraph.mediaType;
    switch (type) {
      case MediaType.audio:
        _toggleAudioPlayback();
        break;
      case MediaType.photo:
        _openPhotoFullScreen();
        break;
      case MediaType.video:
      case MediaType.document:
        _openFileExternally();
        break;
      default:
        _openFileExternally();
    }
  }

  IconData _iconForType(MediaType? type) {
    switch (type) {
      case MediaType.photo:
        return LucideIcons.image;
      case MediaType.video:
        return LucideIcons.video;
      case MediaType.audio:
        return LucideIcons.music;
      case MediaType.document:
        return LucideIcons.fileText;
      default:
        return LucideIcons.file;
    }
  }

  Color _colorForType(MediaType? type) {
    switch (type) {
      case MediaType.photo:
        return AppColors.indigo500;
      case MediaType.video:
        return AppColors.coral500;
      case MediaType.audio:
        return AppColors.teal500;
      case MediaType.document:
        return AppColors.gold600;
      default:
        return AppColors.neutral500;
    }
  }

  Color _bgForType(MediaType? type) {
    switch (type) {
      case MediaType.photo:
        return AppColors.indigo50;
      case MediaType.video:
        return AppColors.coral50;
      case MediaType.audio:
        return AppColors.teal50;
      case MediaType.document:
        return AppColors.gold50;
      default:
        return AppColors.neutral100;
    }
  }

  String _labelForType(MediaType? type) {
    switch (type) {
      case MediaType.photo:
        return s.photo;
      case MediaType.video:
        return s.video;
      case MediaType.audio:
        return s.audioLabel;
      case MediaType.document:
        return s.document;
      default:
        return s.fileLabel;
    }
  }

  String _formatDuration(Duration d) {
    final mins = d.inMinutes.remainder(60).toString().padLeft(2, '0');
    final secs = d.inSeconds.remainder(60).toString().padLeft(2, '0');
    return '$mins:$secs';
  }

  /// Build image widget supporting both server URLs and base64 data URLs.
  Widget _buildMediaImage(String mediaPath) {
    if (mediaPath.startsWith('data:')) {
      // Legacy base64 data URL
      try {
        final commaIdx = mediaPath.indexOf(',');
        if (commaIdx > 0) {
          final b64 = mediaPath.substring(commaIdx + 1);
          return Image.memory(
            base64Decode(b64),
            fit: BoxFit.cover,
            width: double.infinity,
            height: 200,
          );
        }
      } catch (_) {}
      return const SizedBox.shrink();
    }
    // Server URL (relative like /uploads/xxx.jpg or absolute http)
    final url = _resolveUrl(mediaPath);
    return CachedNetworkImage(
      imageUrl: url,
      fit: BoxFit.cover,
      width: double.infinity,
      height: 200,
      errorWidget: (_, __, ___) => Center(
        child: Icon(LucideIcons.image, size: 32, color: AppColors.vrCoral.withValues(alpha: 0.5)),
      ),
      placeholder: (_, __) => const SizedBox(
        width: double.infinity,
        height: 200,
      ),
    );
  }

  /// Build audio player inline widget with play/pause, progress bar.
  Widget _buildAudioPlayer(BuildContext context) {
    final type = paragraph.mediaType;
    final accentColor = _colorForType(type);

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: _bgForType(type),
        borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              // Play/pause button
              GestureDetector(
                onTap: _toggleAudioPlayback,
                child: Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: accentColor,
                    borderRadius: BorderRadius.circular(AppSpacing.radiusSm),
                  ),
                  child: Icon(
                    _isPlaying ? LucideIcons.pause : LucideIcons.play,
                    size: 22,
                    color: Colors.white,
                  ),
                ),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _labelForType(type),
                      style: AppTypography.odiaBodyMedium.copyWith(
                        fontWeight: FontWeight.w600,
                        color: accentColor,
                      ),
                    ),
                    if (paragraph.mediaName != null) ...[
                      const SizedBox(height: 2),
                      Text(
                        paragraph.mediaName!,
                        style: AppTypography.bodySmall.copyWith(
                          color: context.t.mutedColor,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
          // Progress bar + time
          if (_duration > Duration.zero || _isPlaying) ...[
            const SizedBox(height: AppSpacing.sm),
            SliderTheme(
              data: SliderTheme.of(context).copyWith(
                trackHeight: 3,
                thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 6),
                overlayShape: const RoundSliderOverlayShape(overlayRadius: 12),
                activeTrackColor: accentColor,
                inactiveTrackColor: accentColor.withValues(alpha: 0.2),
                thumbColor: accentColor,
              ),
              child: Slider(
                min: 0,
                max: _duration.inMilliseconds.toDouble().clamp(1, double.infinity),
                value: _position.inMilliseconds.toDouble().clamp(0, _duration.inMilliseconds.toDouble().clamp(1, double.infinity)),
                onChanged: (value) {
                  _audioPlayer?.seek(Duration(milliseconds: value.toInt()));
                },
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 4),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    _formatDuration(_position),
                    style: AppTypography.bodySmall.copyWith(
                      color: context.t.mutedColor,
                      fontSize: 11,
                    ),
                  ),
                  Text(
                    _formatDuration(_duration),
                    style: AppTypography.bodySmall.copyWith(
                      color: context.t.mutedColor,
                      fontSize: 11,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final type = paragraph.mediaType;
    final isAudio = type == MediaType.audio;
    final isImage = type == MediaType.photo;
    final mediaPath = paragraph.mediaPath ?? '';
    final isDataUrl = mediaPath.startsWith('data:');
    final isServerUrl = mediaPath.startsWith('/uploads/') || mediaPath.startsWith('http');
    final hasImage = isImage && (isDataUrl || isServerUrl);

    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.sm,
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
        child: Stack(
          children: [
            // Audio: inline player
            if (isAudio)
              _buildAudioPlayer(context)
            // Image preview for photos
            else if (hasImage)
              GestureDetector(
                onTap: _openPhotoFullScreen,
                child: Container(
                  height: 200,
                  width: double.infinity,
                  decoration: BoxDecoration(
                    color: context.t.actionChipBg,
                  ),
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      _buildMediaImage(mediaPath),
                      // Tap-to-view hint overlay
                      Positioned(
                        bottom: AppSpacing.sm,
                        left: AppSpacing.sm,
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                          decoration: BoxDecoration(
                            color: Colors.black.withValues(alpha: 0.5),
                            borderRadius: BorderRadius.circular(AppSpacing.radiusSm),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(LucideIcons.maximize2, size: 12, color: Colors.white),
                              const SizedBox(width: 4),
                              Text(
                                s.enlarge,
                                style: AppTypography.bodySmall.copyWith(
                                  color: Colors.white,
                                  fontSize: 11,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      // OCR sparkle button
                      if (widget.onOcr != null)
                        Positioned(
                          bottom: AppSpacing.sm,
                          right: AppSpacing.sm,
                          child: GestureDetector(
                            onTap: widget.onOcr,
                            child: Container(
                              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                              decoration: BoxDecoration(
                                color: const Color(0xFFFA6C38),
                                borderRadius: BorderRadius.circular(AppSpacing.radiusSm),
                                boxShadow: [
                                  BoxShadow(
                                    color: Colors.black.withValues(alpha: 0.2),
                                    blurRadius: 4,
                                    offset: const Offset(0, 2),
                                  ),
                                ],
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  const Icon(LucideIcons.sparkles, size: 14, color: Colors.white),
                                  const SizedBox(width: 4),
                                  Text(
                                    'OCR',
                                    style: AppTypography.bodySmall.copyWith(
                                      color: Colors.white,
                                      fontSize: 11,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              )
            // Other file types: styled card
            else
              GestureDetector(
                onTap: _handleTap,
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.lg,
                    vertical: AppSpacing.lg,
                  ),
                  decoration: BoxDecoration(
                    color: _bgForType(type),
                    borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
                  ),
                  child: Row(
                    children: [
                      Container(
                        width: 44,
                        height: 44,
                        decoration: BoxDecoration(
                          color: _colorForType(type).withValues(alpha: 0.1),
                          borderRadius: BorderRadius.circular(AppSpacing.radiusSm),
                        ),
                        child: Icon(
                          _iconForType(type),
                          size: 22,
                          color: _colorForType(type),
                        ),
                      ),
                      const SizedBox(width: AppSpacing.md),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              _labelForType(type),
                              style: AppTypography.odiaBodyMedium.copyWith(
                                fontWeight: FontWeight.w600,
                                color: _colorForType(type),
                              ),
                            ),
                            if (paragraph.mediaName != null) ...[
                              const SizedBox(height: 2),
                              Text(
                                paragraph.mediaName!,
                                style: AppTypography.bodySmall.copyWith(
                                  color: context.t.mutedColor,
                                ),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ],
                          ],
                        ),
                      ),
                      Icon(
                        LucideIcons.externalLink,
                        size: 16,
                        color: _colorForType(type).withValues(alpha: 0.6),
                      ),
                    ],
                  ),
                ),
              ),
            // Remove button (hidden in read-only mode)
            if (widget.onRemove != null)
              Positioned(
                top: AppSpacing.sm,
                right: AppSpacing.sm,
                child: GestureDetector(
                  onTap: widget.onRemove,
                  child: Container(
                    width: 28,
                    height: 28,
                    decoration: BoxDecoration(
                      color: Colors.black.withValues(alpha: 0.5),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(
                      LucideIcons.x,
                      size: 14,
                      color: Colors.white,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

// =============================================================================
// Full-screen image viewer
// =============================================================================

class _FullScreenImageViewer extends StatelessWidget {
  final String mediaPath;
  final String title;

  const _FullScreenImageViewer({
    required this.mediaPath,
    required this.title,
  });

  String _resolveUrl(String path) {
    if (path.startsWith('http')) return path;
    return '${ApiConfig.baseUrl}$path';
  }

  @override
  Widget build(BuildContext context) {
    Widget imageWidget;
    if (mediaPath.startsWith('data:')) {
      try {
        final commaIdx = mediaPath.indexOf(',');
        if (commaIdx > 0) {
          final b64 = mediaPath.substring(commaIdx + 1);
          imageWidget = Image.memory(
            base64Decode(b64),
            fit: BoxFit.contain,
          );
        } else {
          imageWidget = const SizedBox.shrink();
        }
      } catch (_) {
        imageWidget = const SizedBox.shrink();
      }
    } else {
      imageWidget = CachedNetworkImage(
        imageUrl: _resolveUrl(mediaPath),
        fit: BoxFit.contain,
        errorWidget: (_, __, ___) => Center(
          child: Icon(LucideIcons.imageOff, size: 48, color: Colors.white.withValues(alpha: 0.5)),
        ),
        placeholder: (_, __) => const SizedBox.shrink(),
      );
    }

    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        title: Text(
          title,
          style: AppTypography.bodyMedium.copyWith(color: Colors.white),
        ),
        leading: IconButton(
          icon: const Icon(LucideIcons.x),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: Center(
        child: InteractiveViewer(
          minScale: 0.5,
          maxScale: 4.0,
          child: imageWidget,
        ),
      ),
    );
  }
}

class _IdleBottomBar extends ConsumerWidget {
  final bool canSubmit;
  final bool isProcessing;
  final bool hasTextSelection;
  final bool isReadOnly;
  final VoidCallback onAttach;
  final VoidCallback onRecord;
  final VoidCallback onLongPressRecord;
  final VoidCallback onRewrite;
  final VoidCallback onSubmit;

  const _IdleBottomBar({
    required this.canSubmit,
    required this.isProcessing,
    required this.hasTextSelection,
    this.isReadOnly = false,
    required this.onAttach,
    required this.onRecord,
    required this.onLongPressRecord,
    required this.onRewrite,
    required this.onSubmit,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = context.t;
    final s = AppStrings.of(ref);

    // Only show AI rewrite when user has actually selected text
    final bool isRewriteMode = hasTextSelection && !isProcessing;

    return Container(
      decoration: BoxDecoration(
        color: t.cardBg,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.06),
            blurRadius: 12,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.xl,
            vertical: AppSpacing.md,
          ),
          child: Row(
            mainAxisAlignment: isReadOnly
                ? MainAxisAlignment.center
                : MainAxisAlignment.spaceEvenly,
            children: [
              // Attach media button (always visible)
              _LabeledBarButton(
                label: s.tooltipAttach,
                labelColor: t.mutedColor,
                child: Semantics(
                  label: s.tooltipAttach,
                  button: true,
                  child: GestureDetector(
                    onTap: onAttach,
                    child: Container(
                      width: 44,
                      height: 44,
                      decoration: BoxDecoration(
                        color: t.actionChipBg,
                        shape: BoxShape.circle,
                      ),
                      child: Icon(
                        LucideIcons.paperclip,
                        size: 20,
                        color: t.bodyColor,
                      ),
                    ),
                  ),
                ),
              ),

              if (!isReadOnly) ...[
                // Center button: Mic (default) or AI Rewrite (when paragraph selected)
                // Tap = transcription only. Long-press = transcription + audio file.
                _LabeledBarButton(
                  label: isRewriteMode ? s.tooltipAI : s.tooltipMic,
                  labelColor: isRewriteMode ? t.primary : t.mutedColor,
                  child: Semantics(
                    label: isRewriteMode ? s.tooltipAI : s.tooltipMic,
                    button: true,
                    child: GestureDetector(
                      onTap: isProcessing
                          ? null
                          : isRewriteMode
                              ? onRewrite
                              : onRecord,
                      onLongPress: isProcessing || isRewriteMode
                          ? null
                          : () {
                              HapticFeedback.mediumImpact();
                              onLongPressRecord();
                            },
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 250),
                        curve: Curves.easeInOut,
                        width: 44,
                        height: 44,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          gradient: isProcessing
                              ? null
                              : isRewriteMode
                                  ? null
                                  : t.primaryGradient,
                          color: isProcessing
                              ? t.dividerColor
                              : isRewriteMode
                                  ? t.aiChipBg
                                  : null,
                          border: isRewriteMode
                              ? Border.all(
                                  color: t.primary.withValues(alpha: 0.4),
                                  width: 1.5,
                                )
                              : null,
                          boxShadow: isProcessing
                              ? null
                              : [
                                  BoxShadow(
                                    color: t.primary.withValues(alpha: 0.3),
                                    blurRadius: 16,
                                    offset: const Offset(0, 4),
                                  ),
                                ],
                        ),
                        child: isProcessing
                            ? Center(
                                child: SizedBox(
                                  width: 22,
                                  height: 22,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2.5,
                                    color: t.onPrimary,
                                  ),
                                ),
                              )
                            : Icon(
                                isRewriteMode
                                    ? LucideIcons.sparkles
                                    : LucideIcons.mic,
                                color: isRewriteMode
                                    ? t.primary
                                    : t.onPrimary,
                                size: isRewriteMode ? 22 : 24,
                              ),
                      ),
                    ),
                  ),
                ),

                // Submit button
                _LabeledBarButton(
                  label: s.submit,
                  labelColor: canSubmit && !isProcessing
                      ? AppColors.teal500
                      : t.mutedColor,
                  child: Semantics(
                    label: s.submit,
                    button: true,
                    enabled: canSubmit && !isProcessing,
                    child: GestureDetector(
                      onTap: canSubmit && !isProcessing ? onSubmit : null,
                      child: Container(
                        width: 44,
                        height: 44,
                        decoration: BoxDecoration(
                          color: canSubmit && !isProcessing
                              ? AppColors.teal500
                              : t.dividerColor,
                          shape: BoxShape.circle,
                        ),
                        child: Icon(
                          LucideIcons.send,
                          size: 18,
                          color: canSubmit && !isProcessing
                              ? t.onPrimary
                              : t.mutedColor,
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// Vertical wrapper that renders a button with a small text label below it.
/// Used in the editor bottom bar so reporters can see what each icon does
/// without needing to long-press for a tooltip.
class _LabeledBarButton extends StatelessWidget {
  final Widget child;
  final String label;
  final Color labelColor;

  const _LabeledBarButton({
    required this.child,
    required this.label,
    required this.labelColor,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        child,
        const SizedBox(height: 4),
        Text(
          label,
          style: AppTypography.odiaBodySmall.copyWith(
            color: labelColor,
            fontSize: 10,
            fontWeight: FontWeight.w600,
            height: 1.1,
          ),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
      ],
    );
  }
}

// =============================================================================
// Zone 3: Bottom bar — AI instruction recording mode
// =============================================================================

class _AIInstructionBottomBar extends ConsumerWidget {
  final String transcript;
  final VoidCallback onApply;
  final VoidCallback onCancel;

  const _AIInstructionBottomBar({
    required this.transcript,
    required this.onApply,
    required this.onCancel,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = context.t;
    final s = AppStrings.of(ref);
    return Container(
      decoration: BoxDecoration(
        color: t.cardBg,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.08),
            blurRadius: 16,
            offset: const Offset(0, -4),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.base,
            vertical: AppSpacing.md,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Prompt label
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(LucideIcons.sparkles, size: 14, color: t.primary),
                  const SizedBox(width: 4),
                  Text(
                    s.aiInstructHint,
                    style: AppTypography.odiaBodySmall.copyWith(
                      color: t.mutedColor,
                    ),
                  ),
                ],
              ),
              // Live transcript
              if (transcript.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(
                    top: AppSpacing.sm,
                    left: AppSpacing.md,
                    right: AppSpacing.md,
                  ),
                  child: Text(
                    transcript,
                    style: AppTypography.odiaBodyMedium.copyWith(
                      color: t.bodyColor,
                      fontWeight: FontWeight.w600,
                    ),
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                    textAlign: TextAlign.center,
                  ),
                ),
              const SizedBox(height: AppSpacing.md),
              // Apply + Cancel row
              Row(
                children: [
                  // Cancel
                  Expanded(
                    child: OutlinedButton(
                      onPressed: onCancel,
                      style: OutlinedButton.styleFrom(
                        foregroundColor: t.mutedColor,
                        side: BorderSide(color: t.dividerColor),
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(
                          borderRadius:
                              BorderRadius.circular(AppSpacing.radiusFull),
                        ),
                      ),
                      child: Text(
                        s.cancel,
                        style: AppTypography.odiaTitleLarge.copyWith(
                          color: t.mutedColor,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.md),
                  // Apply
                  Expanded(
                    flex: 2,
                    child: ElevatedButton.icon(
                      onPressed: onApply,
                      icon: const Icon(LucideIcons.sparkles, size: 16),
                      label: Text(
                        s.apply,
                        style: AppTypography.odiaTitleLarge.copyWith(
                          color: t.onPrimary,
                        ),
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: t.primary,
                        foregroundColor: t.onPrimary,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(
                          borderRadius:
                              BorderRadius.circular(AppSpacing.radiusFull),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// =============================================================================
// Zone 3: Bottom bar — recording mode
// =============================================================================

class _RecordingBottomBar extends StatefulWidget {
  final String formattedDuration;
  final AnimationController waveformController;
  final bool isAudioSaveMode;
  final bool isNoisy;
  final String moveCloserLabel;
  final bool speakerFilterActive;
  final bool isSpeakerVerified;
  final VoidCallback onStop;

  const _RecordingBottomBar({
    required this.formattedDuration,
    required this.waveformController,
    this.isAudioSaveMode = false,
    this.isNoisy = false,
    this.moveCloserLabel = 'Move closer',
    this.speakerFilterActive = false,
    this.isSpeakerVerified = true,
    required this.onStop,
  });

  @override
  State<_RecordingBottomBar> createState() => _RecordingBottomBarState();
}

class _RecordingBottomBarState extends State<_RecordingBottomBar>
    with SingleTickerProviderStateMixin {
  late AnimationController _bounceController;
  late Animation<double> _bounceAnim;

  @override
  void initState() {
    super.initState();
    _bounceController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    );
    _bounceAnim = Tween<double>(begin: 0, end: -6).animate(
      CurvedAnimation(parent: _bounceController, curve: Curves.easeInOut),
    );
    if (widget.isNoisy) _bounceController.repeat(reverse: true);
  }

  @override
  void didUpdateWidget(covariant _RecordingBottomBar old) {
    super.didUpdateWidget(old);
    if (widget.isNoisy && !old.isNoisy) {
      _bounceController.repeat(reverse: true);
    } else if (!widget.isNoisy && old.isNoisy) {
      _bounceController.stop();
      _bounceController.reset();
    }
  }

  @override
  void dispose() {
    _bounceController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AppColors.vrCoral,          // #FA6C38
            AppColors.vrCoralMuted,     // #FC9A72
            AppColors.vrCoral,          // #FA6C38
          ],
          stops: [0.0, 0.5, 1.0],
        ),
        boxShadow: [
          BoxShadow(
            color: AppColors.vrCoral.withValues(alpha: 0.35),
            blurRadius: 20,
            offset: const Offset(0, -6),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.xl,
            vertical: AppSpacing.md,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Noise hint chip
              AnimatedSize(
                duration: const Duration(milliseconds: 300),
                curve: Curves.easeOut,
                child: widget.isNoisy
                    ? AnimatedBuilder(
                        animation: _bounceAnim,
                        builder: (context, child) => Transform.translate(
                          offset: Offset(0, _bounceAnim.value),
                          child: child,
                        ),
                        child: Padding(
                          padding: const EdgeInsets.only(bottom: 8),
                          child: Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 12,
                              vertical: 6,
                            ),
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.2),
                              borderRadius: BorderRadius.circular(16),
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                const Icon(LucideIcons.mic, size: 14, color: Colors.white),
                                const SizedBox(width: 6),
                                Text(
                                  widget.moveCloserLabel,
                                  style: const TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w600,
                                    color: Colors.white,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      )
                    : const SizedBox.shrink(),
              ),
              Row(
                children: [
                  // Timer
                  Text(
                    widget.formattedDuration,
                    style: AppTypography.titleLarge.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.w700,
                      fontFeatures: const [FontFeature.tabularFigures()],
                    ),
                  ),

                  // Audio save badge
                  if (widget.isAudioSaveMode) ...[
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 3,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.25),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: const Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(LucideIcons.music, size: 12, color: Colors.white),
                          SizedBox(width: 3),
                          Text(
                            'REC',
                            style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.w700,
                              color: Colors.white,
                              letterSpacing: 0.5,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],

                  // Speaker verification badge
                  if (widget.speakerFilterActive) ...[
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 3,
                      ),
                      decoration: BoxDecoration(
                        color: widget.isSpeakerVerified
                            ? const Color(0xFF10B981).withValues(alpha: 0.3)
                            : const Color(0xFFF59E0B).withValues(alpha: 0.3),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            widget.isSpeakerVerified
                                ? LucideIcons.shieldCheck
                                : LucideIcons.shieldOff,
                            size: 12,
                            color: Colors.white,
                          ),
                        ],
                      ),
                    ),
                  ],

                  const SizedBox(width: AppSpacing.lg),

                  // Waveform bars
                  Expanded(
                    child: _WaveformBars(controller: widget.waveformController),
                  ),

                  const SizedBox(width: AppSpacing.lg),

                  // Stop button
                  GestureDetector(
                    onTap: widget.onStop,
                    child: Container(
                      width: 48,
                      height: 48,
                      decoration: BoxDecoration(
                        color: Colors.white,
                        shape: BoxShape.circle,
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withValues(alpha: 0.15),
                            blurRadius: 8,
                            offset: const Offset(0, 2),
                          ),
                        ],
                      ),
                      child: const Icon(
                        LucideIcons.square,
                        size: 18,
                        color: AppColors.vrCoral,
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SubmitSuccessOverlay extends StatefulWidget {
  const _SubmitSuccessOverlay();

  @override
  State<_SubmitSuccessOverlay> createState() => _SubmitSuccessOverlayState();
}

class _SubmitSuccessOverlayState extends State<_SubmitSuccessOverlay>
    with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;
  late Animation<double> _scale;
  late Animation<double> _fade;
  late Animation<double> _checkProgress;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    );
    _fade = Tween<double>(begin: 0, end: 1).animate(
      CurvedAnimation(parent: _ctrl, curve: const Interval(0, 0.3)),
    );
    _scale = Tween<double>(begin: 0.3, end: 1).animate(
      CurvedAnimation(parent: _ctrl, curve: const Interval(0, 0.5, curve: Curves.elasticOut)),
    );
    _checkProgress = Tween<double>(begin: 0, end: 1).animate(
      CurvedAnimation(parent: _ctrl, curve: const Interval(0.4, 0.8, curve: Curves.easeOut)),
    );
    _ctrl.forward();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (context, _) => Material(
        color: Colors.black.withValues(alpha: _fade.value * 0.5),
        child: Center(
          child: Transform.scale(
            scale: _scale.value,
            child: Opacity(
              opacity: _fade.value,
              child: Container(
                width: 140,
                height: 140,
                decoration: BoxDecoration(
                  color: AppColors.success,
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: AppColors.success.withValues(alpha: 0.4),
                      blurRadius: 30,
                      spreadRadius: 10,
                    ),
                  ],
                ),
                child: CustomPaint(
                  painter: _CheckPainter(progress: _checkProgress.value),
                  child: const SizedBox.expand(),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _CheckPainter extends CustomPainter {
  final double progress;
  _CheckPainter({required this.progress});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.white
      ..strokeWidth = 5
      ..strokeCap = StrokeCap.round
      ..style = PaintingStyle.stroke;

    final cx = size.width / 2;
    final cy = size.height / 2;
    // Checkmark: two segments
    final p1 = Offset(cx - 22, cy + 2);
    final p2 = Offset(cx - 6, cy + 18);
    final p3 = Offset(cx + 24, cy - 16);

    final path = Path();
    if (progress <= 0.5) {
      // First segment: p1 → p2
      final t = progress / 0.5;
      path.moveTo(p1.dx, p1.dy);
      path.lineTo(p1.dx + (p2.dx - p1.dx) * t, p1.dy + (p2.dy - p1.dy) * t);
    } else {
      // Full first segment + partial second
      final t = (progress - 0.5) / 0.5;
      path.moveTo(p1.dx, p1.dy);
      path.lineTo(p2.dx, p2.dy);
      path.lineTo(p2.dx + (p3.dx - p2.dx) * t, p2.dy + (p3.dy - p2.dy) * t);
    }

    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(_CheckPainter old) => old.progress != progress;
}

class _AttachOption extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final Color bgColor;
  final String label;
  final String subtitle;
  final VoidCallback onTap;

  const _AttachOption({
    required this.icon,
    required this.iconColor,
    required this.bgColor,
    required this.label,
    required this.subtitle,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Container(
        width: 40,
        height: 40,
        decoration: BoxDecoration(
          color: bgColor,
          borderRadius: BorderRadius.circular(AppSpacing.radiusSm),
        ),
        child: Icon(icon, color: iconColor, size: 20),
      ),
      title: Text(label, style: AppTypography.odiaTitleLarge),
      subtitle: Text(subtitle, style: AppTypography.bodySmall),
      onTap: onTap,
    );
  }
}

class _AiRefineFab extends ConsumerWidget {
  final VoidCallback onTap;
  final bool isGenerating;

  const _AiRefineFab({required this.onTap, required this.isGenerating});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = AppStrings.of(ref);
    return Tooltip(
      message: s.aiRefineHint,
      child: Material(
        color: Colors.transparent,
        elevation: 0,
        child: InkWell(
          onTap: isGenerating ? null : onTap,
          borderRadius: BorderRadius.circular(28),
          child: Ink(
            decoration: BoxDecoration(
              gradient: AppGradients.electricPulse,
              borderRadius: BorderRadius.circular(28),
              boxShadow: [
                BoxShadow(
                  color: AppColors.coral500.withValues(alpha: 0.32),
                  blurRadius: 20,
                  offset: const Offset(0, 6),
                ),
              ],
            ),
            child: Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.base,
                vertical: AppSpacing.sm + 2,
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  SizedBox(
                    width: 18,
                    height: 18,
                    child: isGenerating
                        ? const CircularProgressIndicator(
                            strokeWidth: 2.4,
                            valueColor:
                                AlwaysStoppedAnimation<Color>(Colors.white),
                          )
                        : const Icon(
                            LucideIcons.sparkles,
                            size: 18,
                            color: Colors.white,
                          ),
                  ),
                  const SizedBox(width: AppSpacing.xs + 2),
                  Text(
                    isGenerating ? s.generatingStory : s.generateStory,
                    style: AppTypography.odiaBodySmall.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.2,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Spinner whose stroke picks up the AI gradient. Small, used when AI
/// Refine is actively running — keeps the same multi-colour identity
/// as the resting state.
class _GradientSpinner extends StatefulWidget {
  const _GradientSpinner();

  @override
  State<_GradientSpinner> createState() => _GradientSpinnerState();
}

class _GradientSpinnerState extends State<_GradientSpinner>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
  )..repeat();

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return RotationTransition(
      turns: _ctrl,
      child: ShaderMask(
        blendMode: BlendMode.srcIn,
        shaderCallback: (bounds) =>
            AppGradients.electricPulse.createShader(bounds),
        child: const Icon(
          LucideIcons.loader2,
          size: 16,
          color: Colors.white,
        ),
      ),
    );
  }
}

class _WaveformBars extends StatelessWidget {
  final AnimationController controller;

  const _WaveformBars({required this.controller});

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: controller,
      builder: (context, _) {
        return SizedBox(
          height: 28,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: List.generate(5, (i) {
              final phase = i * 0.4;
              final t = (controller.value * 2 * math.pi) + phase;
              final height = 8.0 + 14.0 * ((math.sin(t) + 1) / 2);

              return Padding(
                padding: const EdgeInsets.symmetric(horizontal: 2),
                child: Container(
                  width: 3,
                  height: height,
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.85),
                    borderRadius: BorderRadius.circular(1.5),
                  ),
                ),
              );
            }),
          ),
        );
      },
    );
  }
}

// =============================================================================
// Error banner
// =============================================================================

class _ErrorBanner extends StatelessWidget {
  final String message;
  final VoidCallback onDismiss;

  const _ErrorBanner({
    required this.message,
    required this.onDismiss,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.base,
        vertical: AppSpacing.md,
      ),
      color: AppColors.coral50,
      child: Row(
        children: [
          const Icon(
            LucideIcons.alertCircle,
            size: 16,
            color: AppColors.coral500,
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(
              message,
              style: AppTypography.bodySmall.copyWith(
                color: AppColors.coral600,
              ),
            ),
          ),
          GestureDetector(
            onTap: onDismiss,
            child: const Icon(
              LucideIcons.x,
              size: 16,
              color: AppColors.coral500,
            ),
          ),
        ],
      ),
    );
  }
}
