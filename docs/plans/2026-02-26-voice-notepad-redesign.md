# Voice Notepad Redesign

**Date**: 2026-02-26
**Status**: Approved
**Goal**: Radically simplify NewsFlow for 50+ non-tech field reporters in Odisha

## Core Mental Model

"Google Docs meets WhatsApp Voice Notes" — the entire create flow is a single-screen notepad. No wizard, no steps, no forms. Speak, read, submit.

## User Persona

- 50+ year old field reporter in Odisha
- Non-tech savvy, Odia-speaking
- Needs to file stories quickly from the field
- May not have all info at once — returns to add more later
- Core loop: Record → Read → Submit (with optional edit via re-speak or typing)

## Architecture: 3-Zone Single Screen

### Zone 1: Smart Header
- AI auto-generates headline from content (updates as content grows)
- AI auto-infers category + location from transcript
- Tap to manually override any field
- "Draft" badge always visible, turns "Ready" when submittable
- Three-dot menu for delete/share/language (hidden complexity)

### Zone 2: Scrollable Notepad (Core)
- Each paragraph is a discrete, tappable block
- Content from separate recording sessions appears as separate paragraphs
- "+" dividers between paragraphs for inserting photos or recording at that position
- Photos appear inline between paragraphs

**Tap-to-Edit:**
1. Tap a paragraph → it highlights (blue left border)
2. Options appear: Re-speak | Type | Delete
3. "Re-speak" opens mic → replaces JUST that paragraph
4. "Type" opens keyboard for inline editing
5. "Delete" removes the paragraph

### Zone 3: Floating Bottom Bar
**Idle state:** Photo button | Record button | Submit button
**Recording state:** Timer | Waveform | Stop button (Sarvam-style)

## Draft Lifecycle
- Auto-save on every change (no save button)
- Reporter can close app, come back later, continue editing
- Drafts appear on home screen for easy access

## Home Screen Simplification
- 2 sections: "My Drafts" and "Submitted"
- 3-item bottom nav: Home | + New | Me
- No category filters, no search bar, no complex news cards
- No dummy/mock data

## What Gets Removed
| Current | New |
|---------|-----|
| 4-step wizard | 1 screen notepad |
| 8 category chips | AI auto-tags |
| 3 priority buttons | Removed (editor decides) |
| Location text field | AI infers |
| Separate media step | Inline photo inserts |
| Review step | Notepad IS the review |
| 6 submission tabs | 2 sections: Drafts / Submitted |
| Complex home with filters | Simple drafts list |
| Dummy data | Clean, real state only |

## User Journey
1. Open app → see drafts (or empty state with "Tap to start")
2. Tap "+" → empty notepad with big mic
3. Tap mic → speak → text appears as paragraph, headline auto-generates
4. Take photo → inserts inline
5. Later: reopen draft → add more paragraphs
6. Tap wrong paragraph → re-speak to fix
7. Tap Submit → done
