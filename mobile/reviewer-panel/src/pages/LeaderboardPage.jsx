import { useState, useEffect } from 'react';
import { Loader2, Flame, Star, Zap, Trophy, Award } from 'lucide-react';
import { fetchLeaderboard, getAvatarColor, getInitialsFromName } from '../services/api';
import { Avatar } from '../components/common';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from '@/components/ui/table';
import { cn } from '@/lib/utils';

const PERIODS = [
  { key: 'week', label: 'This Week' },
  { key: 'month', label: 'This Month' },
  { key: 'all', label: 'All Time' },
];

const BADGE_CONFIG = {
  first_story: { icon: Star, label: 'First Story', cls: 'bg-blue-50 text-blue-700' },
  on_fire: { icon: Flame, label: 'On Fire', cls: 'bg-orange-50 text-orange-700' },
  unstoppable: { icon: Zap, label: 'Unstoppable', cls: 'bg-purple-50 text-purple-700' },
  top_reporter: { icon: Trophy, label: 'Top Reporter', cls: 'bg-amber-50 text-amber-700' },
  century: { icon: Award, label: 'Century', cls: 'bg-green-50 text-green-700' },
};

const RANK_STYLES = {
  1: 'bg-amber-100 text-amber-700 border-amber-200',
  2: 'bg-slate-100 text-slate-600 border-slate-200',
  3: 'bg-orange-100 text-orange-700 border-orange-200',
};

function BadgePill({ badgeKey }) {
  const config = BADGE_CONFIG[badgeKey];
  if (!config) return null;
  const Icon = config.icon;
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-semibold rounded-full',
        config.cls
      )}
    >
      <Icon size={10} />
      {config.label}
    </span>
  );
}

function PodiumCard({ entry, rank }) {
  const isFirst = rank === 1;
  const rankStyle = RANK_STYLES[rank] || '';
  const initials = getInitialsFromName(entry.name);
  const color = getAvatarColor(entry.name);

  return (
    <Card
      className={cn(
        'flex flex-col items-center text-center p-6 border transition-all duration-150',
        isFirst ? 'md:-mt-4 md:pb-8 shadow-md border-amber-200' : ''
      )}
    >
      {/* Rank badge */}
      <div
        className={cn(
          'size-8 rounded-full flex items-center justify-center text-sm font-bold mb-3 border',
          rankStyle
        )}
      >
        {rank}
      </div>

      <Avatar initials={initials} color={color} size="lg" />
      <h3 className="text-[0.9375rem] font-semibold text-foreground leading-tight mt-3 mb-1">
        {entry.name}
      </h3>
      {entry.location && (
        <span className="text-xs text-muted-foreground">{entry.location}</span>
      )}

      <span className="text-2xl font-bold text-foreground">{entry.points}</span>
      <span className="text-xs text-muted-foreground mb-2">points</span>

      {entry.streak > 0 && (
        <div className="flex items-center gap-1 text-xs text-orange-600 font-medium mb-2">
          <Flame size={14} />
          {entry.streak} days
        </div>
      )}

      {entry.badges && entry.badges.length > 0 && (
        <div className="flex flex-wrap gap-1 justify-center mt-1">
          {entry.badges.map((b) => (
            <BadgePill key={b} badgeKey={b} />
          ))}
        </div>
      )}
    </Card>
  );
}

