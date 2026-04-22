# Voice Notepad Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the 4-step create-news wizard with a single-screen voice notepad, simplify home screen to drafts+submitted, reduce bottom nav to 3 items, remove all mock data.

**Architecture:** Paragraph-based state model where each recording session creates a discrete paragraph block. Inline photos inserted between paragraphs. AI auto-generates headline/category/location from content. Auto-save as draft on every change.

**Tech Stack:** Flutter 3.41, Riverpod 3.x, GoRouter, Sarvam AI (streaming STT + LLM), dart:js_interop for web audio

---

### Task 1: Rework State Model — Paragraph-Based Content

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/lib/features/create_news/providers/create_news_provider.dart`

**Step 1: Define Paragraph model and new NotepadState**

Replace `CreateNewsState` with a paragraph-based model:

```dart
/// A single content block in the notepad.
class Paragraph {
  final String id;
  final String text;
  final String? photoPath; // null = text paragraph, non-null = photo block
  final DateTime createdAt;

  const Paragraph({
    required this.id,
    this.text = '',
    this.photoPath,
    DateTime? createdAt,
  }) : createdAt = createdAt ?? const _Now();

  Paragraph copyWith({String? text, String? photoPath}) =>
      Paragraph(id: id, text: text ?? this.text, photoPath: photoPath ?? this.photoPath, createdAt: createdAt);
}

class NotepadState {
  final String headline;           // AI auto-generated, editable
  final String? category;          // AI auto-inferred
  final String? location;          // AI auto-inferred
  final List<Paragraph> paragraphs;
  final bool isRecording;
  final String liveTranscript;     // current recording session
  final Duration recordingDuration;
  final int? editingParagraphIndex; // which paragraph is selected for edit
  final int? insertAtIndex;        // where to insert next recording (null = end)
  final bool isGeneratingTitle;
  final bool isProcessing;         // any AI operation
  final String? error;
}
```

Remove: `currentStep`, `transcribedText`, `body`, `priority`, `translatedEnglish`, `rephrasedOdia`, `audioBase64`, `isTranslating`, `isRephrasing`, `isSpeaking`, `transcribedOdia`.

**Step 2: Rework CreateNewsNotifier**

Key method changes:
- `toggleRecording()` → on STOP: creates new `Paragraph` from `liveTranscript`, inserts at `insertAtIndex` (or appends). Auto-generates headline. Auto-infers category/location.
- `reRecordParagraph(int index)` → sets `editingParagraphIndex`, starts recording. On stop: replaces that paragraph's text.
- `deleteParagraph(int index)` → removes paragraph from list.
- `updateParagraphText(int index, String text)` → inline text edit.
- `insertPhoto(int atIndex, String path)` → inserts photo Paragraph.
- `removePhoto(int index)` → removes photo paragraph.
- Remove: `nextStep/prevStep`, `translateToEnglish`, `rephraseWithAI`, `speakText`, `setCategory/setPriority/setLocation`.
- Keep: `_generateTitleFromTranscript` (runs on full body text).
- Add: `_autoInferMetadata(String fullText)` → uses Sarvam LLM to extract category + location.

**Step 3: Add body getter**

```dart
String get fullBodyText => paragraphs
    .where((p) => p.photoPath == null)
    .map((p) => p.text)
    .join('\n\n');
```

**Step 4: Commit**

```bash
git add lib/features/create_news/providers/create_news_provider.dart
git commit -m "feat: rework state model to paragraph-based notepad"
```

---

### Task 2: Build Notepad Screen (replaces CreateNewsScreen + all step screens)

**Files:**
- Create: `/Users/admin/Desktop/newsflow/lib/features/create_news/screens/notepad_screen.dart`
- Delete references to: `step_voice.dart`, `step_details.dart`, `step_media.dart`, `step_review.dart`

**Step 1: Build the 3-zone layout**

```dart
class NotepadScreen extends ConsumerStatefulWidget { ... }

