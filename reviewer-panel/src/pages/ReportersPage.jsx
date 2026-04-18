import { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Loader2, Flame, Trophy, ChevronLeft, ChevronRight } from 'lucide-react';
import { useI18n } from '../i18n';
import {
  fetchReporters,
  transformReporter,
  fetchLeaderboard,
} from '../services/api';
import { Avatar, SearchBar, PageHeader } from '../components/common';
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
  const [page, setPage] = useState(1);

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
    <div className="p-6 lg:p-8 max-w-[1400px]">
      <PageHeader
        icon={Trophy}
        title="Reporters"
        subtitle="Reporters ranked by score"
      />

      {/* Toolbar — search · period · show deleted */}
      <div className="flex items-center gap-3 mb-5 flex-wrap">
        <SearchBar
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t('reporters.searchPlaceholder')}
          className="max-w-[320px] flex-1 min-w-[200px]"
        />

        <div className="inline-flex items-center bg-muted rounded-lg p-1">
          {PERIODS.map((p) => (
            <Button
              key={p.key}
              variant={period === p.key ? 'default' : 'ghost'}
              size="sm"
              className={cn(
                'h-7 px-3 rounded-md text-xs font-medium',
                period === p.key ? '' : 'text-muted-foreground hover:text-foreground'
              )}
              onClick={() => setPeriod(p.key)}
            >
              {p.label}
            </Button>
          ))}
        </div>

      </div>

      {/* Table */}
      {loading ? (
        <div className="flex items-center justify-center py-16 text-sm text-muted-foreground italic">
          <Loader2 size={24} className="animate-spin" />
        </div>
      ) : reporters.length === 0 ? (
        <div className="flex items-center justify-center py-16 text-sm text-muted-foreground italic">
          {t('reporters.noReporters')}
        </div>
      ) : (
        <Card className="overflow-hidden p-0">
          <Table>
            <TableHeader>
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
          <Pagination
            currentPage={pageSafe}
            totalPages={totalPages}
            onChange={setPage}
          />
        </Card>
      )}
    </div>
  );
}

export default ReportersPage;
