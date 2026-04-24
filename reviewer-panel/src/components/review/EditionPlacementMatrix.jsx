import { useEffect, useMemo, useState, useCallback } from 'react';
import { useI18n } from '../../i18n';
import {
  getStoryPlacements,
  setStoryPlacements,
  listTodaysEditions,
} from '../../services/api/editions.js';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';
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

function shiftDate(iso, days) {
  const [y, m, d] = iso.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + days);
  return dt.toISOString().slice(0, 10);
}

/**
 * EditionPlacementMatrix — one row of cells, one per edition for the
 * story's publication date. Clicking a cell opens a popover to pick a
 * page (or drop the story from that edition). When you pick a page, the
 * choice fans out to every other non-Avimat edition that has a page with
 * the same name and hasn't been manually overridden in this session.
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
  // The reviewer can step the date forward/back to navigate days that
  // have editions; un-placed stories simply stay in review status.
  const [activeDate, setActiveDate] = useState(() => todayIST());

  const [editions, setEditions] = useState([]);
  const [placements, setPlacements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [overrides, setOverrides] = useState(() => new Set());

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

  // Sort: daily editions first by numeric suffix (Ed 1, Ed 2, …), Avimat last.
  // Backend ordering is unstable; without this the cells render right-to-left
  // which reads weirdly when reviewers think in "Ed 1 → Ed 6" terms.
  const sortedEditions = useMemo(() => {
    const numOf = (title) => {
      const m = String(title || '').match(/(\d+)/);
      return m ? Number(m[1]) : Number.POSITIVE_INFINITY;
    };
    return [...editions].sort((a, b) => {
      if (a.title === AVIMAT) return 1;
      if (b.title === AVIMAT) return -1;
      return numOf(a.title) - numOf(b.title);
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

  const applyAllDaily = useCallback(() => {
    const ref = [...placementByEdition.values()].find((v) => v?.pageName);
    const targetName = ref?.pageName || 'pg_1';
    const next = new Map(placementByEdition);
    for (const ed of editions) {
      if (ed.title === AVIMAT) continue;
      const match = ed.pages?.find((p) => p.page_name === targetName);
      if (match) next.set(ed.id, { pageId: match.id, pageName: match.page_name });
    }
    commit(next);
  }, [placementByEdition, editions, commit]);

  const clearAll = useCallback(() => {
    const next = new Map();
    for (const ed of editions) next.set(ed.id, null);
    commit(next);
  }, [editions, commit]);

  const isToday = activeDate === todayIST();

  return (
    <div className="px-3 pb-2">
      {/* Row 1: date stepper. Stays on one line — no wrapping date. */}
      <div className="mb-1.5 flex items-center gap-1">
        <button
          type="button"
          onClick={() => setActiveDate((d) => shiftDate(d, -1))}
          className="flex h-6 w-6 items-center justify-center rounded-md border border-border bg-background text-[12px] leading-none hover:bg-accent"
          aria-label="Previous day"
        >
          ‹
        </button>
        <span className="whitespace-nowrap text-[11px] font-medium tabular-nums">
          {activeDate}
          {isToday && <span className="ml-1 text-[10px] font-normal text-muted-foreground">(today)</span>}
        </span>
        <button
          type="button"
          onClick={() => setActiveDate((d) => shiftDate(d, 1))}
          className="flex h-6 w-6 items-center justify-center rounded-md border border-border bg-background text-[12px] leading-none hover:bg-accent"
          aria-label="Next day"
        >
          ›
        </button>
        {!isToday && (
          <button
            type="button"
            onClick={() => setActiveDate(todayIST())}
            className="ml-1 rounded-md border border-border bg-background px-2 py-0.5 text-[11px] hover:bg-accent"
          >
            Today
          </button>
        )}
        <span className="flex-1" />
        {saving && <span className="text-[10px] text-muted-foreground">saving…</span>}
      </div>

      {/* Row 2: action chips. Separate row so they never collide with the date. */}
      {editions.length > 0 && (
        <div className="mb-2 flex items-center gap-1">
          <button
            type="button"
            onClick={applyAllDaily}
            className="whitespace-nowrap rounded-md border border-border bg-background px-2 py-0.5 text-[11px] hover:bg-accent"
          >
            {t('placements.allDaily')}
          </button>
          <button
            type="button"
            onClick={clearAll}
            className="whitespace-nowrap rounded-md border border-border bg-background px-2 py-0.5 text-[11px] hover:bg-accent"
          >
            {t('placements.clear')}
          </button>
        </div>
      )}

      {loading ? (
        <div className="text-xs text-muted-foreground">{t('common.loading', 'Loading...')}</div>
      ) : !editions.length ? (
        <div className="text-xs text-muted-foreground">
          {t('placements.noEditions', { date: activeDate })}
        </div>
      ) : (
        // Fixed 4-column grid keeps cells aligned. Trailing slots stay empty
        // rather than centring an orphan row, which reads cleaner.
        <div className="grid grid-cols-4 gap-1.5">
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
  return (
    <div className="flex min-w-0 flex-col items-stretch">
      <div className="mb-0.5 truncate text-center text-[10px] font-medium text-muted-foreground">
        {edition.title}
      </div>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            className={cn(
              'w-full rounded border border-border bg-background px-1 py-1 text-center text-xs hover:bg-accent',
              current?.pageName && 'border-primary/40 bg-primary/5 font-medium text-foreground'
            )}
          >
            {current?.pageName || '—'}
          </button>
        </PopoverTrigger>
        <PopoverContent align="start" className="max-h-60 w-40 overflow-y-auto p-1">
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
        </PopoverContent>
      </Popover>
    </div>
  );
}

export default EditionPlacementMatrix;
