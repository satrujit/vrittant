/// Attaches Latin → Odia transliteration to a [TextEditingController].
///
/// On each text change, detects when the user has just committed a
/// word (typed a space, newline, period, comma, etc.) after a Latin-
/// alphabet sequence and asynchronously replaces the just-typed Latin
/// word with its top Odia candidate from [TransliterationService].
///
/// Why a controller listener instead of a custom TextField widget:
/// the notepad has many TextFields (headline, body paragraphs, inline
/// edit, table cells) and they're already wired to project-specific
/// styling, focus management, autocomplete, etc. Attaching at the
/// controller level avoids re-implementing that surface and keeps the
/// integration site to one line per call site.
///
/// iOS-specific bits embedded in [_replaceWord]:
///   - `composing: TextRange.empty` — clears the IME composition
///     state so iOS' QuickType engine doesn't fight our replacement.
///   - The replacement is a single atomic [TextEditingValue] update —
///     iOS handles atomic updates cleanly even mid-composition.
///   - The TextField itself must be configured with
///     `autocorrect: false, enableSuggestions: false` (call sites do
///     this).
///
/// Race-safety: if the user keeps typing while an API call is in
/// flight, the response checks the controller's current text and
/// only replaces if the original Latin word is still where it was
/// when the call started. Otherwise the response is dropped (a more
/// recent edit has already moved past it).

import 'package:flutter/widgets.dart';

import 'transliteration_service.dart';

/// Word-boundary characters that trigger a transliteration attempt
/// when typed. Mirror of what most input methods treat as a word
/// terminator. Newline included for paragraph breaks.
const _kBoundaryChars = {' ', '\n', '\t', '.', ',', ';', ':', '!', '?'};

/// Maximum distance we'll look back from the cursor to find the
/// boundary that just got typed. Protects against pathological
/// typing patterns where `onChanged` fires for a paste etc.
const _kMaxBoundaryLookback = 64;

/// Attach transliteration to [controller]. Returns a `void Function()`
/// that the caller MUST invoke when the controller is disposed (or
/// when transliteration should be detached) to remove the listener.
///
/// Idempotent: attaching twice is a no-op (the second call returns the
/// detacher of the first).
VoidCallback attachTransliteration(TextEditingController controller) {
  // Use the controller hashCode + a per-controller flag stored on the
  // listener closure to avoid double-attaching.
  if (_attachedControllers.contains(controller)) {
    return _detachers[controller]!;
  }

  String previousText = controller.text;
  bool inFlightReplacement = false;

  void listener() {
    final next = controller.text;
    final cursor = controller.selection.baseOffset;
    final prev = previousText;
    previousText = next;

    if (inFlightReplacement) return;
    if (cursor < 0) return;
    if (next.length <= prev.length) return; // deletion, not a typed char

    // The just-typed character is at `cursor - 1` (assuming a forward
    // cursor advance, which is the only case `onChanged` reaches us
    // with text length increased by 1+). Be defensive and clamp.
    final inserted = _justInsertedSegment(prev, next, cursor);
    if (inserted == null || inserted.isEmpty) return;

    // Only fire on the LAST character if it's a boundary. If the user
    // pasted "namaskar bhai", we don't want to transliterate either
    // word here — paste is a single composite event and the user
    // didn't trigger our gesture.
    final lastChar = inserted[inserted.length - 1];
    if (!_kBoundaryChars.contains(lastChar)) return;
    // Skip if the inserted segment is more than one char (paste case)
    // — only single-char typed boundaries trigger transliteration.
    if (inserted.length > 1) return;

    // Find the Latin word that just got terminated by this boundary.
    final boundaryIndex = cursor - 1; // index of the space/period/etc
    final wordEnd = boundaryIndex; // exclusive
    final wordStart = _findWordStart(next, wordEnd);
    if (wordStart >= wordEnd) {
      // No Latin word before the boundary — but if the user typed a
      // period after Odia text, convert it to purna chheda (।).
      if (lastChar == '.') {
        _replacePeriodWithDanda(controller, boundaryIndex);
        previousText = controller.text;
      }
      return;
    }
    final word = next.substring(wordStart, wordEnd);

    // Fire the transliteration. We capture wordStart/wordEnd at this
    // point in time; when the API responds, we re-validate that the
    // controller still has this exact word at this exact position
    // before replacing.
    inFlightReplacement = true;
    () async {
      String? translated;
      try {
        translated = await TransliterationService.instance.transliterate(word);
      } catch (_) {
        translated = null;
      }
      if (translated == null || translated.isEmpty) {
        // No transliteration, but still convert period → purna chheda
        if (lastChar == '.') {
          _replacePeriodWithDanda(controller, boundaryIndex);
          previousText = controller.text;
        }
        inFlightReplacement = false;
        return;
      }
      _replaceWord(
        controller,
        wordStart: wordStart,
        wordEnd: wordEnd,
        original: word,
        replacement: translated,
      );
      // After transliteration, convert the period to purna chheda (।)
      // if that was the boundary character.
      if (lastChar == '.') {
        _replacePeriodWithDanda(controller, wordStart + translated.length);
      }
      // previousText must be updated to the new text so our next
      // listener invocation doesn't re-detect the same change as a
      // user-typed event.
      previousText = controller.text;
      inFlightReplacement = false;
    }();
  }

  controller.addListener(listener);
  _attachedControllers.add(controller);
  detacher() {
    if (!_attachedControllers.contains(controller)) return;
    controller.removeListener(listener);
    _attachedControllers.remove(controller);
    _detachers.remove(controller);
  }
  _detachers[controller] = detacher;
  return detacher;
}

