import { useState, useEffect, useMemo, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Flame, Search, X } from 'lucide-react';
import { useI18n } from '../i18n';
import {
  fetchReporters,
  transformReporter,
  fetchLeaderboard,
} from '../services/api';
import { Avatar, Pagination } from '../components/common';
import { cn } from '@/lib/utils';

// Column geometry — header and rows MUST use the same string so the
// columns line up. Same chrome as ReviewQueueTable / NewsFeedTable —
// title-equivalent column gets flex space, numerics are fixed widths.
const GRID_COLS =
  '60px minmax(0,2.5fr) minmax(0,1.5fr) 90px 90px 110px 110px';

const PERIODS = [
  { key: 'week', label: 'This Week' },
  { key: 'month', label: 'This Month' },
  { key: 'all', label: 'All Time' },
];

const PAGE_SIZE = 20;

const RANK_STYLES = {
  1: 'bg-amber-100 text-amber-700 border-amber-300',
  2: 'bg-slate-100 text-slate-700 border-slate-300',
  3: 'bg-orange-100 text-orange-700 border-orange-300',
};

/**
 * Reporters page — leaderboard view.
 *
 * Reviewers are managed under Settings → Users; they don't have points or
 * streaks (those are reporter-only signals), so we don't surface them here.
 */
function ReportersPage() {
  const { t } = useI18n();
  const [search, setSearch] = useState('');
  const [reportersList, setReportersList] = useState([]);
  const [leaderboard, setLeaderboard] = useState([]);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState('month');
  // Page lives in the URL so opening a reporter detail and returning
  // restores the same page (instead of snapping back to page 1).
  const [searchParams, setSearchParams] = useSearchParams();
  const page = Math.max(1, parseInt(searchParams.get('page') || '1', 10) || 1);
  const setPage = useCallback((updater) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      const cur = Math.max(1, parseInt(next.get('page') || '1', 10) || 1);
      const value = typeof updater === 'function' ? updater(cur) : updater;
      if (!value || value === 1) next.delete('page');
      else next.set('page', String(value));
      return next;
    }, { replace: true });
  }, [setSearchParams]);

  // Fetch users
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchReporters({ includeInactive: false })
      .then((data) => {
        if (!cancelled) {
          setReportersList((data.reporters || []).map(transformReporter));
        }
      })
      .catch((err) => {
        console.error('Failed to fetch reporters:', err);
        if (!cancelled) setReportersList([]);
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  // Fetch leaderboard scores per period
  useEffect(() => {
    let cancelled = false;
    fetchLeaderboard(period)
      .then((res) => {
        if (cancelled) return;
        const entries = (res.entries || res.leaderboard || []).map((e) => ({
          id: e.reporter_id || e.id,
          points: e.points ?? 0,
          streak: e.current_streak ?? e.streak ?? 0,
        }));
        setLeaderboard(entries);
      })
      .catch((err) => {
        console.error('Failed to fetch leaderboard:', err);
        if (!cancelled) setLeaderboard([]);
      });
    return () => { cancelled = true; };
  }, [period]);

  // Reset page when filters change so user isn't stranded on an empty page
  useEffect(() => { setPage(1); }, [search, period]);

  // Merge + filter to reporters only, sorted by points desc
  const reporters = useMemo(() => {
    const scoreById = new Map(
      leaderboard.map((e) => [String(e.id), { points: e.points, streak: e.streak }])
    );

    const onlyReporters = reportersList.filter((r) => r.user_type === 'reporter');

    const q = search.trim().toLowerCase();
    const filtered = q
      ? onlyReporters.filter(
          (r) =>
            r.name.toLowerCase().includes(q) ||
            (r.areaName || '').toLowerCase().includes(q)
        )
      : onlyReporters;

    return filtered
      .map((u) => {
        const score = scoreById.get(String(u.id)) || { points: 0, streak: 0 };
        return { ...u, points: score.points, streak: score.streak };
      })
      .sort((a, b) => {
        if ((b.points ?? 0) !== (a.points ?? 0)) return (b.points ?? 0) - (a.points ?? 0);
        return (b.submissionCount ?? 0) - (a.submissionCount ?? 0);
      })
      // Assign rank in the fully sorted list so pagination doesn't break it.
      .map((u, i) => ({ ...u, _rank: i + 1 }));
  }, [search, reportersList, leaderboard]);

  const totalPages = Math.max(1, Math.ceil(reporters.length / PAGE_SIZE));
  const pageSafe = Math.min(page, totalPages);
  const slice = reporters.slice((pageSafe - 1) * PAGE_SIZE, pageSafe * PAGE_SIZE);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Header strip — matches Dashboard / All Stories / News Feed: inline
          title on the left, no PageHeader card. Full-bleed (drops the
          max-w-[1400px] cap) so the leaderboard table aligns with the
          other queue pages. */}
      <header className="shrink-0 flex flex-wrap items-center justify-between gap-4 px-6 pt-6">
        <div className="flex flex-col gap-0.5 min-w-0">
          <h1 className="text-xl font-semibold tracking-tight text-foreground truncate">
            {t('reporters.title', 'Reporters')}
          </h1>
          <p className="text-[12.5px] text-muted-foreground">
            {t('reporters.subtitle', 'Reporters ranked by score')}
          </p>
        </div>
      </header>

      {/* Filter strip — same compact chrome as the other queue pages
          (h-7, text-[11.5px], gap-1.5, border-b underline). Search left,
          period chips next to it, clear button when search is set. */}
      <div className="shrink-0 px-6 pt-3 pb-2">
        <div className="flex flex-wrap items-center gap-1.5 border-b border-border/60 px-1 py-2.5">
          <div className="relative">
            <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t('reporters.searchPlaceholder')}
              className="h-7 w-44 rounded-md border border-border/60 bg-card pl-7 pr-7 text-[11.5px] outline-none transition-colors focus:border-ring focus:shadow-[0_0_0_3px_rgba(250,108,56,0.08)]"
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch('')}
                className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-0.5 text-muted-foreground hover:bg-accent"
                aria-label="Clear search"
              >
                <X size={12} />
              </button>
            )}
          </div>

          {/* Period chips — segmented control matching Dashboard's status
              filter and News Feed's quick-source strip. Kept as chips
              (not a dropdown) because three options is the chip sweet
              spot and "this week / month / all-time" reads at a glance. */}
          <div className="flex items-center gap-0.5 rounded-md border border-border/60 bg-card p-0.5">
            {PERIODS.map((p) => (
              <button
                key={p.key}
                type="button"
                onClick={() => setPeriod(p.key)}
                aria-pressed={period === p.key}
                className={cn(
                  'rounded-[5px] px-2 py-1 text-[11.5px] font-medium transition-colors',
                  period === p.key
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-accent hover:text-foreground',
                )}
              >
                {p.label}
              </button>
            ))}
          </div>

          {search && (
            <button
              type="button"
              onClick={() => setSearch('')}
              className="inline-flex h-7 items-center gap-1 rounded-md px-2 text-[11.5px] text-muted-foreground hover:bg-accent hover:text-foreground"
            >
              <X size={12} />
              {t('allStories.clearFilters', 'Clear')}
            </button>
          )}
        </div>
      </div>

      {/* Table + pagination region — same shape as the other queue
          pages: scrollable rows, sticky header, lightweight footer
          with the result-range count + pager. No Card wrapper, no
          shadcn <Table> — uses the role="grid" pattern shared with
          ReviewQueueTable / NewsFeedTable. */}
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="flex-1 min-h-0 overflow-auto px-6">
          {loading && reporters.length === 0 ? (
            <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
              {t('common.loading') || 'Loading…'}
            </div>
          ) : !loading && reporters.length === 0 ? (
            <div className="flex h-40 flex-col items-center justify-center gap-1 text-sm text-muted-foreground">
              <span className="text-base font-medium text-foreground">
                {t('reporters.noReporters')}
              </span>
            </div>
          ) : (
            <div role="grid" className="divide-y divide-border/80">
              {/* Sticky header — same chrome as ReviewQueueTable. */}
              <div
                className="sticky top-0 z-10 grid items-center gap-4 bg-background/95 px-4 text-[11px] font-medium uppercase tracking-wider text-muted-foreground backdrop-blur"
                style={{ gridTemplateColumns: GRID_COLS, height: 36 }}
              >
                <div>Rank</div>
                <div>Name</div>
                <div>Location</div>
                <div className="text-right">Points</div>
                <div className="text-right">Streak</div>
                <div className="text-right">Submissions</div>
                <div className="text-right">Approved</div>
              </div>

              {slice.map((user) => {
                const rank = user._rank;
                const rankStyle = RANK_STYLES[rank];
                return (
                  <Link
                    key={user.id}
                    to={`/reporters/${user.id}`}
                    role="row"
                    data-row-id={user.id}
                    className={cn(
                      'group grid items-center gap-4 px-4 no-underline transition-colors hover:bg-accent/40',
                      !user.isActive && 'opacity-50',
                    )}
                    style={{ gridTemplateColumns: GRID_COLS, height: 56 }}
                  >
                    <div>
                      {rankStyle ? (
                        <span
                          className={cn(
                            'inline-flex items-center justify-center size-6 rounded-full border text-xs font-bold',
                            rankStyle,
                          )}
                        >
                          {rank}
                        </span>
                      ) : (
                        <span className="pl-1.5 text-xs font-medium text-muted-foreground tabular-nums">
                          {rank}
                        </span>
                      )}
                    </div>
                    <div className="flex min-w-0 items-center gap-3">
                      <Avatar initials={user.initials} color={user.color} size="sm" />
                      <div className="flex min-w-0 flex-col">
                        <span className="truncate text-[13.5px] font-medium text-foreground transition-colors group-hover:text-primary">
                          {user.name}
                        </span>
                        {!user.isActive && (
                          <span className="text-[10px] font-medium text-destructive">
                            Deleted
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="truncate text-xs text-muted-foreground">
                      {user.areaName || '—'}
                    </div>
                    <div className="text-right text-[13px] font-semibold tabular-nums text-foreground">
                      {user.points ?? 0}
                    </div>
                    <div className="text-right">
                      {user.streak > 0 ? (
                        <span className="inline-flex items-center gap-1 text-xs font-medium tabular-nums text-orange-600">
                          <Flame size={12} />
                          {user.streak}d
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </div>
                    <div className="text-right text-xs tabular-nums text-muted-foreground">
                      {user.submissionCount ?? 0}
                    </div>
                    <div className="text-right text-xs tabular-nums text-muted-foreground">
                      {user.publishedCount ?? 0}
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </div>

        {/* Pagination footer — matches AllStoriesPage exactly: result
            range count left, pager right, lightweight border-t/40. */}
        {reporters.length > 0 && !loading && (
          <div className="flex shrink-0 items-center justify-between border-t border-border/40 px-6 py-2 text-xs text-muted-foreground max-sm:flex-col max-sm:items-center max-sm:gap-3">
            <span>
              {((pageSafe - 1) * PAGE_SIZE) + 1}–{Math.min(reporters.length, pageSafe * PAGE_SIZE)} of {reporters.length}
            </span>
            <Pagination
              currentPage={pageSafe}
              totalPages={totalPages}
              onPageChange={setPage}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export default ReportersPage;
