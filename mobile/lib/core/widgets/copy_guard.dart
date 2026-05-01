import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';

/// Builds a `contextMenuBuilder` for [TextField] / [SelectableText] /
/// [EditableText] that intercepts the Copy and Cut menu items: when
/// the selection is longer than [wordLimit] words, the clipboard is
/// silently rewritten to "<orgName> Confidential" instead of the
/// actual selected text.
///
/// Threat model
/// ------------
/// Reporters were dictating internal stories into Vrittant, then
/// long-pressing the body, "Select All" → "Copy", and pasting the
/// polished article into WhatsApp / Telegram before the editor's
/// review. This is a soft deterrent against that specific abuse
/// path. It does NOT stop:
///
///   - screenshots (the OS owns those, no app-level prevention)
///   - chunked copies of ≤ [wordLimit] words at a time
///   - external OCR of the screen
///   - the OS share-sheet path (fires a different intent — flagged
///     as a follow-up; we'd guard ShareTextIntent the same way)
///
/// What it DOES stop is the easy "select all → paste" exfiltration,
/// which is by far the most common path.
///
/// Coverage
/// --------
/// Both Copy and Cut are guarded. Cut also performs the deletion of
/// the selected text from the editor (so the cut UX still works) —
/// only the clipboard payload is replaced. Paste is not guarded
/// (it's inbound, not a leak).
///
/// Hardware-keyboard `Cmd/Ctrl+C` follows a different code path
/// (CopySelectionTextIntent dispatched directly to the EditableText
/// without going through the toolbar). On the mobile devices we ship
/// to, that's a vanishingly rare path; not worth adding intent-level
/// override complexity for now. If we ship on iPad with hardware
/// keyboards we'll revisit.
///
/// Usage:
///
/// ```dart
/// TextField(
///   contextMenuBuilder: buildCopyGuardContextMenu(orgName: 'Pragativadi'),
///   ...
/// )
/// ```
EditableTextContextMenuBuilder buildCopyGuardContextMenu({
  required String orgName,
  int wordLimit = 30,
}) {
  return (BuildContext context, EditableTextState editableState) {
    final patched = editableState.contextMenuButtonItems.map((item) {
      switch (item.type) {
        case ContextMenuButtonType.copy:
          return ContextMenuButtonItem(
            type: ContextMenuButtonType.copy,
            onPressed: () => _guardedCopy(
              editableState: editableState,
              orgName: orgName,
              wordLimit: wordLimit,
            ),
          );
        case ContextMenuButtonType.cut:
          return ContextMenuButtonItem(
            type: ContextMenuButtonType.cut,
            onPressed: () => _guardedCut(
              editableState: editableState,
              orgName: orgName,
              wordLimit: wordLimit,
            ),
          );
        // selectAll / paste / lookUp / searchWeb / share / etc.: leave
        // the framework's default item in place. Selection-changing
        // items don't leak content; share is a known gap (see doc).
        default:
          return item;
      }
    }).toList(growable: false);

    return AdaptiveTextSelectionToolbar.buttonItems(
      anchors: editableState.contextMenuAnchors,
      buttonItems: patched,
    );
  };
}

void _guardedCopy({
  required EditableTextState editableState,
  required String orgName,
  required int wordLimit,
}) {
  final value = editableState.textEditingValue;
  final selected = value.selection.textInside(value.text);
  final wordCount = _countWords(selected);
  final clipboardText = wordCount > wordLimit
      ? _confidentialMessage(orgName)
      : selected;
  Clipboard.setData(ClipboardData(text: clipboardText));
  editableState.hideToolbar(false);
}

void _guardedCut({
  required EditableTextState editableState,
  required String orgName,
  required int wordLimit,
}) {
  final value = editableState.textEditingValue;
  final selection = value.selection;
  if (!selection.isValid || selection.isCollapsed) return;

  final selected = selection.textInside(value.text);
  final wordCount = _countWords(selected);
  final clipboardText = wordCount > wordLimit
      ? _confidentialMessage(orgName)
      : selected;
  Clipboard.setData(ClipboardData(text: clipboardText));

  // Cut still removes the selected text from the editor — only the
  // clipboard payload is swapped. Reporters can't sneak around the
  // guard by cutting (which would otherwise leave them with the
  // text in clipboard AND deletion already done).
  final newText = value.text.replaceRange(selection.start, selection.end, '');
  editableState.userUpdateTextEditingValue(
    TextEditingValue(
      text: newText,
      selection: TextSelection.collapsed(offset: selection.start),
    ),
    SelectionChangedCause.toolbar,
  );
  editableState.hideToolbar(false);
}

int _countWords(String text) {
  final trimmed = text.trim();
  if (trimmed.isEmpty) return 0;
  return trimmed.split(RegExp(r'\s+')).where((w) => w.isNotEmpty).length;
}

String _confidentialMessage(String orgName) {
  // Trimmed defensively — an org name with stray whitespace would
  // produce "  Confidential" which looks broken when pasted.
  final cleaned = orgName.trim().isEmpty ? 'Vrittant' : orgName.trim();
  return '$cleaned Confidential';
}
