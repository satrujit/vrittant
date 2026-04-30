# Dashboard Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace `reviewer-panel/src/pages/DashboardPage.jsx` with a Linear-with-color review queue that adds hover-peek, inline status change, live row arrival, density toggle, and keyboard navigation.

**Architecture:** Pure frontend swap. New purpose-specific components live under `reviewer-panel/src/components/dashboard/`. The existing data hook (polling `fetchStories` every 30 s) is kept; only the rendering layer changes. No backend or API contract changes.

**Tech Stack:** React 18 + Vite, shadcn/ui (the new shadcn primitives we already have: Button, Popover, Tabs), Tailwind 4, Lucide icons, Vitest + @testing-library/react for component tests (already wired). Coral primary `#FA6C38` reserved for the brand accent. The panel's existing i18n hook (`useI18n`) is used for all visible strings.

**Reference docs:**
- Design: `docs/plans/2026-04-30-dashboard-redesign-design.md`
- Rollback anchor (git tag): `pre-dashboard-redesign-2026-04-30`

**Working repo:** `/Users/admin/Desktop/newsflow-api/` on branch `develop`.

---

## Discipline

- One component per task. Build → test the testable bits → commit.
- "Testable bits" = pure functions, hooks with state, behaviour that can be exercised without rendering the whole page (status pill cycle, density toggle persistence, keyboard mapper). Visual layout is verified on the UAT deploy.
- No file is left without `npx vite build` passing for the panel before commit.
- Commit messages match repo style: `feat(panel): …`, `test(panel): …`.

## Pre-flight

### Task 0: Confirm rollback tag and clean working tree

**Step 0.1: Verify the tag exists locally and on the remote**

Run:
```bash
cd /Users/admin/Desktop/newsflow-api
git tag -l 'pre-dashboard-redesign-2026-04-30'
git ls-remote --tags origin pre-dashboard-redesign-2026-04-30
```
Expected: tag listed in both. If missing, abort and re-tag the commit before this plan was written (`c0c6322`).

**Step 0.2: Confirm the working tree is clean**

Run: `git status -s`
Expected: empty output (or only untracked `uploads/`).

**Step 0.3: Run the existing panel test suite as a baseline**

Run: `cd reviewer-panel && npx vitest run`
Expected: `Test Files 6 passed (6) | Tests 29 passed (29)`. Save this number — it must not regress.

---

## Task 1: `useDensityPreference` hook

**Files:**
- Create: `reviewer-panel/src/hooks/useDensityPreference.js`
- Test: `reviewer-panel/src/test/dashboard/useDensityPreference.test.jsx`

The density toggle persists to localStorage. Tests are easy because the surface is just `(value, setValue)` keyed by a string.

**Step 1.1: Write the failing tests**

Create `reviewer-panel/src/test/dashboard/useDensityPreference.test.jsx`:

```javascript
import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useDensityPreference, DENSITIES } from '../../hooks/useDensityPreference';

describe('useDensityPreference', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('defaults to "comfortable"', () => {
    const { result } = renderHook(() => useDensityPreference());
    expect(result.current[0]).toBe('comfortable');
  });

  it('reads persisted value from localStorage', () => {
    localStorage.setItem('vr_dashboard_density', 'compact');
    const { result } = renderHook(() => useDensityPreference());
    expect(result.current[0]).toBe('compact');
  });

  it('writes new value to localStorage', () => {
    const { result } = renderHook(() => useDensityPreference());
    act(() => result.current[1]('cozy'));
    expect(result.current[0]).toBe('cozy');
    expect(localStorage.getItem('vr_dashboard_density')).toBe('cozy');
  });

  it('rejects unknown values silently and keeps current', () => {
    const { result } = renderHook(() => useDensityPreference());
    act(() => result.current[1]('huge'));
    expect(result.current[0]).toBe('comfortable');
  });

  it('exports a DENSITIES record with row-height pixels', () => {
    expect(DENSITIES.compact.rowHeight).toBe(40);
    expect(DENSITIES.comfortable.rowHeight).toBe(52);
    expect(DENSITIES.cozy.rowHeight).toBe(68);
  });
});
```

**Step 1.2: Run the tests to verify they fail**

Run: `cd reviewer-panel && npx vitest run src/test/dashboard/useDensityPreference.test.jsx`
Expected: 5 failures (file not yet created → import error).

**Step 1.3: Implement `useDensityPreference.js`**

```javascript
import { useCallback, useState } from 'react';

export const DENSITIES = {
  compact:     { label: 'Compact',     rowHeight: 40 },
  comfortable: { label: 'Comfortable', rowHeight: 52 },
  cozy:        { label: 'Cozy',        rowHeight: 68 },
};

const STORAGE_KEY = 'vr_dashboard_density';

function readInitial() {
  if (typeof window === 'undefined') return 'comfortable';
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return DENSITIES[stored] ? stored : 'comfortable';
}

export function useDensityPreference() {
  const [value, setValue] = useState(readInitial);

  const update = useCallback((next) => {
    if (!DENSITIES[next]) return;
    setValue(next);
    window.localStorage.setItem(STORAGE_KEY, next);
  }, []);

  return [value, update];
}
```

**Step 1.4: Run the tests to verify they pass**

Run: `cd reviewer-panel && npx vitest run src/test/dashboard/useDensityPreference.test.jsx`
Expected: 5 passing.

