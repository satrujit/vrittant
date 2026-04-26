import { useEffect, useMemo, useState, useCallback } from 'react';
import { Calendar as CalendarIcon } from 'lucide-react';
import { useI18n } from '../../i18n';
import {
  getStoryPlacements,
  setStoryPlacements,
  listTodaysEditions,
} from '../../services/api/editions.js';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

const AVIMAT = 'Avimat';

/** Today's date in IST as YYYY-MM-DD. The day editor's clock matters,
 *  not the browser's UTC offset. */
function todayIST() {
  const fmt = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Kolkata',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
  return fmt.format(new Date()); // en-CA gives YYYY-MM-DD
}

/** "27 April 2028" — long format used in the section header. */
function formatLongDate(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  return new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(dt);
}

/** Pull just the page number out of a page_name like "Page 6". Falls
 *  back to the full name when the title isn't a "Page N" string. The
 *  cell renders the number BIG, so most reviewers should see a single
 *  glanceable digit. */
function shortPageLabel(pageName) {
  if (!pageName) return null;
  const m = String(pageName).match(/(\d+)/);
  return m ? m[1] : pageName;
}

/**
 * EditionPlacementMatrix — story → edition page assignments.
 *
 * Layout: a 3-column grid of edition cells (one per geographic
 * edition). Each cell stacks the edition name on top of the
 * currently-assigned page number (or an em-dash when not placed).
 * Clicking a cell opens a popover to pick a page or drop the story
 * from that edition.
 *
 * Date control: the active publication date renders as a long
 * formatted string ("27 April 2028") and clicking it opens a
 * calendar popover with a native date picker. Replaces the older
 * ‹ ›-stepper UI.
 *
 * Avimat (Sunday-only edition) is intentionally never auto-filled —
 * direct clicks on its cell are the only way to place a story there.
 *
 * State model:
 *   - `placements` mirrors the server (list of {edition_id, page_id, ...})
 *   - `overrides` is a Set of edition ids the user has clicked this
 *     mount; cells in the override set are immune to fan-out
 *   - All mutations PUT the full placement set in one call
 */
