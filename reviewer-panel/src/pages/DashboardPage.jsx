import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
// TODO: per-row reassignment was on the legacy DashboardPage; deferred
// to a follow-up plan. See docs/plans/2026-04-30-dashboard-redesign-design.md
// "Out of scope" section.
import {
  fetchStats, fetchStories, transformStory, updateStoryStatus,
} from '../services/api';
import { useDensityPreference } from '../hooks/useDensityPreference';
import { useKeyboardRowNav } from '../hooks/useKeyboardRowNav';
import { cycleStatus } from '../components/dashboard/inlineStatus';
import StatStrip from '../components/dashboard/StatStrip';
import FilterBar from '../components/dashboard/FilterBar';
import ReviewQueueTable from '../components/dashboard/ReviewQueueTable';
import DensityToggle from '../components/dashboard/DensityToggle';
import { useI18n } from '../i18n';
import { useAuth } from '../contexts/AuthContext';

const PAGE_SIZE = 25;
const REFRESH_INTERVAL = 30_000;

export default function DashboardPage() {
  const { t } = useI18n();
  const { config, user } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Stats
  const [stats, setStats] = useState({ pending_review: 0, reviewed_today: 0, total_published: 0 });
  const [statsLoading, setStatsLoading] = useState(true);

  // Stories
  const [stories, setStories] = useState([]);
  const [storiesLoading, setStoriesLoading] = useState(true);
  const [total, setTotal] = useState(0);

  // Filters
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');

  // Pagination — synced to ?page=N
  const page = Math.max(0, parseInt(searchParams.get('page') || '0', 10));
  const setPage = useCallback((next) => {
    const sp = new URLSearchParams(searchParams);
    if (next > 0) sp.set('page', String(next));
    else sp.delete('page');
    setSearchParams(sp, { replace: true });
  }, [searchParams, setSearchParams]);

  // Preferences
  const [density, setDensity] = useDensityPreference();

  const intervalRef = useRef(null);

  const loadStats = useCallback(async () => {
    try {
      const data = await fetchStats();
      setStats(data);
    } catch (err) {
      console.error('Stats failed:', err);
    } finally {
      setStatsLoading(false);
    }
  }, []);

  const loadStories = useCallback(async () => {
    try {
      const params = { limit: PAGE_SIZE, offset: page * PAGE_SIZE };

      // Role-scoped defaults — same as legacy queue semantics.
      if (user?.user_type === 'org_admin') {
        params.status = 'submitted';
      } else {
        params.assigned_to = 'me';
        params.exclude_status = 'draft,published,rejected';
      }

      // User-driven overrides (filter bar chips + search + category).
      if (search)         params.search = search;
      if (statusFilter) {
        params.status = statusFilter;
        // If the user picks an explicit status, drop the reviewer-scope
        // exclude so the chip really does what it says.
        delete params.exclude_status;
      }
      if (categoryFilter) params.category = categoryFilter;

      const data = await fetchStories(params);
      setStories((data?.stories || []).map(transformStory));
      setTotal(data?.total ?? 0);
    } catch (err) {
      console.error('Stories failed:', err);
    } finally {
      setStoriesLoading(false);
    }
  }, [search, statusFilter, categoryFilter, page, user]);

  // Initial + filter-change fetches
  useEffect(() => { loadStats(); }, [loadStats]);
  useEffect(() => { loadStories(); }, [loadStories]);

  // Whenever the user-driven filters change, reset to page 0. Otherwise
  // switching from "All" to "Flagged" while on ?page=3 requests offset=75
  // against a much smaller filtered set.
  useEffect(() => {
    setPage(0);
    // We deliberately don't depend on `setPage` itself — it's a stable
    // useCallback but that's a fragile assumption to depend on here.
  }, [search, statusFilter, categoryFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  // Polling
  useEffect(() => {
    intervalRef.current = setInterval(() => {
      loadStats();
      loadStories();
    }, REFRESH_INTERVAL);
    return () => clearInterval(intervalRef.current);
  }, [loadStats, loadStories]);

  // Inline status change (optimistic)
  const handleStatusChange = useCallback(async (storyId, nextStatus) => {
    setStories((prev) => prev.map((s) => s.id === storyId ? { ...s, status: nextStatus } : s));
    try {
      await updateStoryStatus(storyId, nextStatus);
      loadStats();
    } catch (err) {
      console.error('Status change failed:', err);
      loadStories(); // revert by re-fetching
    }
  }, [loadStats, loadStories]);

  // Keyboard nav
  const onOpenRow = useCallback((idx) => {
    const story = stories[idx];
    if (story) navigate(`/review/${story.id}`);
  }, [stories, navigate]);
  const onCycleRowStatus = useCallback((idx) => {
    const story = stories[idx];
    if (story) handleStatusChange(story.id, cycleStatus(story.status));
  }, [stories, handleStatusChange]);

  const { focusedIndex, setFocusedIndex, handleKeyDown } = useKeyboardRowNav({
    rowCount: stories.length,
    onOpen: onOpenRow,
    onCycleStatus: onCycleRowStatus,
  });

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const categories = useMemo(
    () => (config?.categories || []).map((c) => c.label || c),
    [config]
  );

  return (
    <div className="flex h-full flex-col">
      {/* Header strip */}
      <header className="flex flex-wrap items-center justify-between gap-4 px-6 pt-6">
        <div className="flex flex-col gap-1">
          <h1 className="text-xl font-semibold tracking-tight text-foreground">
            {t('dashboard.title')}
          </h1>
          <StatStrip
            pending={stats.pending_review}
            reviewedToday={stats.reviewed_today}
            totalPublished={stats.total_published}
            loading={statsLoading}
          />
        </div>
        <DensityToggle value={density} onChange={setDensity} />
      </header>

      {/* Filter bar */}
      <div className="px-6">
        <FilterBar
          search={search}             onSearchChange={setSearch}
          status={statusFilter}       onStatusChange={setStatusFilter}
          categories={categories}     category={categoryFilter}      onCategoryChange={setCategoryFilter}
        />
      </div>

      {/* Table */}
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="flex-1 overflow-y-auto px-6 pb-6">
          <ReviewQueueTable
            stories={stories}
            loading={storiesLoading}
            density={density}
            focusedIndex={focusedIndex}
            onRowFocus={setFocusedIndex}
            onStatusChange={handleStatusChange}
          />
        </div>
        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between border-t border-border/40 px-6 py-2 text-xs text-muted-foreground">
            <span>
              {(page * PAGE_SIZE) + 1}–{Math.min(total, (page + 1) * PAGE_SIZE)} of {total}
            </span>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setPage(page - 1)}
                disabled={page === 0}
                className="rounded-md border border-border/60 bg-card px-2 py-1 transition-colors hover:bg-accent disabled:opacity-40 disabled:hover:bg-card"
              >
                ←
              </button>
              <button
                type="button"
                onClick={() => setPage(page + 1)}
                disabled={(page + 1) * PAGE_SIZE >= total}
                className="rounded-md border border-border/60 bg-card px-2 py-1 transition-colors hover:bg-accent disabled:opacity-40 disabled:hover:bg-card"
              >
                →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