**Step 1.5: Commit**

```bash
git add reviewer-panel/src/hooks/useDensityPreference.js \
        reviewer-panel/src/test/dashboard/useDensityPreference.test.jsx
git commit -m "feat(panel): density preference hook with localStorage persistence"
```

---

## Task 2: `cycleStatus` helper + `InlineStatusPill` component

**Files:**
- Create: `reviewer-panel/src/components/dashboard/inlineStatus.js` (pure helpers)
- Create: `reviewer-panel/src/components/dashboard/InlineStatusPill.jsx`
- Test: `reviewer-panel/src/test/dashboard/inlineStatus.test.js`

**Step 2.1: Write tests for the pure cycle/colour helpers**

Create `reviewer-panel/src/test/dashboard/inlineStatus.test.js`:

```javascript
import { describe, it, expect } from 'vitest';
import { STATUS_ORDER, cycleStatus, statusToken } from '../../components/dashboard/inlineStatus';

describe('inlineStatus helpers', () => {
  it('exports the canonical cycle order', () => {
    expect(STATUS_ORDER).toEqual([
      'submitted', 'in_progress', 'approved', 'rejected', 'flagged', 'published',
    ]);
  });

  it('cycleStatus moves to the next status', () => {
    expect(cycleStatus('submitted')).toBe('in_progress');
    expect(cycleStatus('in_progress')).toBe('approved');
    expect(cycleStatus('published')).toBe('submitted');
  });

  it('cycleStatus on unknown falls back to "submitted"', () => {
    expect(cycleStatus('garbage')).toBe('submitted');
  });

  it('statusToken returns semantic colour tokens', () => {
    expect(statusToken('approved').accent).toBe('emerald');
    expect(statusToken('rejected').accent).toBe('rose');
    expect(statusToken('submitted').accent).toBe('indigo');
  });
});
```

**Step 2.2: Run tests, expect failure (file missing)**

Run: `cd reviewer-panel && npx vitest run src/test/dashboard/inlineStatus.test.js`
Expected: failures on import.

**Step 2.3: Implement `inlineStatus.js`**

```javascript
// Canonical status cycle for the dashboard's quick-cycle keyboard shortcut (S)
// and the inline pill dropdown. Ordered by reviewer workflow.
export const STATUS_ORDER = [
  'submitted',
  'in_progress',
  'approved',
  'rejected',
  'flagged',
  'published',
];

export function cycleStatus(current) {
  const i = STATUS_ORDER.indexOf(current);
  if (i === -1) return 'submitted';
  return STATUS_ORDER[(i + 1) % STATUS_ORDER.length];
}

// Soft tinted bg + saturated text — Linear-with-colour palette.
// Tailwind class fragments are kept in the consumer so JIT can pick them up;
// here we only return the semantic accent name for switch-mapping.
export function statusToken(status) {
  switch (status) {
    case 'submitted':   return { accent: 'indigo' };
    case 'in_progress': return { accent: 'sky' };
    case 'approved':    return { accent: 'emerald' };
    case 'rejected':    return { accent: 'rose' };
    case 'flagged':     return { accent: 'amber' };
    case 'published':   return { accent: 'violet' };
    default:            return { accent: 'slate' };
  }
}
```

**Step 2.4: Run tests, expect pass**

Run: `cd reviewer-panel && npx vitest run src/test/dashboard/inlineStatus.test.js`
Expected: 4 passing.

**Step 2.5: Implement `InlineStatusPill.jsx`**

```jsx
import { useState, useCallback } from 'react';
import { ChevronDown } from 'lucide-react';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';
import { cn } from '@/lib/utils';
import { STATUS_ORDER, statusToken } from './inlineStatus';
import { useI18n } from '../../i18n';

const PILL_CLASSES = {
  indigo:  'bg-indigo-50 text-indigo-700 ring-indigo-200/60 hover:bg-indigo-100',
  sky:     'bg-sky-50 text-sky-700 ring-sky-200/60 hover:bg-sky-100',
  emerald: 'bg-emerald-50 text-emerald-700 ring-emerald-200/60 hover:bg-emerald-100',
  rose:    'bg-rose-50 text-rose-700 ring-rose-200/60 hover:bg-rose-100',
  amber:   'bg-amber-50 text-amber-700 ring-amber-200/60 hover:bg-amber-100',
  violet:  'bg-violet-50 text-violet-700 ring-violet-200/60 hover:bg-violet-100',
  slate:   'bg-slate-100 text-slate-700 ring-slate-200/60 hover:bg-slate-200',
};

export default function InlineStatusPill({ status, onChange, disabled = false }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const accent = statusToken(status).accent;

  const select = useCallback((next) => {
    if (next !== status) onChange?.(next);
    setOpen(false);
  }, [status, onChange]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          disabled={disabled}
          className={cn(
            'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11.5px] font-medium ring-1 transition-all',
            PILL_CLASSES[accent],
            disabled && 'cursor-default opacity-60',
          )}
          onClick={(e) => e.stopPropagation()}
        >
          <span>{t(`status.${status}`) || status.replace('_', ' ')}</span>
          {!disabled && <ChevronDown size={11} className="opacity-60" />}
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-44 p-1" onClick={(e) => e.stopPropagation()}>
        {STATUS_ORDER.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => select(s)}
            className={cn(
              'flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-xs transition-colors hover:bg-accent',
              s === status && 'bg-accent/60',
            )}
          >
            <span className="capitalize">{t(`status.${s}`) || s.replace('_', ' ')}</span>
            <span
              className={cn(
                'inline-block size-1.5 rounded-full',
                {
                  indigo: 'bg-indigo-500', sky: 'bg-sky-500', emerald: 'bg-emerald-500',
                  rose: 'bg-rose-500', amber: 'bg-amber-500', violet: 'bg-violet-500',
                  slate: 'bg-slate-400',
                }[statusToken(s).accent]
              )}
            />
          </button>
        ))}
      </PopoverContent>
    </Popover>
  );
}
```

