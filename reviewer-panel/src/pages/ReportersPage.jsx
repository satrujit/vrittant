import { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Loader2, Flame, Trophy } from 'lucide-react';
import { useI18n } from '../i18n';
import {
  fetchReporters,
  transformReporter,
  fetchLeaderboard,
} from '../services/api';
import { Avatar, SearchBar } from '../components/common';
import { Checkbox } from '@/components/ui/checkbox';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
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

const RANK_STYLES = {
  1: 'bg-amber-100 text-amber-700 border-amber-300',
  2: 'bg-slate-100 text-slate-700 border-slate-300',
  3: 'bg-orange-100 text-orange-700 border-orange-300',
};

/**
 * Merged Users + Leaderboard table.
 *
 * Sorted by points (desc) for the selected period; reporters not in the
 * leaderboard appear at the bottom with 0 points. Click a name to open the
 * reporter's detail page — no separate View column.
 */
function UsersTable({ users, t }) {
  if (users.length === 0) {
    return (
      <div className="flex items-center justify-center py-16 text-sm text-muted-foreground italic">
        {t('reporters.noReporters')}
      </div>
    );
  }

  return (
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
          {users.map((user, i) => {
            const rank = i + 1;
            const rankStyle = RANK_STYLES[rank];
            return (
              <TableRow
                key={user.id}
                className={cn(
                  i % 2 === 1 ? 'bg-muted/20' : '',
                  !user.isActive && 'opacity-50'
                )}
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
    </Card>
  );
}

function ReportersPage() {
  const { t } = useI18n();
  const [search, setSearch] = useState('');
  const [reportersList, setReportersList] = useState([]);
  const [leaderboard, setLeaderboard] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showDeleted, setShowDeleted] = useState(false);
  const [tab, setTab] = useState('reporters');
  const [period, setPeriod] = useState('month');

  // Fetch reporters list (people)
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchReporters({ includeInactive: showDeleted })
      .then((data) => {
        if (!cancelled) {
          const transformed = (data.reporters || []).map(transformReporter);
          setReportersList(transformed);
        }
      })
      .catch((err) => {
        console.error('Failed to fetch reporters:', err);
        if (!cancelled) setReportersList([]);
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [showDeleted]);

  // Fetch leaderboard (scores) per period — keyed off period only
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

  // Merge leaderboard scores onto each user, then partition + sort by points desc
  const { reporters, reviewers } = useMemo(() => {
    const scoreById = new Map(
      leaderboard.map((e) => [String(e.id), { points: e.points, streak: e.streak }])
    );

    const noAdmins = reportersList.filter((r) => r.user_type !== 'org_admin');

    const withScores = noAdmins.map((u) => {
      const score = scoreById.get(String(u.id)) || { points: 0, streak: 0 };
      return { ...u, points: score.points, streak: score.streak };
    });

    const q = search.trim().toLowerCase();
    const filtered = q
      ? withScores.filter(
          (r) =>
            r.name.toLowerCase().includes(q) ||
            (r.areaName || '').toLowerCase().includes(q)
        )
      : withScores;

    const sorted = [...filtered].sort((a, b) => {
      if ((b.points ?? 0) !== (a.points ?? 0)) return (b.points ?? 0) - (a.points ?? 0);
      return (b.submissionCount ?? 0) - (a.submissionCount ?? 0);
    });

    return {
      reporters: sorted.filter((r) => r.user_type === 'reporter'),
      reviewers: sorted.filter((r) => r.user_type === 'reviewer'),
    };
  }, [search, reportersList, leaderboard]);

  return (
    <div className="p-6 lg:p-8 max-w-[1400px]">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="flex items-center justify-center size-10 rounded-lg bg-primary/10">
          <Trophy className="size-5 text-primary" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-foreground leading-tight">
            Users
          </h1>
          <p className="text-sm text-muted-foreground">
            Reporters and reviewers, ranked by score
          </p>
        </div>
      </div>

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

        <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer select-none whitespace-nowrap ml-auto">
          <Checkbox
            checked={showDeleted}
            onCheckedChange={(v) => setShowDeleted(!!v)}
          />
          {t('settings.users.showDeleted')}
        </label>
      </div>

      {/* Tabs + Table */}
      {loading ? (
        <div className="flex items-center justify-center py-16 text-sm text-muted-foreground italic">
          <Loader2 size={24} className="animate-spin" />
        </div>
      ) : (
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="mb-4">
            <TabsTrigger value="reporters">
              Reporters
              <span className="ml-1.5 text-xs text-muted-foreground font-normal">
                ({reporters.length})
              </span>
            </TabsTrigger>
            <TabsTrigger value="reviewers">
              Reviewers
              <span className="ml-1.5 text-xs text-muted-foreground font-normal">
                ({reviewers.length})
              </span>
            </TabsTrigger>
          </TabsList>

          <TabsContent value="reporters">
            <UsersTable users={reporters} t={t} />
          </TabsContent>
          <TabsContent value="reviewers">
            <UsersTable users={reviewers} t={t} />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}

export default ReportersPage;
