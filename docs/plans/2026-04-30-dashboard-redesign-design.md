# Dashboard Redesign — Linear-with-color

**Date:** 2026-04-30
**Scope:** `reviewer-panel/src/pages/DashboardPage.jsx` only.
**Rollback anchor:** Git tag `pre-dashboard-redesign-2026-04-30`.
**Ship target:** Direct replacement on develop → main → prod (no V2 toggle).

## Why

The current Dashboard is functional but visually noisy: hard borders on every cell, three large stat cards eating vertical space, status pills competing with category chips for attention, and no real hover/peek affordance for triage. Reviewers process the queue all day — every visual or behavioural friction point gets paid for many times per shift.

The user asked for a "Linear-type but a bit more colourful" aesthetic with both visual excellence *and* a productivity jump. This redesign delivers both in one ship.

## Aesthetic direction

**Linear's restraint, with semantic colour earning its place.**

- Page chrome calms down. Three large stat cards collapse into one inline strip ("12 pending · 38 reviewed today · 1.2k published") in the page header.
- Filter bar becomes one row of segmented chips, not stacked dropdowns.
- Table rows lose their hard borders. Hairline `rgba(0,0,0,0.04)` separators only — the *row* is the visual unit, not the cell.
- 52px row height by default (compact 40px, cozy 68px via density toggle).
- Status pills get real semantic colour: submitted=indigo, approved=emerald, rejected=rose, flagged=amber, published=violet. Soft tinted bg + saturated text, never loud.
- Category becomes a small dot+label, not a chip — until hover, then it lights up.
- The brand coral `#FA6C38` is reserved for: the active row highlight, the pending count, the keyboard-focused row outline. Nothing else.

## Behaviours (productivity wins)

1. **Hover-peek (400 ms delay)** — hover any row → floating card slides in from the right showing the first paragraph + first image. Reviewers triage without clicks.
2. **Inline status change** — click the status pill → small dropdown right there. No page jump for one-status flips.
3. **Live arrivals** — the page already polls; new stories now fade in at the top with a 2-second coral highlight that decays. The queue feels alive.
4. **Density toggle** — top-right, persisted to localStorage. Compact 40 / Comfortable 52 / Cozy 68.
5. **Keyboard navigation** — `↑↓` row, `Enter` open, `J/K` Vim-style alternate, `S` cycle status on focused row.

## Components

New under `reviewer-panel/src/components/dashboard/` (purpose-specific, not yet a generic primitive):

- `StatStrip.jsx` — inline 3-stat header
- `FilterBar.jsx` — segmented status / category / search row
- `ReviewQueueTable.jsx` — the new table body with rows + columns
- `RowHoverPeek.jsx` — floating preview card
- `InlineStatusPill.jsx` — clickable pill + dropdown
- `DensityToggle.jsx` — top-right control
- `LiveRowHighlight.jsx` — coral-decay highlight overlay (CSS animation)

The `useReviewQueue` data hook already exists (polling the same endpoint as today). No backend changes.

## Columns (unchanged from today)

Story · Reporter & Subject · Submission Time · Category · Status · Action

User confirmed columns stay the same; this is purely a visual + behavioural rewrite.

## Risks & reversibility

- **No V2 toggle.** Direct replacement on prod.
- **Rollback path:** if the redesign tests poorly, run `git reset --hard pre-dashboard-redesign-2026-04-30` on develop + main, then force-push. The tag captures every prior commit through 2026-04-30.
- **Per-user preference for density** persists in localStorage — defaults to "Comfortable" so existing users see something close to today's height.
- **No data migration, no backend changes** — pure frontend swap. Risk surface is small.

## Out of scope

- All Stories, Reporters, BucketsList tables (a follow-up after Dashboard lands).
- New columns or backend filters.
- Mobile breakpoints below 640 px (the panel is desktop-first; existing `max-sm:` rules will continue to work but no extra polish for narrow screens).

## Success criteria

- A reviewer's eye lands on the row content (not the borders) within the first second.
- Triaging a single story (peek → inline status flip) takes one hover + one click instead of click → page → click → back.
- The page remains performant at 100+ rows (no observable jank from the new motion).