**Step 2.6: Verify panel build still succeeds**

Run: `cd reviewer-panel && npx vite build`
Expected: `built in <Ns>` with no errors.

**Step 2.7: Commit**

```bash
git add reviewer-panel/src/components/dashboard/inlineStatus.js \
        reviewer-panel/src/components/dashboard/InlineStatusPill.jsx \
        reviewer-panel/src/test/dashboard/inlineStatus.test.js
git commit -m "feat(panel): inline status pill with click-to-cycle dropdown"
```

---

## Task 3: `useKeyboardRowNav` hook

**Files:**
- Create: `reviewer-panel/src/hooks/useKeyboardRowNav.js`
- Test: `reviewer-panel/src/test/dashboard/useKeyboardRowNav.test.jsx`

The hook owns: focused row index, handlers for ↑↓ J K, callbacks for Enter (open) and S (cycle status). Pure logic — easy to test.

**Step 3.1: Write the failing tests**

```javascript
import { describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useKeyboardRowNav } from '../../hooks/useKeyboardRowNav';

const mkEvent = (key) => ({ key, preventDefault: vi.fn(), target: { tagName: 'BODY' } });

describe('useKeyboardRowNav', () => {
  it('starts with no focused row', () => {
    const { result } = renderHook(() => useKeyboardRowNav({ rowCount: 5 }));
    expect(result.current.focusedIndex).toBe(-1);
  });

  it('ArrowDown moves focus down and clamps at last row', () => {
    const { result } = renderHook(() => useKeyboardRowNav({ rowCount: 3 }));
    act(() => result.current.handleKeyDown(mkEvent('ArrowDown')));
    expect(result.current.focusedIndex).toBe(0);
    act(() => result.current.handleKeyDown(mkEvent('ArrowDown')));
    act(() => result.current.handleKeyDown(mkEvent('ArrowDown')));
    act(() => result.current.handleKeyDown(mkEvent('ArrowDown')));
    expect(result.current.focusedIndex).toBe(2);
  });

  it('j and k mirror arrow keys', () => {
    const { result } = renderHook(() => useKeyboardRowNav({ rowCount: 3 }));
    act(() => result.current.handleKeyDown(mkEvent('j')));
    expect(result.current.focusedIndex).toBe(0);
    act(() => result.current.handleKeyDown(mkEvent('j')));
    expect(result.current.focusedIndex).toBe(1);
    act(() => result.current.handleKeyDown(mkEvent('k')));
    expect(result.current.focusedIndex).toBe(0);
  });

  it('Enter calls onOpen with the focused index', () => {
    const onOpen = vi.fn();
    const { result } = renderHook(() => useKeyboardRowNav({ rowCount: 3, onOpen }));
    act(() => result.current.handleKeyDown(mkEvent('ArrowDown')));
    act(() => result.current.handleKeyDown(mkEvent('Enter')));
    expect(onOpen).toHaveBeenCalledWith(0);
  });

  it('S calls onCycleStatus with the focused index', () => {
    const onCycleStatus = vi.fn();
    const { result } = renderHook(() => useKeyboardRowNav({ rowCount: 3, onCycleStatus }));
    act(() => result.current.handleKeyDown(mkEvent('ArrowDown')));
    act(() => result.current.handleKeyDown(mkEvent('s')));
    expect(onCycleStatus).toHaveBeenCalledWith(0);
  });

  it('ignores keys when typing in an input', () => {
    const onOpen = vi.fn();
    const { result } = renderHook(() => useKeyboardRowNav({ rowCount: 3, onOpen }));
    const e = { key: 'Enter', preventDefault: vi.fn(), target: { tagName: 'INPUT' } };
    act(() => result.current.handleKeyDown(e));
    expect(onOpen).not.toHaveBeenCalled();
  });
});
```

**Step 3.2: Run tests, expect failure**

Run: `cd reviewer-panel && npx vitest run src/test/dashboard/useKeyboardRowNav.test.jsx`
Expected: failures on import.

**Step 3.3: Implement `useKeyboardRowNav.js`**

