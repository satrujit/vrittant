import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Loader2 } from 'lucide-react';
import { useI18n } from '../i18n';
import { fetchReporters, transformReporter } from '../services/api';
import { Avatar, SearchBar } from '../components/common';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
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

function timeAgo(dateStr) {
  if (!dateStr) return '—';
  const now = new Date();
  const d = new Date(dateStr);
  const diffMs = now - d;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'Just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH}h ago`;
  const diffD = Math.floor(diffH / 24);
  if (diffD < 7) return `${diffD}d ago`;
  if (diffD < 30) return `${Math.floor(diffD / 7)}w ago`;
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
}

function UsersTable({ users, navigate, t }) {
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
            <TableHead>Name</TableHead>
            <TableHead>Location</TableHead>
            <TableHead className="text-right">Submissions</TableHead>
            <TableHead className="text-right">Published</TableHead>
            <TableHead>Last Active</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {users.map((user, i) => (
            <TableRow
              key={user.id}
              className={cn(
                i % 2 === 1 ? 'bg-muted/30' : '',
                !user.isActive && 'opacity-50'
              )}
            >
              <TableCell>
                <div className="flex items-center gap-3">
                  <Avatar initials={user.initials} color={user.color} size="sm" />
                  <div className="flex flex-col min-w-0">
                    <span className="text-sm font-medium text-foreground truncate">
                      {user.name}
                    </span>
                    {!user.isActive && (
                      <span className="text-[10px] font-medium text-destructive">
                        Deleted
                      </span>
                    )}
                  </div>
                </div>
              </TableCell>
              <TableCell className="text-sm text-muted-foreground">
                {user.areaName || '—'}
              </TableCell>
              <TableCell className="text-right font-semibold">
                {user.submissionCount}
              </TableCell>
              <TableCell className="text-right font-semibold">
                {user.publishedCount}
              </TableCell>
              <TableCell className="text-sm text-muted-foreground">
                {timeAgo(user.lastActive)}
              </TableCell>
              <TableCell className="text-right">
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-primary hover:text-primary"
                  onClick={() => navigate(`/reporters/${user.id}`)}
                >
                  View
                  <ArrowRight size={14} />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

function ReportersPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [reportersList, setReportersList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showDeleted, setShowDeleted] = useState(false);
  const [tab, setTab] = useState('reporters');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchReporters({ includeInactive: showDeleted })
      .then((data) => {
        if (!cancelled) {
          const transformed = (data.reporters || []).map(transformReporter);
          setReportersList(transformed);
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error('Failed to fetch reporters:', err);
        if (!cancelled) {
          setReportersList([]);
          setLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, [showDeleted]);

  // Filter out org_admin, then split by type
  const { reporters, reviewers } = useMemo(() => {
    const noAdmins = reportersList.filter(r => r.user_type !== 'org_admin');
    let list = noAdmins;
    if (search.trim()) {
      const q = search.toLowerCase();
      list = noAdmins.filter(
        (r) =>
          r.name.toLowerCase().includes(q) ||
          (r.areaName || '').toLowerCase().includes(q)
      );
    }
    return {
      reporters: list.filter(r => r.user_type === 'reporter'),
      reviewers: list.filter(r => r.user_type === 'reviewer'),
    };
  }, [search, reportersList]);

  const activeList = tab === 'reporters' ? reporters : reviewers;

  return (
    <div className="p-6 lg:p-8 max-w-[1400px]">
      {/* Header */}
      <div className="flex items-start justify-between gap-5 mb-6">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold text-foreground leading-tight">
            Users
          </h1>
          <p className="text-sm text-muted-foreground leading-normal">
            Manage reporters and reviewers
          </p>
        </div>
      </div>

      {/* Search + Show deleted */}
      <div className="flex items-center gap-4 mb-6">
        <SearchBar
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t('reporters.searchPlaceholder')}
          className="max-w-[400px]"
        />
        <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer select-none whitespace-nowrap">
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
            <UsersTable users={reporters} navigate={navigate} t={t} />
          </TabsContent>
          <TabsContent value="reviewers">
            <UsersTable users={reviewers} navigate={navigate} t={t} />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}

export default ReportersPage;