function LeaderboardPage() {
  const [period, setPeriod] = useState('month');
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchLeaderboard(period)
      .then((res) => {
        if (!cancelled) {
          // Normalize backend response: map field names to what the UI expects
          const entries = (res.entries || res.leaderboard || []).map((e) => ({
            id: e.reporter_id || e.id,
            name: e.reporter_name || e.name,
            points: e.points,
            submissions: e.submissions,
            approved: e.approved,
            streak: e.current_streak ?? e.streak ?? 0,
            rank: e.rank,
            location: e.location || e.area_name || '',
            badges: (e.badges || []).map((b) => (typeof b === 'string' ? b : b.key)),
          }));
          setData(entries);
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error('Failed to fetch leaderboard:', err);
        if (!cancelled) {
          setData([]);
          setLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, [period]);

  const top3 = data.slice(0, 3);
  const rest = data.slice(3, 10);

  // Reorder for podium display: 2nd | 1st | 3rd
  const podiumOrder = top3.length >= 3
    ? [{ entry: top3[1], rank: 2 }, { entry: top3[0], rank: 1 }, { entry: top3[2], rank: 3 }]
    : top3.map((entry, i) => ({ entry, rank: i + 1 }));

  return (
    <div className="p-6 lg:p-8 max-w-[1400px]">
      {/* Header */}
      <div className="flex flex-col gap-1 mb-6">
        <h1 className="text-2xl font-bold text-foreground leading-tight">
          Leaderboard
        </h1>
        <p className="text-sm text-muted-foreground leading-normal">
          Reporter rankings and achievements
        </p>
      </div>

      {/* Period tabs */}
      <div className="inline-flex items-center bg-muted rounded-lg p-1 mb-8">
        {PERIODS.map((p) => (
          <Button
            key={p.key}
            variant={period === p.key ? 'default' : 'ghost'}
            size="sm"
            className={cn(
              'rounded-md text-xs font-medium',
              period === p.key
                ? ''
                : 'text-muted-foreground hover:text-foreground'
            )}
            onClick={() => setPeriod(p.key)}
          >
            {p.label}
          </Button>
        ))}
      </div>

      {/* Loading */}
      {loading ? (
        <div className="flex items-center justify-center py-16 text-sm text-muted-foreground italic">
          <Loader2 size={24} className="animate-spin" />
        </div>
      ) : data.length === 0 ? (
        <div className="flex items-center justify-center py-16 text-sm text-muted-foreground italic">
          No data available
        </div>
      ) : (
        <>
          {/* Podium */}
          {top3.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:items-end mb-8">
              {podiumOrder.map(({ entry, rank }) => (
                <PodiumCard key={entry.id || entry.name} entry={entry} rank={rank} />
              ))}
            </div>
          )}

          {/* Table for rank 4+ */}
          {rest.length > 0 && (
            <Card className="overflow-hidden p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-16">Rank</TableHead>
                    <TableHead>Reporter</TableHead>
                    <TableHead>Location</TableHead>
                    <TableHead className="text-right">Points</TableHead>
                    <TableHead className="text-right">Submissions</TableHead>
                    <TableHead className="text-right">Approved</TableHead>
                    <TableHead className="text-right">Streak</TableHead>
                    <TableHead>Badges</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rest.map((entry, i) => {
                    const rank = i + 4;
                    const initials = getInitialsFromName(entry.name);
                    const color = getAvatarColor(entry.name);
                    return (
                      <TableRow
                        key={entry.id || entry.name}
                        className={i % 2 === 1 ? 'bg-muted/30' : ''}
                      >
                        <TableCell className="font-medium text-muted-foreground">
                          {rank}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Avatar initials={initials} color={color} size="sm" />
                            <span className="text-sm font-medium text-foreground">
                              {entry.name}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {entry.location || '-'}
                        </TableCell>
                        <TableCell className="text-right font-semibold">
                          {entry.points}
                        </TableCell>
                        <TableCell className="text-right text-muted-foreground">
                          {entry.submissions ?? '-'}
                        </TableCell>
                        <TableCell className="text-right text-muted-foreground">
                          {entry.approved ?? '-'}
                        </TableCell>
                        <TableCell className="text-right">
                          {entry.streak > 0 ? (
                            <div className="inline-flex items-center gap-1 text-xs text-orange-600 font-medium">
                              <Flame size={12} />
                              {entry.streak}d
                            </div>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-1">
                            {(entry.badges || []).map((b) => (
                              <BadgePill key={b} badgeKey={b} />
                            ))}
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

export default LeaderboardPage;