```javascript
import { useCallback, useState } from 'react';

const TYPING_TAGS = new Set(['INPUT', 'TEXTAREA', 'SELECT']);

export function useKeyboardRowNav({ rowCount, onOpen, onCycleStatus }) {
  const [focusedIndex, setFocusedIndex] = useState(-1);

  const handleKeyDown = useCallback((e) => {
    const tag = e.target?.tagName;
    if (TYPING_TAGS.has(tag) || e.target?.isContentEditable) return;

    const down  = e.key === 'ArrowDown' || e.key === 'j';
    const up    = e.key === 'ArrowUp'   || e.key === 'k';
    const open  = e.key === 'Enter';
    const cycle = e.key === 's' || e.key === 'S';

    if (!(down || up || open || cycle)) return;
    e.preventDefault();

    if (down) {
      setFocusedIndex((i) => Math.min(rowCount - 1, i + 1 < 0 ? 0 : i + 1));
      return;
    }
    if (up) {
      setFocusedIndex((i) => Math.max(0, i - 1));
      return;
    }
    if (open && focusedIndex >= 0) {
      onOpen?.(focusedIndex);
      return;
    }
    if (cycle && focusedIndex >= 0) {
      onCycleStatus?.(focusedIndex);
    }
  }, [rowCount, onOpen, onCycleStatus, focusedIndex]);

  return { focusedIndex, setFocusedIndex, handleKeyDown };
}
```

**Step 3.4: Run tests, expect pass**

Run: `cd reviewer-panel && npx vitest run src/test/dashboard/useKeyboardRowNav.test.jsx`
Expected: 6 passing.

**Step 3.5: Commit**

```bash
git add reviewer-panel/src/hooks/useKeyboardRowNav.js \
        reviewer-panel/src/test/dashboard/useKeyboardRowNav.test.jsx
git commit -m "feat(panel): keyboard row navigation hook (↑↓/j/k/Enter/S)"
```

---

## Task 4: `StatStrip` component

**Files:**
- Create: `reviewer-panel/src/components/dashboard/StatStrip.jsx`

Pure presentational. No tests — visual only. The text comes from props; rendering is a flexbox row with three numeric labels.

**Step 4.1: Implement**

```jsx
import { useI18n } from '../../i18n';
import { cn } from '@/lib/utils';

export default function StatStrip({ pending, reviewedToday, totalPublished, loading }) {
  const { t } = useI18n();

  const items = [
    { label: t('dashboard.pendingReview'),  value: pending,         accent: true  },
    { label: t('dashboard.reviewedToday'),  value: reviewedToday,   accent: false },
    { label: t('dashboard.totalPublished'), value: totalPublished,  accent: false },
  ];

  return (
    <div className="flex items-baseline gap-x-6 text-[13px] text-muted-foreground">
      {items.map((item, i) => (
        <div key={item.label} className="flex items-baseline gap-1.5">
          <span
            className={cn(
              'font-semibold tabular-nums text-foreground',
              item.accent && 'text-primary',
              loading && 'opacity-50',
            )}
          >
            {loading ? '—' : (item.value ?? 0).toLocaleString()}
          </span>
          <span>{item.label}</span>
          {i < items.length - 1 && <span className="ml-3 text-muted-foreground/40">·</span>}
        </div>
      ))}
    </div>
  );
}
```

**Step 4.2: Verify build**

Run: `cd reviewer-panel && npx vite build`
Expected: build succeeds.

**Step 4.3: Commit**

```bash
git add reviewer-panel/src/components/dashboard/StatStrip.jsx
git commit -m "feat(panel): inline stat strip replacing three stat cards"
```

---

## Task 5: `FilterBar` component

**Files:**
- Create: `reviewer-panel/src/components/dashboard/FilterBar.jsx`

Single-row segmented chips for status + category, plus a search input. All controlled — value/onChange props from the parent (current DashboardPage already owns these in state).

**Step 5.1: Implement**

```jsx
import { Search, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useI18n } from '../../i18n';

const STATUS_FILTERS = [
  { value: '',            labelKey: 'dashboard.filterAll' },
  { value: 'submitted',   labelKey: 'status.submitted' },
  { value: 'in_progress', labelKey: 'status.inProgress' },
  { value: 'approved',    labelKey: 'status.approved' },
  { value: 'flagged',     labelKey: 'status.flagged' },
];

export default function FilterBar({
  search, onSearchChange,
  status, onStatusChange,
  categories = [], category, onCategoryChange,
}) {
  const { t } = useI18n();

  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-border/60 px-1 py-2.5">
      {/* Search */}
      <div className="relative">
        <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <input
          type="text"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder={t('dashboard.searchPlaceholder')}
          className="h-8 w-56 rounded-md border border-border/60 bg-card pl-8 pr-7 text-xs outline-none transition-colors focus:border-ring focus:shadow-[0_0_0_3px_rgba(250,108,56,0.08)]"
        />
        {search && (
          <button
            type="button"
            onClick={() => onSearchChange('')}
            className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-0.5 text-muted-foreground hover:bg-accent"
            aria-label="Clear search"
          >
            <X size={12} />
          </button>
        )}
      </div>

      {/* Status chips */}
      <div className="flex items-center gap-0.5 rounded-md border border-border/60 bg-card p-0.5">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.value || 'all'}
            type="button"
            onClick={() => onStatusChange(f.value)}
            className={cn(
              'rounded-[5px] px-2 py-1 text-[11.5px] font-medium transition-colors',
              status === f.value
                ? 'bg-primary/10 text-primary'
                : 'text-muted-foreground hover:bg-accent hover:text-foreground',
            )}
          >
            {t(f.labelKey) || f.value}
          </button>
        ))}
      </div>

      {/* Category dropdown — kept simple; categories vary per org */}
      {categories.length > 0 && (
        <select
          value={category || ''}
          onChange={(e) => onCategoryChange(e.target.value)}
          className="h-8 rounded-md border border-border/60 bg-card px-2 text-xs text-foreground outline-none focus:border-ring"
        >
          <option value="">{t('dashboard.filterAllCategories') || 'All categories'}</option>
          {categories.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      )}
    </div>
  );
}
```

