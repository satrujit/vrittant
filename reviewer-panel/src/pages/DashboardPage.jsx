import { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import {
  ChevronLeft,
  ChevronRight,
  MapPin,
  Loader2,
  RefreshCw,
  Clock,
} from 'lucide-react';
import { useI18n } from '../i18n';
import { useAuth } from '../contexts/AuthContext';
import { fetchStats, fetchStories, fetchReporters, transformStory, reassignStory } from '../services/api';
import { Avatar, StatusBadge, CategoryChip, SearchBar, PageHeader } from '../components/common';
import { LayoutDashboard } from 'lucide-react';
import { formatDate, formatTimeAgo } from '../utils/helpers';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import ReassignPopover from '../components/assignment/ReassignPopover';

const PAGE_SIZE = 10;
const REFRESH_INTERVAL = 30_000; // 30 seconds

function formatPublishedCount(n) {
  if (n >= 1000) {
    return (n / 1000).toFixed(1) + 'k';
  }
  return String(n);
}

export default function DashboardPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  // Org admins oversee everyone, so the dashboard queue is org-wide for them.
  // Reviewers see only what's assigned to them (delegated work lives on All Stories).
  const isOrgAdmin = user?.user_type === 'org_admin';
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);

  // API data state
  const [statsData, setStatsData] = useState(null);
  const [stories, setStories] = useState([]);
  const [totalStories, setTotalStories] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [reviewers, setReviewers] = useState([]);
  const intervalRef = useRef(null);

  // Fetch active reviewers once for reassign dropdown
  useEffect(() => {
    fetchReporters()
      .then((data) => {
        const list = data.reporters || [];
        setReviewers(list.filter((u) => u.user_type === 'reviewer' && (u.is_active ?? true)));
      })
      .catch(() => setReviewers([]));
  }, []);

  const handleReassign = useCallback(async (storyId, userId) => {
    const reviewer = reviewers.find((r) => String(r.id) === String(userId));
    setStories((prev) =>
      prev.map((s) =>
        s.id === storyId
          ? {
              ...s,
              assigned_to: userId,
              assignee_id: userId,
              assignee_name: reviewer?.name || s.assignee_name,
              assigned_match_reason: 'manual',
            }
          : s
      )
    );
    try {
      await reassignStory(storyId, userId);
    } catch (err) {
      console.error('Failed to reassign story:', err);
    }
  }, [reviewers]);

  // Fetch stats
  const loadStats = useCallback(async (silent) => {
    if (!silent) setStatsLoading(true);
    try {
      const data = await fetchStats();
      setStatsData(data);
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    } finally {
      if (!silent) setStatsLoading(false);
    }
  }, []);

  // Fetch stats on mount
  useEffect(() => {
    loadStats(false);
  }, [loadStats]);

  // Fetch all submitted stories (pending review)
  const loadStories = useCallback(async (silent) => {
    if (!silent) setLoading(true);
    try {
      const offset = (currentPage - 1) * PAGE_SIZE;
      const params = {
        status: 'submitted',
        offset,
        limit: PAGE_SIZE,
      };
      // Reviewers see only their own queue; org_admins see everyone's
      // pending work (matches the stats card scoping in /admin/stats).
      if (!isOrgAdmin) {
        params.assigned_to = 'me';
      }
      if (searchQuery.trim()) {
        params.search = searchQuery.trim();
      }
      const data = await fetchStories(params);
      const transformed = (data.stories || []).map(transformStory);
      setStories(transformed);
      setTotalStories(data.total || 0);
    } catch (err) {
      console.error('Failed to fetch stories:', err);
      if (!silent) {
        setStories([]);
        setTotalStories(0);
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }, [currentPage, searchQuery, isOrgAdmin]);

  useEffect(() => {
    loadStories(false);
  }, [loadStories]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    intervalRef.current = setInterval(() => {
      setRefreshing(true);
      Promise.all([loadStories(true), loadStats(true)]).finally(() =>
        setRefreshing(false)
      );
    }, REFRESH_INTERVAL);
    return () => clearInterval(intervalRef.current);
  }, [loadStories, loadStats]);

  const totalPages = Math.ceil(totalStories / PAGE_SIZE);
  const startIndex = (currentPage - 1) * PAGE_SIZE;
  const endIndex = Math.min(startIndex + PAGE_SIZE, totalStories);

  const handleSearch = (e) => {
    setSearchQuery(e.target.value);
    setCurrentPage(1);
  };

  const stats = statsData
    ? [
        {
          label: t('dashboard.pendingReview'),
          value: statsData.pending_review ?? 0,
        },
        {
          label: t('dashboard.reviewedToday'),
          value: statsData.reviewed_today ?? 0,
        },
        {
          label: t('dashboard.totalPublished'),
          value: formatPublishedCount(statsData.total_published ?? 0),
        },
        {
          label: 'Avg / Reporter',
          value: statsData.total_reporters
            ? (statsData.total_stories / statsData.total_reporters).toFixed(1)
            : '0',
        },
      ]
    : [];

  return (
    <div className="flex flex-col gap-6 max-w-[1400px] mx-auto p-6 lg:p-8">
      <PageHeader
        icon={LayoutDashboard}
        title={t('dashboard.title')}
        subtitle={t('dashboard.subtitle')}
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setRefreshing(true);
              Promise.all([loadStories(true), loadStats(true)]).finally(() =>
                setRefreshing(false)
              );
            }}
            disabled={refreshing}
          >
            <RefreshCw size={14} className={cn('mr-1.5', refreshing && 'animate-spin')} />
            {t('dashboard.refresh') || 'Refresh'}
          </Button>
        }
        className="mb-0"
      />

      {/* Stats strip — single row, dividers, no card chrome */}
      {statsLoading ? (
        <div className="py-8 text-center text-muted-foreground text-sm border border-border rounded-lg">
          <Loader2 size={20} className="animate-spin inline-block" />
        </div>
      ) : (
        <div className="vr-metric-strip">
          {stats.map((stat) => (
            <div key={stat.label} className="vr-metric-strip__item">
              <span className="vr-metric-strip__label">{stat.label}</span>
              <span className="vr-metric-strip__value">{stat.value}</span>
            </div>
          ))}
        </div>
      )}

      {/* Table Card */}
      <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden">
        {/* Toolbar */}
        <div className="flex items-center gap-2 px-6 py-4 border-b border-border max-sm:px-4 max-sm:py-2">
          <div className="flex-1 max-w-xs">
            <SearchBar
              value={searchQuery}
              onChange={handleSearch}
              placeholder={t('dashboard.searchPlaceholder')}
            />
          </div>
        </div>

        {/* Table */}
        {loading ? (
          <div className="py-16 text-center text-muted-foreground text-sm">
            <Loader2 size={24} className="animate-spin inline-block" />
          </div>
        ) : stories.length === 0 ? (
          <div className="py-16 text-center text-muted-foreground text-sm">
            {t('dashboard.noReports')}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse vr-table-dense">
              <thead>
                <tr>
                  <th className="px-6 py-3 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider text-left border-b border-border whitespace-nowrap max-sm:px-3 max-sm:py-2">
                    {t('table.storyTitle')}
                  </th>
                  <th className="px-6 py-3 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider text-left border-b border-border whitespace-nowrap max-sm:px-3 max-sm:py-2">
                    {t('table.submissionTime')}
                  </th>
                  <th className="px-6 py-3 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider text-left border-b border-border whitespace-nowrap max-sm:px-3 max-sm:py-2">
                    {t('table.category')}
                  </th>
                  <th className="px-6 py-3 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider text-left border-b border-border whitespace-nowrap max-sm:px-3 max-sm:py-2">
                    {t('table.status')}
                  </th>
                  <th className="px-6 py-3 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider text-left border-b border-border whitespace-nowrap max-sm:px-3 max-sm:py-2">
                    {t('assignment.assignedTo')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {stories.map((story) => {
                  const timePrimary = formatDate(story.submittedAt);
                  const timeSecondary = formatTimeAgo(story.submittedAt);

                  return (
                    <tr
                      key={story.id}
                      className="transition-colors hover:bg-accent [&:last-child_td]:border-b-0"
                    >
                      {/* Story title (clickable) + reporter/location metadata */}
                      <td className="px-6 py-3 border-b border-border align-middle max-sm:px-3 max-sm:py-2 max-w-[420px]">
                        <div className="flex flex-col gap-1.5 min-w-[200px]">
                          <Link
                            to={`/review/${story.id}`}
                            className="text-[0.9375rem] font-semibold text-foreground leading-tight line-clamp-1 hover:text-primary transition-colors no-underline"
                          >
                            {story.headline}
                          </Link>
                          <div className="flex items-center gap-1.5">
                            <Avatar
                              initials={story.reporter.initials}
                              color={story.reporter.color}
                              size="sm"
                            />
                            <span className="text-xs text-muted-foreground font-medium">
                              {story.reporter.name}
                            </span>
                            {story.location && (
                              <>
                                <span className="text-xs text-muted-foreground">&middot;</span>
                                <MapPin size={12} className="text-muted-foreground shrink-0" />
                                <span className="text-xs text-muted-foreground">
                                  {story.location}
                                </span>
                              </>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Submission Time — relative w/ clock icon, absolute on hover */}
                      <td className="px-6 py-3 border-b border-border align-middle max-sm:px-3 max-sm:py-2">
                        <span
                          className="inline-flex items-center gap-1 text-xs text-muted-foreground whitespace-nowrap"
                          title={timePrimary}
                        >
                          <Clock size={11} className="shrink-0" />
                          {timeSecondary || timePrimary}
                        </span>
                      </td>

                      {/* Category — dot + label */}
                      <td className="px-6 py-3 border-b border-border align-middle max-sm:px-3 max-sm:py-2">
                        <CategoryChip category={story.category} minimal />
                      </td>

                      {/* Status — dot + label */}
                      <td className="px-6 py-3 border-b border-border align-middle max-sm:px-3 max-sm:py-2">
                        <StatusBadge status={story.status} minimal />
                      </td>

                      {/* Assigned to — inline reassign */}
                      <td className="px-6 py-3 border-b border-border align-middle max-sm:px-3 max-sm:py-2">
                        <ReassignPopover
                          assigneeId={story.assignee_id ?? story.assigned_to}
                          assigneeName={story.assignee_name}
                          matchReason={story.assigned_match_reason}
                          reviewers={reviewers}
                          onReassign={(userId) => handleReassign(story.id, userId)}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {totalStories > 0 && !loading && (
          <div className="flex items-center justify-between px-6 py-3 border-t border-border max-sm:flex-col max-sm:gap-2 max-sm:items-center">
            <span className="text-xs text-muted-foreground">
              {t('dashboard.showingResults', {
                start: startIndex + 1,
                end: endIndex,
                total: totalStories,
              })}
            </span>
            <div className="flex items-center gap-1">
              <Button
                variant="outline"
                size="icon-sm"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                aria-label="Previous page"
              >
                <ChevronLeft size={16} />
              </Button>
              {Array.from({ length: totalPages }, (_, i) => i + 1).map(
                (page) => (
                  <button
                    key={page}
                    className={cn(
                      'inline-flex items-center justify-center min-w-8 h-8 px-2 border rounded-md text-xs font-medium transition-all cursor-pointer',
                      page === currentPage
                        ? 'bg-primary text-primary-foreground border-primary hover:bg-primary/90'
                        : 'bg-card text-foreground border-border hover:bg-accent hover:border-primary/40 hover:text-primary'
                    )}
                    onClick={() => setCurrentPage(page)}
                  >
                    {page}
                  </button>
                )
              )}
              <Button
                variant="outline"
                size="icon-sm"
                onClick={() =>
                  setCurrentPage((p) => Math.min(totalPages, p + 1))
                }
                disabled={currentPage === totalPages}
                aria-label="Next page"
              >
                <ChevronRight size={16} />
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
