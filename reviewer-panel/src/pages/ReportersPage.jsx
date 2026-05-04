import { useState, useEffect, useMemo, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Loader2, Flame, ChevronLeft, ChevronRight, Search, X } from 'lucide-react';
import { useI18n } from '../i18n';
import {
  fetchReporters,
  transformReporter,
  fetchLeaderboard,
} from '../services/api';
import { Avatar } from '../components/common';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from '@/components/ui/table';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';

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

/** Compact prev/next pagination with page indicator. */
function Pagination({ currentPage, totalPages, onChange }) {
  if (totalPages <= 1) return null;
  return (
    <div className="flex items-center justify-end gap-2 px-4 py-2 border-t border-border">
      <Button
        variant="outline"
        size="icon-xs"
        onClick={() => onChange(Math.max(1, currentPage - 1))}
        disabled={currentPage === 1}
        aria-label="Previous page"
      >
        <ChevronLeft size={14} />
      </Button>
      <span className="text-xs text-muted-foreground tabular-nums px-1">
        Page {currentPage} of {totalPages}
      </span>
      <Button
        variant="outline"
        size="icon-xs"
        onClick={() => onChange(Math.min(totalPages, currentPage + 1))}
        disabled={currentPage === totalPages}
        aria-label="Next page"
      >
        <ChevronRight size={14} />
      </Button>
    </div>
  );
}

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

      {/* Scrollable region — only the rows scroll; thead is sticky.
          Full-bleed to match Dashboard / All Stories / News Feed. */}
      <div className="flex-1 min-h-0 w-full px-6 pb-6">
      {loading ? (
        <div className="flex items-center justify-center py-16 text-sm text-muted-foreground italic">
          <Loader2 size={24} className="animate-spin" />
        </div>
      ) : reporters.length === 0 ? (
        <div className="flex items-center justify-center py-16 text-sm text-muted-foreground italic">
          {t('reporters.noReporters')}
        </div>
      ) : (
        <Card className="overflow-hidden p-0 h-full flex flex-col">
          <div className="flex-1 min-h-0 overflow-auto">
          <Table>
            <TableHeader className="sticky top-0 z-10 bg-card shadow-[0_1px_0_0_var(--border)]">
              <TableRow>
                <TableHead className="w-14">Rank</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Location</TableHead>
                <TableHead className="text-right">Points</TableHead>
                <TableHead className="text-right">Streak</TableHead>
                <TableHead className="text-right">Submissions</TableHead>
                <TableHead className="text-right">Approved</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {slice.map((user) => {
                const rank = user._rank;
                const rankStyle = RANK_STYLES[rank];
                return (
                  <TableRow
                    key={user.id}
                    className={cn(!user.isActive && 'opacity-50')}
                  >
                    <TableCell>
                      {rankStyle ? (
                        <span
                          className={cn(
                            'inline-flex items-center justify-center size-6 rounded-full border text-xs font-bold',
                            rankStyle
                          )}
                        >
                          {rank}
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground font-medium pl-1.5">
                          {rank}
                        </span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Link
                        to={`/reporters/${user.id}`}
                        className="flex items-center gap-3 group no-underline"
                      >
                        <Avatar initials={user.initials} color={user.color} size="sm" />
                        <div className="flex flex-col min-w-0">
                          <span className="text-sm font-medium text-foreground group-hover:text-primary transition-colors truncate">
                            {user.name}
                          </span>
                          {!user.isActive && (
                            <span className="text-[10px] font-medium text-destructive">
                              Deleted
                            </span>
                          )}
                        </div>
                      </Link>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {user.areaName || '—'}
                    </TableCell>
                    <TableCell className="text-right">
                      <span className="text-sm font-semibold text-foreground tabular-nums">
                        {user.points ?? 0}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      {user.streak > 0 ? (
                        <span className="inline-flex items-center gap-1 text-xs text-orange-600 font-medium tabular-nums">
                          <Flame size={12} />
                          {user.streak}d
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right text-sm text-muted-foreground tabular-nums">
                      {user.submissionCount ?? 0}
                    </TableCell>
                    <TableCell className="text-right text-sm text-muted-foreground tabular-nums">
                      {user.publishedCount ?? 0}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
          </div>
          <div className="shrink-0">
            <Pagination
              currentPage={pageSafe}
              totalPages={totalPages}
              onChange={setPage}
            />
          </div>
        </Card>
      )}
      </div>
    </div>
  );
}

export default ReportersPage;