**Step 5.2: Verify build**

Run: `cd reviewer-panel && npx vite build`
Expected: build succeeds.

**Step 5.3: Add the new i18n keys (`dashboard.filterAll`, `dashboard.filterAllCategories`)**

Edit `reviewer-panel/src/i18n/locales/en.json`, `or.json`, `hi.json`.
Append next to existing `dashboard.*` keys:

en:
```json
"filterAll": "All",
"filterAllCategories": "All categories",
```

or:
```json
"filterAll": "ସମସ୍ତ",
"filterAllCategories": "ସମସ୍ତ ବିଭାଗ",
```

hi:
```json
"filterAll": "सभी",
"filterAllCategories": "सभी श्रेणियाँ",
```

**Step 5.4: Commit**

```bash
git add reviewer-panel/src/components/dashboard/FilterBar.jsx \
        reviewer-panel/src/i18n/locales/en.json \
        reviewer-panel/src/i18n/locales/or.json \
        reviewer-panel/src/i18n/locales/hi.json
git commit -m "feat(panel): filter bar with segmented status chips + inline search"
```

---

## Task 6: `RowHoverPeek` floating preview

**Files:**
- Create: `reviewer-panel/src/components/dashboard/RowHoverPeek.jsx`

Renders a floating card pinned to the right of the hovered row. The trigger is a 400 ms delay before showing — this lets the reviewer scan rows fast without flicker. We use shadcn's existing `Popover` with `open`/`onOpenChange` controlled, plus a debounced `setTimeout` driven by row mouse-enter/leave.

The peek payload comes from the row data already in memory (no extra fetch).

**Step 6.1: Implement**

```jsx
import { useEffect, useState } from 'react';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';
import { getMediaUrl } from '../../services/api';

const HOVER_DELAY_MS = 400;

export default function RowHoverPeek({ children, story, enabled = true }) {
  const [open, setOpen] = useState(false);
  const [pendingTimer, setPendingTimer] = useState(null);

  useEffect(() => () => pendingTimer && clearTimeout(pendingTimer), [pendingTimer]);

  if (!enabled || !story) return children;

  const firstParagraph = (story.paragraphs?.[0]?.text || '').slice(0, 240);
  const firstImage = story.paragraphs?.find((p) => p.media_path)?.media_path;

  const onEnter = () => {
    const timer = setTimeout(() => setOpen(true), HOVER_DELAY_MS);
    setPendingTimer(timer);
  };
  const onLeave = () => {
    if (pendingTimer) clearTimeout(pendingTimer);
    setPendingTimer(null);
    setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <div onMouseEnter={onEnter} onMouseLeave={onLeave} className="contents">
          {children}
        </div>
      </PopoverTrigger>
      <PopoverContent
        side="right"
        align="start"
        className="w-80 p-3"
        onPointerEnter={(e) => e.preventDefault()}
      >
        <div className="space-y-2">
          {firstImage && (
            <img
              src={getMediaUrl(firstImage)}
              alt=""
              className="h-32 w-full rounded-md object-cover"
              loading="lazy"
            />
          )}
          <p className="text-xs leading-relaxed text-muted-foreground">
            {firstParagraph || '(empty)'}
          </p>
        </div>
      </PopoverContent>
    </Popover>
  );
}
```

**Step 6.2: Verify build**

Run: `cd reviewer-panel && npx vite build`
Expected: build succeeds.

**Step 6.3: Commit**

```bash
git add reviewer-panel/src/components/dashboard/RowHoverPeek.jsx
git commit -m "feat(panel): row hover-peek with 400ms delay and lead paragraph preview"
```

---

## Task 7: Live arrival CSS animation

**Files:**
- Modify: `reviewer-panel/src/index.css` (add a single keyframes rule + utility class)

The animation lives in CSS so the table component can opt rows in by adding a `data-just-arrived` attribute when a row's id wasn't in the previous fetch.

**Step 7.1: Append to `reviewer-panel/src/index.css`**

```css
@keyframes vr-row-arrival {
  0%   { background-color: rgba(250, 108, 56, 0.18); }
  60%  { background-color: rgba(250, 108, 56, 0.12); }
  100% { background-color: transparent; }
}

.vr-row-arrival {
  animation: vr-row-arrival 2s ease-out;
}
```

**Step 7.2: Verify build**

Run: `cd reviewer-panel && npx vite build`
Expected: build succeeds.

**Step 7.3: Commit**

```bash
git add reviewer-panel/src/index.css
git commit -m "feat(panel): coral row-arrival highlight keyframes"
```

---

## Task 8: `ReviewQueueTable` component

**Files:**
- Create: `reviewer-panel/src/components/dashboard/ReviewQueueTable.jsx`

This is the main rendering component. It owns the JSX for rows + columns and consumes everything we've built so far. The diffing-for-arrivals logic lives here (compare incoming story IDs against a `useRef`-stored previous list).

**Step 8.1: Implement**