// Zone 1: _NotepadHeader — back button, draft badge, headline, category/location chips
// Zone 2: Expanded → notepad body (paragraphs + dividers + inline photos)
// Zone 3: _BottomBar — camera | record | submit (or recording bar when active)
```

Reuse components from the mockup file (`notepad_mockup.dart`) but make them functional:
- `_ParagraphBlock` → GestureDetector onTap sets `editingParagraphIndex`
- `_InsertDivider` → onTap shows options (record here / add photo)
- `_EditActionChips` → appear below selected paragraph (re-speak, type, delete)
- `_RecordingBar` → reuse from step_voice.dart (timer + waveform + stop)
- `_BottomBarIdle` → camera, record, submit buttons wired to notifier

**Step 2: Wire recording flow**

- Tap record → `notifier.toggleRecording()` → live transcript appears as ghost paragraph at bottom
- Stop → ghost paragraph becomes real paragraph, appended to list
- Tap "+" divider → record → new paragraph inserted at that position

**Step 3: Wire tap-to-edit flow**

- Tap paragraph → `notifier.selectParagraph(index)`
- Edit chips appear: Re-speak | Type | Delete
- Re-speak → `notifier.reRecordParagraph(index)` → recording replaces that paragraph
- Type → show inline TextField for that paragraph
- Delete → `notifier.deleteParagraph(index)`

**Step 4: Wire photo insert**

- Tap camera in bottom bar → add photo at end
- Tap "+" divider → "Photo" option → add photo at that position
- For now: use file picker or mock filename (same as current step_media)

**Step 5: Commit**

```bash
git add lib/features/create_news/screens/notepad_screen.dart
git commit -m "feat: build single-screen voice notepad"
```

---

### Task 3: Simplify Home Screen

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/lib/features/home/screens/home_screen.dart`

**Step 1: Replace entire home screen**

Remove: gradient header, search bar, category chips, mock articles, NewsCard usage.

New layout (from mockup):
- Simple white header: "NewsFlow" logo + notification bell
- "My Drafts" section with draft cards
- "Submitted" section with submitted cards
- Empty state: big mic icon + "Tap to start a story"

For now, drafts/submitted are empty lists (no mock data). We'll wire real data when we add persistence.

**Step 2: Commit**

```bash
git add lib/features/home/screens/home_screen.dart
git commit -m "feat: simplify home screen to drafts + submitted"
```

---

### Task 4: Simplify Bottom Nav to 3 Items

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/lib/core/widgets/app_bottom_nav.dart`
- Modify: `/Users/admin/Desktop/newsflow/lib/core/router/app_router.dart`

**Step 1: Update AppShell bottom nav**

Reduce to 3 items: Home | + New (circle button) | Me (profile).
Remove the Submissions nav item and the empty Expanded spacer.

**Step 2: Update router**

- Remove `/submissions` route
- Remove `/mockup` route
- Change `/create` to point to `NotepadScreen` instead of `CreateNewsScreen`

**Step 3: Commit**

```bash
git add lib/core/widgets/app_bottom_nav.dart lib/core/router/app_router.dart
git commit -m "feat: simplify bottom nav to 3 items, update routes"
```

---

### Task 5: Clean Up — Remove Old Files and Mock Data

**Files:**
- Delete: `/Users/admin/Desktop/newsflow/lib/features/create_news/screens/create_news_screen.dart`
- Delete: `/Users/admin/Desktop/newsflow/lib/features/create_news/screens/step_details.dart`
- Delete: `/Users/admin/Desktop/newsflow/lib/features/create_news/screens/step_media.dart`
- Delete: `/Users/admin/Desktop/newsflow/lib/features/create_news/screens/step_review.dart`
- Delete: `/Users/admin/Desktop/newsflow/lib/features/mockups/` (entire directory)
- Delete: `/Users/admin/Desktop/newsflow/lib/features/submissions/` (merged into home)
- Clean up any unused imports/widgets (news_card.dart, category_chip.dart if no longer used)

**Step 1: Delete old files**

```bash
rm lib/features/create_news/screens/create_news_screen.dart
rm lib/features/create_news/screens/step_details.dart
rm lib/features/create_news/screens/step_media.dart
rm lib/features/create_news/screens/step_review.dart
rm -rf lib/features/mockups/
```

**Step 2: Fix any broken imports across the codebase**

Grep for imports referencing deleted files and fix them.

**Step 3: Commit**

```bash
git add -A
git commit -m "chore: remove old wizard screens, mockups, and mock data"
```

---

### Task 6: Add New App Strings

**Files:**
- Modify: `/Users/admin/Desktop/newsflow/lib/core/l10n/app_strings.dart`

Add Odia+English strings for:
- `draft` / `ready` (badge labels)
- `myDrafts` / `submitted` (home sections)
- `reSpeak` / `typeEdit` / `deleteParagraph`
- `addPhotoHere` / `recordHere`
- `untitledDraft`
- `paragraphCount` / `photoCount`
- `submit` (for notepad submit button)
- Remove unused strings from old wizard flow

**Step 1: Add strings, commit**

---

### Task 7: Build, Test, Verify

**Step 1: Run Flutter build**

```bash
cd /Users/admin/Desktop/newsflow && flutter build web
```

Fix any compilation errors.

**Step 2: Run dev server and verify in Chrome**

- Home screen shows empty drafts + submitted
- Tap "+" → notepad opens with empty state + mic
- Record → live transcript → paragraph appears
- Tap paragraph → edit options appear
- Re-speak → replaces paragraph
- Tap "+" divider → record inserts at position
- Submit button enabled when content exists

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: voice notepad redesign complete"
```
