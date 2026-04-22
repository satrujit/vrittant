# Select + Instruct Feature Design

## Overview
Replace the cluttered multi-button AI editing UX with a single "Select + Instruct" pattern: user selects text, taps one button, speaks what they want done, AI does it.

## User Flow
1. Double-tap paragraph → inline edit mode
2. Select text → floating button appears: mic+sparkle "ନିର୍ଦ୍ଦେଶ ଦିଅନ୍ତୁ"
3. Tap → mic records spoken instruction via existing STT
4. Tap stop → STT transcript + selected text sent to Sarvam LLM
5. Purple shimmer while processing → result replaces selected portion

## Changes

### Remove
- Floating purple "AI ସୁଧାରନ୍ତୁ" button (always visible during inline edit)
- "✦ AI ସୁଧାରନ୍ତୁ" from native context menu

### Modify
- Speech-edit button → instruct button with sparkle icon, label "ନିର୍ଦ୍ଦେଶ ଦିଅନ୍ତୁ"
- Recording panel label → "ନିର୍ଦ୍ଦେଶ କୁହନ୍ତୁ..." and stop button → "ପ୍ରୟୋଗ କରନ୍ତୁ"
- `_stopSpeechEdit` → routes transcript through LLM instead of direct replacement

### Add
- `instructEditWithAI(index, selectedText, instruction)` in provider

### Keep
- Action chip "AI ସୁଧାରନ୍ତୁ" for one-tap whole-paragraph improve
- All other action chips unchanged

## Files
- `notepad_screen.dart` — UI changes
- `create_news_provider.dart` — new provider method