```jsx
import { useEffect, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Avatar } from '../common';
import { formatDate } from '../../utils/helpers';
import { useI18n } from '../../i18n';
import { DENSITIES } from '../../hooks/useDensityPreference';
import InlineStatusPill from './InlineStatusPill';
import RowHoverPeek from './RowHoverPeek';

export default function ReviewQueueTable({
  stories,
  loading,
  density = 'comfortable',
  focusedIndex = -1,
  onRowFocus,
  onStatusChange,
}) {
  const navigate = useNavigate();
  const { t } = useI18n();
  const rowHeight = DENSITIES[density].rowHeight;

  // Track which IDs were already on the page. New IDs (i.e. arrived during
  // this render compared to the previous render) get the arrival highlight.
  const prevIdsRef = useRef(new Set());
  const arrivedIds = useMemo(() => {
    const next = new Set(stories.map((s) => s.id));
    const arrived = stories
      .map((s) => s.id)
      .filter((id) => !prevIdsRef.current.has(id));
    prevIdsRef.current = next;
    return new Set(arrived);
  }, [stories]);

  // Clear the arrival class after the animation duration so re-renders
  // don't re-trigger it.
  useEffect(() => {
    const timers = [...arrivedIds].map((id) =>
      setTimeout(() => {
        const el = document.querySelector(`[data-row-id="${id}"]`);
        el?.classList.remove('vr-row-arrival');
      }, 2200)
    );
    return () => timers.forEach(clearTimeout);
  }, [arrivedIds]);

  if (loading && stories.length === 0) {
    return (
      <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
        {t('common.loading') || 'Loading…'}
      </div>
    );
  }

  if (!loading && stories.length === 0) {
    return (
      <div className="flex h-40 flex-col items-center justify-center gap-1 text-sm text-muted-foreground">
        <span className="text-base font-medium text-foreground">{t('dashboard.noReports')}</span>
        <span className="text-xs">{t('dashboard.noReportsHint') || 'New submissions will appear here.'}</span>
      </div>
    );
  }

  return (
    <div role="grid" className="divide-y divide-border/40">
      {/* Sticky header */}
      <div
        className="sticky top-0 z-10 grid items-center gap-4 bg-background/95 px-4 text-[11px] font-medium uppercase tracking-wider text-muted-foreground backdrop-blur"
        style={{
          gridTemplateColumns: 'minmax(0,2fr) minmax(0,1.4fr) 110px 110px 130px 32px',
          height: 36,
        }}
      >
        <div>{t('table.storyTitle')}</div>
        <div>{t('table.reporterSubject')}</div>
        <div>{t('table.submissionTime')}</div>
        <div>{t('table.category')}</div>
        <div>{t('table.status')}</div>
        <div />
      </div>

      {stories.map((story, idx) => {
        const isFocused = idx === focusedIndex;
        const isArrived = arrivedIds.has(story.id);
        return (
          <RowHoverPeek key={story.id} story={story}>
            <div
              role="row"
              data-row-id={story.id}
              className={cn(
                'group grid cursor-pointer items-center gap-4 px-4 transition-colors',
                'hover:bg-accent/40',
                isFocused && 'bg-primary/[0.04] shadow-[inset_2px_0_0_0_var(--primary)]',
                isArrived && 'vr-row-arrival',
              )}
              style={{
                gridTemplateColumns: 'minmax(0,2fr) minmax(0,1.4fr) 110px 110px 130px 32px',
                height: rowHeight,
              }}
              onMouseEnter={() => onRowFocus?.(idx)}
              onClick={() => navigate(`/review/${story.id}`)}
            >
              {/* Story title */}
              <div className="min-w-0">
                <div className="truncate text-[13.5px] font-medium text-foreground">
                  {story.headline || t('table.untitled') || 'Untitled'}
                </div>
                {story.display_id && (
                  <div className="text-[11px] text-primary/80">{story.display_id}</div>
                )}
              </div>

              {/* Reporter */}
              <div className="flex min-w-0 items-center gap-2">
                <Avatar
                  initials={story.reporter?.initials}
                  color={story.reporter?.color}
                  size={26}
                />
                <div className="min-w-0">
                  <div className="truncate text-[13px] text-foreground">
                    {story.reporter?.name || '—'}
                  </div>
                  {story.reporter?.area_name && (
                    <div className="truncate text-[11px] text-muted-foreground">
                      {story.reporter.area_name}
                    </div>
                  )}
                </div>
              </div>

              {/* Time */}
              <div className="text-xs tabular-nums text-muted-foreground">
                {formatDate(story.submittedAt)}
              </div>

              {/* Category — dot + label */}
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span className="inline-block size-1.5 rounded-full bg-muted-foreground/40 transition-colors group-hover:bg-primary" />
                <span className="truncate">{story.category || '—'}</span>
              </div>

              {/* Status pill (inline editable) */}
              <div onClick={(e) => e.stopPropagation()}>
                <InlineStatusPill
                  status={story.status}
                  onChange={(next) => onStatusChange?.(story.id, next)}
                />
              </div>

              {/* Action chevron */}
              <div className="text-muted-foreground/60 transition-colors group-hover:text-primary">
                <ChevronRight size={16} />
              </div>
            </div>
          </RowHoverPeek>
        );
      })}
    </div>
  );
}
```

**Step 8.2: Verify build**

Run: `cd reviewer-panel && npx vite build`
Expected: build succeeds.

**Step 8.3: Commit**

```bash
git add reviewer-panel/src/components/dashboard/ReviewQueueTable.jsx
git commit -m "feat(panel): review queue table with peek/inline-status/live-arrival"
```