export function EditionPlacementMatrix({ storyId }) {
  const { t } = useI18n();
  // Default to today (IST), not the story's submission date — a story
  // submitted yesterday can still be slated for tomorrow's edition.
  const [activeDate, setActiveDate] = useState(() => todayIST());

  const [editions, setEditions] = useState([]);
  const [placements, setPlacements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [overrides, setOverrides] = useState(() => new Set());
  const [datePopoverOpen, setDatePopoverOpen] = useState(false);

  // Initial load + reload when active date changes.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([
      listTodaysEditions(activeDate),
      storyId ? getStoryPlacements(storyId) : Promise.resolve([]),
    ])
      .then(([edData, plData]) => {
        if (cancelled) return;
        setEditions(edData?.editions || edData?.items || edData || []);
        setPlacements(Array.isArray(plData) ? plData : []);
      })
      .catch(() => {
        if (cancelled) return;
        setEditions([]);
        setPlacements([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeDate, storyId]);

  // Sort: canonical geographic editions first by their backend order
  // (the seeder writes them in a stable list per org), Avimat last.
  // Falls back to numeric suffix sort for legacy "Ed 1" / "Ed 6" rows.
  const sortedEditions = useMemo(() => {
    const numOf = (title) => {
      const m = String(title || '').match(/(\d+)/);
      return m ? Number(m[1]) : Number.POSITIVE_INFINITY;
    };
    return [...editions].sort((a, b) => {
      if (a.title === AVIMAT) return 1;
      if (b.title === AVIMAT) return -1;
      const an = numOf(a.title);
      const bn = numOf(b.title);
      if (an !== bn) return an - bn;
      return String(a.title || '').localeCompare(String(b.title || ''));
    });
  }, [editions]);

  const placementByEdition = useMemo(() => {
    const m = new Map();
    for (const ed of editions) m.set(ed.id, null);
    for (const p of placements) {
      m.set(p.edition_id, { pageId: p.page_id, pageName: p.page_name });
    }
    return m;
  }, [editions, placements]);

  const commit = useCallback(
    async (nextMap) => {
      const payload = [];
      for (const [edId, val] of nextMap.entries()) {
        if (val?.pageId) payload.push({ edition_id: edId, page_id: val.pageId });
      }
      setSaving(true);
      try {
        const data = await setStoryPlacements(storyId, payload);
        setPlacements(Array.isArray(data) ? data : []);
      } catch (err) {
        console.error('Failed to save placements:', err);
      } finally {
        setSaving(false);
      }
    },
    [storyId]
  );

  const pickPage = useCallback(
    (editionId, page) => {
      const next = new Map(placementByEdition);
      next.set(
        editionId,
        page ? { pageId: page.id, pageName: page.page_name } : null
      );
      setOverrides((s) => {
        const ns = new Set(s);
        ns.add(editionId);
        return ns;
      });
      // Fan-out: pick the same page-by-name on every other non-Avimat
      // edition that the reviewer hasn't already touched this mount.
      // Saves 5 extra clicks for "this story goes on page 3 everywhere".
      if (page) {
        for (const ed of editions) {
          if (ed.id === editionId) continue;
          if (overrides.has(ed.id)) continue;
          if (ed.title === AVIMAT) continue;
          const match = ed.pages?.find((p) => p.page_name === page.page_name);
          if (match) next.set(ed.id, { pageId: match.id, pageName: match.page_name });
        }
      }
      commit(next);
    },
    [placementByEdition, editions, overrides, commit]
  );

  const dropFromEdition = useCallback(
    (editionId) => {
      const next = new Map(placementByEdition);
      next.set(editionId, null);
      setOverrides((s) => {
        const ns = new Set(s);
        ns.add(editionId);
        return ns;
      });
      commit(next);
    },
    [placementByEdition, commit]
  );

  const clearAll = useCallback(() => {
    const next = new Map();
    for (const ed of editions) next.set(ed.id, null);
    commit(next);
  }, [editions, commit]);

  const hasAny = useMemo(
    () => [...placementByEdition.values()].some((v) => v?.pageId),
    [placementByEdition]
  );

  return (
    <div className="px-4 pb-3">
      {/* Header row: clickable date (opens calendar) + Clear All link.
          Date sits in primary colour so it reads as the focal point. */}
      <div className="mb-3 flex items-center justify-between gap-2">
        <Popover open={datePopoverOpen} onOpenChange={setDatePopoverOpen}>
          <PopoverTrigger asChild>
            <button
              type="button"
              className="inline-flex items-center gap-1.5 rounded-md border-none bg-transparent p-0 text-sm font-semibold text-primary transition-opacity hover:opacity-80"
              title={t('placements.changeDate', 'Change date')}
            >
              <CalendarIcon size={14} />
              <span>{formatLongDate(activeDate)}</span>
            </button>
          </PopoverTrigger>
          <PopoverContent align="start" className="w-auto p-2">
            <Input
              type="date"
              autoFocus
              className="h-8 w-[160px] text-xs"
              value={activeDate}
              onChange={(e) => {
                if (e.target.value) {
                  setActiveDate(e.target.value);
                  setDatePopoverOpen(false);
                }
              }}
            />
            <button
              type="button"
              onClick={() => {
                setActiveDate(todayIST());
                setDatePopoverOpen(false);
              }}
              className="mt-1.5 w-full rounded-md border border-border bg-background px-2 py-1 text-[11px] hover:bg-accent"
            >
              {t('placements.today', 'Today')}
            </button>
          </PopoverContent>
        </Popover>

        <div className="flex items-center gap-2">
          {saving && (
            <span className="text-[10px] text-muted-foreground">{t('common.saving', 'saving…')}</span>
          )}
          {hasAny && (
            <button
              type="button"
              onClick={clearAll}
              className="border-none bg-transparent p-0 text-xs text-muted-foreground hover:text-foreground hover:underline"
            >
              {t('placements.clearAll', 'Clear All')}
            </button>
          )}
        </div>
      </div>

      {loading ? (
        <div className="text-xs text-muted-foreground">{t('common.loading', 'Loading...')}</div>
      ) : !editions.length ? (
        <div className="text-xs text-muted-foreground">
          {t('placements.noEditions', { date: formatLongDate(activeDate) })}
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-x-3 gap-y-4">
          {sortedEditions.map((ed) => (
            <Cell
              key={ed.id}
              edition={ed}
              current={placementByEdition.get(ed.id)}
              onPick={(p) => pickPage(ed.id, p)}
              onDrop={() => dropFromEdition(ed.id)}
              dropLabel={t('placements.drop')}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function Cell({ edition, current, onPick, onDrop, dropLabel }) {
  const [open, setOpen] = useState(false);
  const display = shortPageLabel(current?.pageName);
  const isPlaced = !!current?.pageId;
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={cn(
            'group flex min-w-0 cursor-pointer flex-col items-start gap-0.5 rounded border-none bg-transparent p-0 text-left transition-opacity hover:opacity-80',
          )}
        >
          <span className="truncate text-[13px] font-semibold text-foreground" title={edition.title}>
            {edition.title}
          </span>
          <span
            className={cn(
              'text-[26px] font-semibold leading-none tabular-nums',
              isPlaced ? 'text-foreground' : 'text-muted-foreground/60',
            )}
          >
            {display || '–'}
          </span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="max-h-60 w-44 overflow-y-auto p-1">
        {edition.pages?.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => {
              onPick(p);
              setOpen(false);
            }}
            className={cn(
              'block w-full whitespace-nowrap rounded px-2 py-1 text-left text-xs hover:bg-accent',
              current?.pageId === p.id && 'bg-primary/10 font-semibold'
            )}
          >
            {p.page_name}
          </button>
        ))}
        {isPlaced && (
          <>
            <div className="my-1 border-t border-border" />
            <button
              type="button"
              onClick={() => {
                onDrop();
                setOpen(false);
              }}
              className="block w-full whitespace-nowrap rounded px-2 py-1 text-left text-xs text-destructive hover:bg-destructive/10"
            >
              {dropLabel}
            </button>
          </>
        )}
      </PopoverContent>
    </Popover>
  );
}

export default EditionPlacementMatrix;
