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
export function EditionPlacementMatrix({ storyId, publicationDate }) {
  const { t } = useI18n();
  const today = publicationDate || new Date().toISOString().slice(0, 10);

  const [editions, setEditions] = useState([]);
  const [placements, setPlacements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [overrides, setOverrides] = useState(() => new Set());

  // Initial load: editions for the date + current placements.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([
      listTodaysEditions(today),
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
  }, [today, storyId]);

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

  if (loading) {
    return <div className="px-3 pb-2 text-xs text-muted-foreground">{t('common.loading', 'Loading...')}</div>;
  }
  if (!editions.length) {
    return (
      <div className="px-3 pb-2 text-xs text-muted-foreground">
        {t('placements.noEditions', { date: today })}
      </div>
    );
  }

  return (
    <div className="px-3 pb-2">
      <div className="mb-2 flex items-center gap-1.5">
        <button
          type="button"
          onClick={applyAllDaily}
          className="rounded-md border border-border bg-background px-2 py-0.5 text-[11px] hover:bg-accent"
        >
          {t('placements.allDaily')}
        </button>
        <button
          type="button"
          onClick={clearAll}
          className="rounded-md border border-border bg-background px-2 py-0.5 text-[11px] hover:bg-accent"
        >
          {t('placements.clear')}
        </button>
        {saving && (
          <span className="text-[10px] text-muted-foreground">…</span>
        )}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {editions.map((ed) => (
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
    </div>
  );
}

function Cell({ edition, current, onPick, onDrop, dropLabel }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex flex-col items-center">
      <div className="mb-0.5 max-w-[72px] truncate text-[10px] font-medium text-muted-foreground">
        {edition.title}
      </div>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            className={cn(
              'min-w-[60px] rounded border border-border bg-background px-2 py-1 text-xs hover:bg-accent',
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