---

## Task 9: `DensityToggle` component

**Files:**
- Create: `reviewer-panel/src/components/dashboard/DensityToggle.jsx`

Three-segment switch (Compact / Comfortable / Cozy). Driven by `useDensityPreference`.

**Step 9.1: Implement**

```jsx
import { LayoutList, Rows3, Square } from 'lucide-react';
import { cn } from '@/lib/utils';
import { DENSITIES } from '../../hooks/useDensityPreference';
import { useI18n } from '../../i18n';

const ICONS = {
  compact:     LayoutList,
  comfortable: Rows3,
  cozy:        Square,
};

export default function DensityToggle({ value, onChange }) {
  const { t } = useI18n();
  return (
    <div className="flex items-center gap-0.5 rounded-md border border-border/60 bg-card p-0.5">
      {Object.entries(DENSITIES).map(([key, d]) => {
        const Icon = ICONS[key];
        const active = value === key;
        return (
          <button
            key={key}
            type="button"
            onClick={() => onChange(key)}
            className={cn(
              'flex size-7 items-center justify-center rounded-[5px] transition-colors',
              active ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:bg-accent hover:text-foreground',
            )}
            title={t(`dashboard.density.${key}`) || d.label}
          >
            <Icon size={14} />
          </button>
        );
      })}
    </div>
  );
}
```

**Step 9.2: Add i18n entries**

Append `density: { compact, comfortable, cozy }` under `dashboard` in all three locale files.

en:
```json
"density": { "compact": "Compact", "comfortable": "Comfortable", "cozy": "Cozy" }
```
or:
```json
"density": { "compact": "ସଂକୁଚିତ", "comfortable": "ସୁଖଦ", "cozy": "ଆରାମଦାୟକ" }
```
hi:
```json
"density": { "compact": "सघन", "comfortable": "सहज", "cozy": "विशाल" }
```

**Step 9.3: Verify build + commit**

```bash
cd reviewer-panel && npx vite build
git add reviewer-panel/src/components/dashboard/DensityToggle.jsx \
        reviewer-panel/src/i18n/locales/en.json \
        reviewer-panel/src/i18n/locales/or.json \
        reviewer-panel/src/i18n/locales/hi.json
git commit -m "feat(panel): density toggle (compact / comfortable / cozy)"
```

---

## Task 10: Wire it all together — replace `DashboardPage.jsx`

**Files:**
- Modify: `reviewer-panel/src/pages/DashboardPage.jsx` (full rewrite)

The new file:
- Keeps the existing `fetchStats` / `fetchStories` polling loop and `reassignStory` logic.
- Uses `useDensityPreference` for the row height.
- Uses `useKeyboardRowNav` for ↑↓ J K Enter S.
- Renders `<StatStrip>`, `<FilterBar>`, `<ReviewQueueTable>`, `<DensityToggle>`.
- Calls `updateStoryStatus` (already exported from `services/api`) on inline status change.
- Pagination stays as today (the existing component is fine; just restyled to match — see step 10.2 if needed).

**Step 10.1: Read the current file first**

Run: `cat reviewer-panel/src/pages/DashboardPage.jsx | head -60` — confirm imports and prop shapes you'll keep.

**Step 10.2: Implement — full file**

