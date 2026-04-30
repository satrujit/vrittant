import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  fetchStats, fetchStories, transformStory,
  fetchReporters, fetchOrgUsers, reassignStory,
} from '../services/api';
import { useDensityPreference } from '../hooks/useDensityPreference';
import { useKeyboardRowNav } from '../hooks/useKeyboardRowNav';
import StatStrip from '../components/dashboard/StatStrip';
import FilterBar from '../components/dashboard/FilterBar';
import ReviewQueueTable from '../components/dashboard/ReviewQueueTable';
import DensityToggle from '../components/dashboard/DensityToggle';
import { useI18n } from '../i18n';
import { useAuth } from '../contexts/AuthContext';
import { cn } from '@/lib/utils';

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
  const [reporterFilter, setReporterFilter] = useState('');

  // Pickable lists for the FilterBar's reporter dropdown and the
  // per-row AssigneePicker. Loaded once on mount.
  const [reporters, setReporters] = useState([]);
  const [reviewers, setReviewers] = useState([]);
  useEffect(() => {
    fetchReporters().then((data) => setReporters(data?.reporters || [])).catch(() => {});
    // Anyone who is not a plain reporter can be assigned a story —
    // reviewers, org_admins, etc. fetchOrgUsers returns the active set.
    fetchOrgUsers().then((data) => {
      const list = (data?.users || [])
        .filter((u) => u.user_type !== 'reporter')
        .map((u) => ({ id: u.id, name: u.name }));
      setReviewers(list);
    }).catch(() => {});
  }, []);

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

      // User-driven overrides (filter bar chips + search + category + reporter).
      if (search)         params.search = search;
      if (statusFilter) {
        params.status = statusFilter;
        // If the user picks an explicit status, drop the reviewer-scope
        // exclude so the chip really does what it says.
        delete params.exclude_status;
      }
      if (categoryFilter) params.category = categoryFilter;
      if (reporterFilter) {
        params.reporter_id = reporterFilter;
        // Reporter filter is org-wide intent — drop the reviewer-scope
        // assigned_to so a reviewer can find a specific reporter's
        // stories regardless of who they're assigned to.
        delete params.assigned_to;
        delete params.exclude_status;
      }

      const data = await fetchStories(params);
      setStories((data?.stories || []).map(transformStory));
      setTotal(data?.total ?? 0);
    } catch (err) {
      console.error('Stories failed:', err);
    } finally {
      setStoriesLoading(false);
    }
  }, [search, statusFilter, categoryFilter, reporterFilter, page, user]);

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
  }, [search, statusFilter, categoryFilter, reporterFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  // Polling
  useEffect(() => {
    intervalRef.current = setInterval(() => {
      loadStats();
      loadStories();
    }, REFRESH_INTERVAL);
    return () => clearInterval(intervalRef.current);
  }, [loadStats, loadStories]);

  // Keyboard nav. Status changes are deliberately NOT exposed from the
  // queue table — too easy to misclick / miskey through 25 rows. The review
  // page is the only path for changing a story's status.
  const onOpenRow = useCallback((idx) => {
    const story = stories[idx];
    if (story) navigate(`/review/${story.id}`);
  }, [stories, navigate]);

  const { focusedIndex, setFocusedIndex, handleKeyDown } = useKeyboardRowNav({
    rowCount: stories.length,
    onOpen: onOpenRow,
  });

  // Optimistic reassignment from the queue. Patches the local stories
  // array immediately, fires the API, reverts via re-fetch on failure.
  const handleReassign = useCallback(async (storyId, nextAssigneeId) => {
    const target = reviewers.find((r) => r.id === nextAssigneeId);
    setStories((prev) => prev.map((s) =>
      s.id === storyId
        ? { ...s, assigned_to: nextAssigneeId, assignee_name: target?.name || null }
        : s
    ));
    try {
      await reassignStory(storyId, nextAssigneeId);
    } catch (err) {
      console.error('Reassign failed:', err);
      loadStories(); // revert by re-fetching truth
    }
  }, [reviewers, loadStories]);

  // ── ←/→ pagination ────────────────────────────────────────────────────────
  // Global arrow-key paging on the queue. Skipped while typing in any
  // input/textarea/contenteditable; ignored when ⌘/Ctrl/Alt are held so
  // browser back-forward (Cmd+←/→) still works.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
      const tag = e.target?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      if (e.target?.isContentEditable) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const pageCount = Math.ceil(total / PAGE_SIZE);
      if (e.key === 'ArrowLeft' && page > 0) {
        e.preventDefault();
        setPage(page - 1);
      } else if (e.key === 'ArrowRight' && page + 1 < pageCount) {
        e.preventDefault();
        setPage(page + 1);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [page, total, setPage]);

  // ── Quick-jump by display-id digits ───────────────────────────────────────
  // Type the trailing digits of a story's display id (e.g. "499" for
  // PNS-26-499) and press Enter to open it. The buffer accumulates digits
  // for as long as the reviewer keeps typing; Escape clears, any non-digit
  // non-Enter key cancels (so j/k/↑↓ row nav still feels native). When the
  // buffer is non-empty, useKeyboardRowNav is bypassed for Enter so we don't
  // accidentally open the focused row instead of the typed seq_no.
  const [jumpBuffer, setJumpBuffer] = useState('');
  const jumpBufferRef = useRef('');
  useEffect(() => { jumpBufferRef.current = jumpBuffer; }, [jumpBuffer]);

  const tryJumpToSeq = useCallback((digitsStr) => {
    if (!digitsStr) return false;
    const n = parseInt(digitsStr, 10);
    if (Number.isNaN(n)) return false;
    // Match by exact seq_no first, then by display_id ending in the digits
    // (so "499" matches PNS-26-499 even when the buffer is short).
    let match = stories.find((s) => s.seqNo === n);
    if (!match) {
      match = stories.find((s) => s.display_id?.endsWith(`-${digitsStr}`));
    }
    if (match) {
      navigate(`/review/${match.id}`);
      return true;
    }
    return false;
  }, [stories, navigate]);

  useEffect(() => {
    const onKey = (e) => {
      const tag = e.target?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      if (e.target?.isContentEditable) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      // Digit pressed → append, suppress row-nav handling for this tick.
      if (e.key >= '0' && e.key <= '9') {
        e.preventDefault();
        e.stopPropagation();
        setJumpBuffer((prev) => (prev + e.key).slice(-9));
        return;
      }
      // Active buffer + Enter → open matching story; otherwise let row-nav handle.
      if (e.key === 'Enter' && jumpBufferRef.current) {
        e.preventDefault();
        e.stopPropagation();
        tryJumpToSeq(jumpBufferRef.current);
        setJumpBuffer('');
        return;
      }
      // Active buffer + Backspace → delete one digit.
      if (e.key === 'Backspace' && jumpBufferRef.current) {
        e.preventDefault();
        setJumpBuffer((prev) => prev.slice(0, -1));
        return;
      }
      // Active buffer + Escape → clear.
      if (e.key === 'Escape' && jumpBufferRef.current) {
        e.preventDefault();
        e.stopPropagation();
        setJumpBuffer('');
        return;
      }
      // Any other key while a buffer is active → cancel quietly so row-nav
      // (j/k/↑/↓) doesn't get a stale jump indicator hanging around.
      if (jumpBufferRef.current) {
        setJumpBuffer('');
      }
    };
    // Capture phase so we run before useKeyboardRowNav's window listener.
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [tryJumpToSeq]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const categories = useMemo(
    () => (config?.categories || []).map((c) => c.label || c),
    [config]
  );

  // Whether the typed seq matches anything in the loaded queue. Drives the
  // jump indicator's colour so reviewers see at-a-glance if Enter will land.
  const jumpMatch = useMemo(() => {
    if (!jumpBuffer) return null;
    const n = parseInt(jumpBuffer, 10);
    if (Number.isNaN(n)) return null;
    return (
      stories.find((s) => s.seqNo === n) ||
      stories.find((s) => s.display_id?.endsWith(`-${jumpBuffer}`)) ||
      null
    );
  }, [jumpBuffer, stories]);

  return (
    <div className="flex h-full flex-col">
      {/* Quick-jump indicator — appears bottom-right while the user types
          digits; coral when a match exists in the visible queue, muted when
          not (still typing). Press Enter to commit, Escape to clear. */}
      {jumpBuffer && (
        <div className="pointer-events-none fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm shadow-lg animate-in fade-in slide-in-from-bottom-2">
          <span className="text-muted-foreground">Open</span>
          <span
            className={cn(
              'rounded-md px-1.5 py-0.5 font-mono text-xs font-semibold tabular-nums',
              jumpMatch
                ? 'bg-primary/10 text-primary'
                : 'bg-muted text-muted-foreground',
            )}
          >
            #{jumpBuffer}
          </span>
          {jumpMatch ? (
            <span className="text-xs text-muted-foreground">
              <kbd className="rounded border border-border bg-background px-1 text-[10px]">↵</kbd> to open
            </span>
          ) : (
            <span className="text-[11px] text-muted-foreground">no match</span>
          )}
        </div>
      )}
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
          reporters={reporters}       reporter={reporterFilter}      onReporterChange={setReporterFilter}
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
            reviewers={reviewers}
            onReassign={handleReassign}
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
                aria-label="Previous page"
                className="rounded-md border border-border/60 bg-card px-2 py-1 transition-colors hover:bg-accent disabled:opacity-40 disabled:hover:bg-card"
              >
                ←
              </button>
              <button
                type="button"
                onClick={() => setPage(page + 1)}
                disabled={(page + 1) * PAGE_SIZE >= total}
                aria-label="Next page"
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