/// Replace [original] in [controller] (located at
/// [wordStart]..[wordEnd]) with [replacement]. Re-validates the
/// position before writing — if the user has typed past the original
/// word in the time the API took to respond, drops the replacement
/// rather than corrupting the text.
void _replaceWord(
  TextEditingController controller, {
  required int wordStart,
  required int wordEnd,
  required String original,
  required String replacement,
}) {
  final current = controller.text;
  // Position re-validation
  if (wordEnd >= current.length) return;
  if (wordStart < 0) return;
  if (current.substring(wordStart, wordEnd) != original) return;

  // The boundary character (space / period / newline / …) sits at
  // index `wordEnd` of the current text. We replace [wordStart,
  // wordEnd+1) AND embed the boundary char back into the replacement
  // payload — so the boundary survives even if the IME drops the
  // trailing char during an atomic mid-frame `TextEditingValue`
  // update on iOS (the symptom reporters saw: "space gets
  // eliminated after the word converts to Odia").
  final boundaryChar = current.substring(wordEnd, wordEnd + 1);
  final replacementWithBoundary = '$replacement$boundaryChar';
  final newText = current.replaceRange(
    wordStart,
    wordEnd + 1,
    replacementWithBoundary,
  );

  // Cursor shift. Old text had `original.length + 1` chars in the
  // replaced range (word + boundary); new text has
  // `replacementWithBoundary.length`. Anything to the right of
  // wordEnd+1 shifts by the difference.
  final delta = replacementWithBoundary.length - (original.length + 1);
  final oldCursor = controller.selection.baseOffset;
  final newCursor = oldCursor <= wordEnd
      ? oldCursor // user moved cursor backwards inside the original word — keep it where it was
      : oldCursor + delta;

  controller.value = TextEditingValue(
    text: newText,
    selection: TextSelection.collapsed(offset: newCursor.clamp(0, newText.length)),
    // Critical for iOS: clear IME composition state so QuickType
    // doesn't try to "correct" the just-inserted Odia text.
    composing: TextRange.empty,
  );
}

/// Walks backwards from [end] (exclusive) to find the start of a
/// contiguous Latin-alphabet run. Stops at any non-Latin character.
int _findWordStart(String text, int end) {
  int i = end;
  final lookbackLimit = (end - _kMaxBoundaryLookback).clamp(0, end);
  while (i > lookbackLimit) {
    final c = text.codeUnitAt(i - 1);
    final isLatin = (c >= 0x41 && c <= 0x5A) || (c >= 0x61 && c <= 0x7A) ||
        c == 0x27; // apostrophe (e.g. "don't")
    if (!isLatin) break;
    i -= 1;
  }
  return i;
}

/// Returns the substring that was inserted when [prev] became [next],
/// assuming the change was a forward insertion at the cursor. Returns
/// `null` if the change doesn't look like a clean insertion (could be
/// a selection replacement, a delete, etc).
String? _justInsertedSegment(String prev, String next, int cursor) {
  final insertLen = next.length - prev.length;
  if (insertLen <= 0) return null;
  final insertEnd = cursor;
  final insertStart = cursor - insertLen;
  if (insertStart < 0 || insertEnd > next.length) return null;
  // Verify the surrounding context matches the previous text.
  final prefix = next.substring(0, insertStart);
  final suffix = next.substring(insertEnd);
  if (prefix.length + suffix.length != prev.length) return null;
  if (!prev.startsWith(prefix)) return null;
  if (!prev.endsWith(suffix)) return null;
  return next.substring(insertStart, insertEnd);
}

/// Replace the period at [index] with Odia purna chheda (।).
/// Preserves cursor position and clears IME composition.
void _replacePeriodWithDanda(TextEditingController controller, int index) {
  final text = controller.text;
  if (index < 0 || index >= text.length) return;
  if (text[index] != '.') return;
  final newText = text.replaceRange(index, index + 1, '।');
  final oldCursor = controller.selection.baseOffset;
  controller.value = TextEditingValue(
    text: newText,
    selection: TextSelection.collapsed(
      offset: oldCursor.clamp(0, newText.length),
    ),
    composing: TextRange.empty,
  );
}

// Module-level state to keep `attachTransliteration` idempotent.
final Set<TextEditingController> _attachedControllers = <TextEditingController>{};
final Map<TextEditingController, VoidCallback> _detachers = <TextEditingController, VoidCallback>{};