```jsx
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  fetchStats, fetchStories, transformStory, updateStoryStatus,
} from '../services/api';
import { useDensityPreference } from '../hooks/useDensityPreference';
import { useKeyboardRowNav } from '../hooks/useKeyboardRowNav';
import { cycleStatus } from '../components/dashboard/inlineStatus';
import StatStrip from '../components/dashboard/StatStrip';
import FilterBar from '../components/dashboard/FilterBar';
import ReviewQueueTable from '../components/dashboard/ReviewQueueTable';
import DensityToggle from '../components/dashboard/DensityToggle';
import { useI18n } from '../i18n';
import { useAuth } from '../contexts/AuthContext';

const PAGE_SIZE = 25;
const REFRESH_INTERVAL = 30_000;

export default function DashboardPage() {
  const { t } = useI18n();
  const { config } = useAuth();
  const navigate = useNavigate();

  // Stats
  const [stats, setStats] = useState({ pending_review: 0, reviewed_today: 0, total_published: 0 });
  const [statsLoading, setStatsLoading] = useState(true);

  // Stories
  const [stories, setStories] = useState([]);
  const [storiesLoading, setStoriesLoading] = useState(true);

  // Filters
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');

  // Preferences
  const [density, setDensity] = useDensityPreference();

  const intervalRef = useRef(null);

  const loadStats = useCallback(async () => {
    try {
      const data = await fetchStats();
      setStats(data);
    } catch (err) {
      console.error('Stats failed:', err);
    } finally {
      setStatsLoading(false);
    }
  }, []);

  const loadStories = useCallback(async () => {
    try {
      const params = { limit: PAGE_SIZE };
      if (search)         params.search = search;
      if (statusFilter)   params.status = statusFilter;
      if (categoryFilter) params.category = categoryFilter;
      const data = await fetchStories(params);
      setStories((data?.stories || []).map(transformStory));
    } catch (err) {
      console.error('Stories failed:', err);
    } finally {
      setStoriesLoading(false);
    }
  }, [search, statusFilter, categoryFilter]);

  // Initial + filter-change fetches
  useEffect(() => { loadStats(); }, [loadStats]);
  useEffect(() => { loadStories(); }, [loadStories]);

  // Polling
  useEffect(() => {
    intervalRef.current = setInterval(() => {
      loadStats();
      loadStories();
    }, REFRESH_INTERVAL);
    return () => clearInterval(intervalRef.current);
  }, [loadStats, loadStories]);

  // Inline status change (optimistic)
  const handleStatusChange = useCallback(async (storyId, nextStatus) => {
    setStories((prev) => prev.map((s) => s.id === storyId ? { ...s, status: nextStatus } : s));
    try {
      await updateStoryStatus(storyId, nextStatus);
      loadStats();
    } catch (err) {
      console.error('Status change failed:', err);
      loadStories(); // revert by re-fetching
    }
  }, [loadStats, loadStories]);

  // Keyboard nav
  const onOpenRow = useCallback((idx) => {
    const story = stories[idx];
    if (story) navigate(`/review/${story.id}`);
  }, [stories, navigate]);
  const onCycleRowStatus = useCallback((idx) => {
    const story = stories[idx];
    if (story) handleStatusChange(story.id, cycleStatus(story.status));
  }, [stories, handleStatusChange]);

  const { focusedIndex, setFocusedIndex, handleKeyDown } = useKeyboardRowNav({
    rowCount: stories.length,
    onOpen: onOpenRow,
    onCycleStatus: onCycleRowStatus,
  });

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const categories = useMemo(
    () => (config?.categories || []).map((c) => c.label || c),
    [config]
  );

  return (
    <div className="flex h-full flex-col">
      {/* Header strip */}
      <header className="flex flex-wrap items-center justify-between gap-4 px-6 pt-6">
        <div className="flex flex-col gap-1">
          <h1 className="text-xl font-semibold tracking-tight text-foreground">
            {t('dashboard.title')}
          </h1>
          <StatStrip
            pending={stats.pending_review}
            reviewedToday={stats.reviewed_today}
            totalPublished={stats.total_published}
            loading={statsLoading}
          />
        </div>
        <DensityToggle value={density} onChange={setDensity} />
      </header>

      {/* Filter bar */}
      <div className="px-6">
        <FilterBar
          search={search}             onSearchChange={setSearch}
          status={statusFilter}       onStatusChange={setStatusFilter}
          categories={categories}     category={categoryFilter}      onCategoryChange={setCategoryFilter}
        />
      </div>

      {/* Table */}
      <div className="flex-1 overflow-y-auto px-6 pb-6">
        <ReviewQueueTable
          stories={stories}
          loading={storiesLoading}
          density={density}
          focusedIndex={focusedIndex}
          onRowFocus={setFocusedIndex}
          onStatusChange={handleStatusChange}
        />
      </div>
    </div>
  );
}
```

**Step 10.3: Verify build**

Run: `cd reviewer-panel && npx vite build`
Expected: build succeeds, no warnings about missing imports/components.

**Step 10.4: Run the full panel test suite**

Run: `cd reviewer-panel && npx vitest run`
Expected: previous 29 tests still pass, plus the new 15 (5 density + 4 status + 6 keyboard) = **44 passing**.

**Step 10.5: Commit**

```bash
git add reviewer-panel/src/pages/DashboardPage.jsx
git commit -m "feat(panel): replace DashboardPage with Linear-with-color queue"
```

---

## Task 11: Push to develop, watch UAT, then merge to main

**Step 11.1: Push develop**

```bash
cd /Users/admin/Desktop/newsflow-api
git push origin develop
```

**Step 11.2: Watch the UAT deploy**

Run: `gh run list --branch develop --limit 2`
Expected: `Deploy to UAT` and `CI — Tests` both eventually `completed success`.

**Step 11.3: User-driven UAT smoke check (manual)**

Open https://vrittant-uat.web.app — verify:
- Stat strip shows three numbers in one row, coral on the pending count.
- Filter bar is one row of segmented chips + search.
- Hovering a row for ~½ second pops the peek card.
- Clicking a status pill opens a dropdown with all six statuses.
- Pressing `↓` focuses the first row (coral left-edge); `Enter` opens it; `S` cycles its status.
- Density toggle works and survives a refresh.

If any check fails: stop, debug, push fix; do NOT merge to main.

**Step 11.4: Merge to main + push (only after smoke checks pass)**

```bash
git checkout main
git merge --no-ff develop -m "merge develop: dashboard redesign — Linear-with-color"
git push origin main
git checkout develop
```

**Step 11.5: Verify prod deploy**

Run: `gh run list --branch main --limit 2`
Expected: `Deploy to Production` `completed success`.

---

## Rollback (only if user rejects after seeing prod)

```bash
cd /Users/admin/Desktop/newsflow-api
git checkout main
git reset --hard pre-dashboard-redesign-2026-04-30
git push --force-with-lease origin main
git checkout develop
git reset --hard pre-dashboard-redesign-2026-04-30
git push --force-with-lease origin develop
```

This removes every commit produced by this plan from both branches. The design doc and rollback tag remain in the reflog if we want to revisit.

---

## Out of scope (follow-up plans)

- All Stories table redesign (same primitives apply, but column shape differs — separate plan).
- Reporters table redesign with sparkline trends.
- BucketsList page (cards, not a table — different design language).
- Bulk-action multi-select on the queue.
- Saved views / per-user filter presets.
