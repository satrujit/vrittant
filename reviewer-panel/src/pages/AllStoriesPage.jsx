import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Sparkles,
  MoreHorizontal,
  Trash2,
  X,
} from 'lucide-react';
import { useI18n } from '../i18n';
import { useAuth } from '../contexts/AuthContext';
import { fetchStories, fetchReporters, transformStory, semanticSearchStories, adminDeleteStory, reassignStory } from '../services/api';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { SearchBar, SearchableSelect, Pagination } from '../components/common';
import { formatDate } from '../utils/helpers';
import { assignableReviewers } from '../utils/users';
import { useDensityPreference } from '../hooks/useDensityPreference';
import DensityToggle from '../components/dashboard/DensityToggle';
import ReviewQueueTable from '../components/dashboard/ReviewQueueTable';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import ReassignPopover from '../components/assignment/ReassignPopover';

const PAGE_SIZE = 100;

const ALL_STATUSES = [
  'submitted',
  'approved',
  'rejected',
  'flagged',
  'layout_completed',
  'published',
];


// Default date filter — last 1 day so the page opens on "today's" submissions.
// Users can still widen by clearing the field.
function getYesterdayISO() {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

export default function AllStoriesPage() {
  const { t } = useI18n();
  const { config, user } = useAuth();
  const navigate = useNavigate();
  const isOrgAdmin = user?.user_type === 'org_admin';
  const categoryList = (config?.categories || []).filter(c => c.is_active).map(c => c.key);
  // Shared density preference with the Dashboard — flipping the toggle on
  // either page propagates via localStorage + the density-preference-changed
  // custom event, so the two pages always render at the same density.
  // ReviewQueueTable resolves rowHeight from this internally.
  const [density, setDensity] = useDensityPreference();
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [reporterFilter, setReporterFilter] = useState('');
  const [assigneeFilter, setAssigneeFilter] = useState('');
  const [locationFilter, setLocationFilter] = useState('');
  // Default to yesterday so the page opens on "last 1 day" of submissions.
  // Personal queue scoping moved to the Dashboard — All Stories is org-wide.
  const [dateFrom, setDateFrom] = useState(getYesterdayISO);
  const [dateTo, setDateTo] = useState('');
  // Page lives in the URL (?page=N) so that opening a story and pressing
  // back/Close on the review page restores the same page the user was on,
  // rather than snapping back to page 1 on remount.
  const [searchParams, setSearchParams] = useSearchParams();
  const currentPage = Math.max(1, parseInt(searchParams.get('page') || '1', 10) || 1);
  const setCurrentPage = useCallback((updater) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      const cur = Math.max(1, parseInt(next.get('page') || '1', 10) || 1);
      const value = typeof updater === 'function' ? updater(cur) : updater;
      if (!value || value === 1) next.delete('page');
      else next.set('page', String(value));
      return next;
    }, { replace: true });
  }, [setSearchParams]);

  // API data state
  const [stories, setStories] = useState([]);
  const [totalStories, setTotalStories] = useState(0);
  const [loading, setLoading] = useState(true);
  const [semanticLoading, setSemanticLoading] = useState(false);

  // Reporters list for filter dropdown — also source of reviewers for the
  // assignee filter and inline reassign dropdown (single fetch, two derivations).
  const [reporters, setReporters] = useState([]);
  const [reviewers, setReviewers] = useState([]);
  useEffect(() => {
    fetchReporters()
      .then((data) => {
        const list = data.reporters || [];
        setReporters(list);
        setReviewers(assignableReviewers(list));
      })
      .catch(() => {
        setReporters([]);
        setReviewers([]);
      });
  }, []);

  // Search submits on Enter only (not on every keystroke). Semantic
  // search hits an LLM endpoint and AI-translates non-Odia queries — both
  // are slow and metered, so per-keystroke firing was burning quota and
  // returning stale results. Reporters get instant local typing feedback;
  // the actual fetch fires when they press Enter.
  const handleSearch = (e) => {
    setSearchQuery(e.target.value);
  };

  const submitSearch = () => {
    setCurrentPage(1);
    setDebouncedSearch(searchQuery.trim());
  };

  const handleSearchKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      submitSearch();
    }
  };

  // True when the user has typed something they haven't applied yet.
  // Used to surface a small "press ↵" hint so the gap between input
  // and results doesn't feel broken.
  const hasPendingSearch = searchQuery.trim() !== debouncedSearch.trim();

  // Fetch stories when filters or page change — exclude drafts by default
  const loadStories = useCallback(async () => {
    setLoading(true);
    try {
      const offset = (currentPage - 1) * PAGE_SIZE;
      const hasFilters = statusFilter || categoryFilter || reporterFilter || assigneeFilter || locationFilter || dateFrom || dateTo;
      const useSemanticSearch = debouncedSearch.trim() && !hasFilters;

      if (useSemanticSearch) {
        // AI-powered semantic search (no additional filters)
        setSemanticLoading(true);
        const data = await semanticSearchStories({ q: debouncedSearch.trim(), offset, limit: PAGE_SIZE });
        const transformed = (data.stories || []).map(transformStory);
        setStories(transformed);
        setTotalStories(data.total || 0);
        setSemanticLoading(false);
      } else {
        // Regular ILIKE search with filters
        setSemanticLoading(false);
        const params = {
          recent: false,
          offset,
          limit: PAGE_SIZE,
        };
        if (debouncedSearch.trim()) params.search = debouncedSearch.trim();
        // If no status filter is selected, exclude drafts
        if (statusFilter) {
          params.status = statusFilter;
        } else {
          params.exclude_status = 'draft';
        }
        if (categoryFilter) params.category = categoryFilter;
        if (reporterFilter) params.reporter_id = reporterFilter;
        if (assigneeFilter) params.assigned_to = assigneeFilter;
        if (locationFilter) params.location = locationFilter;
        if (dateFrom) params.date_from = dateFrom;
        if (dateTo) params.date_to = dateTo;

        const data = await fetchStories(params);
        const transformed = (data.stories || []).map(transformStory);
        setStories(transformed);
        setTotalStories(data.total || 0);
      }
    } catch (err) {
      console.error('Failed to fetch stories:', err);
      setStories([]);
      setTotalStories(0);
      setSemanticLoading(false);
    } finally {
      setLoading(false);
    }
  }, [currentPage, debouncedSearch, statusFilter, categoryFilter, reporterFilter, assigneeFilter, locationFilter, dateFrom, dateTo]);

  useEffect(() => {
    loadStories();
  }, [loadStories]);

  const totalPages = Math.ceil(totalStories / PAGE_SIZE);
  const startIndex = (currentPage - 1) * PAGE_SIZE;
  const endIndex = Math.min(startIndex + PAGE_SIZE, totalStories);

  const handleStatusChange = (val) => {
    setStatusFilter(val);
    setCurrentPage(1);
  };

  const handleCategoryChange = (val) => {
    setCategoryFilter(val);
    setCurrentPage(1);
  };

  const handleReporterChange = (val) => {
    setReporterFilter(val);
    setCurrentPage(1);
  };

  const handleAssigneeChange = (val) => {
    setAssigneeFilter(val);
    setCurrentPage(1);
  };

  const handleLocationChange = (val) => {
    setLocationFilter(val);
    setCurrentPage(1);
  };

  const handleReassign = async (storyId, userId) => {
    // Optimistic update — patch the row, then refetch in background to
    // pull the canonical assignee_name + assigned_match_reason.
    const reviewer = reviewers.find((r) => String(r.id) === String(userId));
    setStories((prev) =>
      prev.map((s) =>
        s.id === storyId
          ? {
              ...s,
              assignee_id: userId,
              assignee_name: reviewer?.name || s.assignee_name,
              assigned_match_reason: 'manual',
            }
          : s
      )
    );
    try {
      await reassignStory(storyId, userId);
      await loadStories();
    } catch (err) {
      console.error('Failed to reassign story:', err);
      // On failure, refetch to revert the optimistic patch.
      await loadStories();
    }
  };

  const handleDateFromChange = (e) => {
    setDateFrom(e.target.value);
    setCurrentPage(1);
  };

  const handleDateToChange = (e) => {
    setDateTo(e.target.value);
    setCurrentPage(1);
  };

  // Show "Clear" whenever ANY filter has a value — including the default
  // dateFrom (yesterday), since the user may want to clear that too. Keeps
  // the affordance always discoverable instead of conditional.
  const hasActiveFilters = !!(
    statusFilter ||
    categoryFilter ||
    reporterFilter ||
    assigneeFilter ||
    locationFilter ||
    dateFrom ||
    dateTo ||
    searchQuery
  );

  const handleClearFilters = () => {
    setStatusFilter('');
    setCategoryFilter('');
    setReporterFilter('');
    setAssigneeFilter('');
    setLocationFilter('');
    setDateFrom('');
    setDateTo('');
    setSearchQuery('');
    setDebouncedSearch('');
    setCurrentPage(1);
  };

  // Derive unique locations from reporters
  const uniqueLocations = [...new Set(reporters.map((r) => r.area_name).filter(Boolean))];

  const handleDeleteStory = async (storyId) => {
    // eslint-disable-next-line no-alert
    if (!window.confirm(t('stories.delete.confirm'))) return;
    try {
      await adminDeleteStory(storyId);
      await loadStories();
    } catch (err) {
      console.error('Failed to delete story:', err);
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Header strip — matches DashboardPage's pattern: inline title on
          the left, DensityToggle on the right. The PageHeader component
          (used elsewhere) was replaced here so the two queue-style pages
          (Dashboard + All Stories) read as the same product visually. */}
      <header className="shrink-0 flex flex-wrap items-center justify-between gap-4 px-6 pt-6">
        <div className="flex flex-col gap-0.5 min-w-0">
          <h1 className="text-xl font-semibold tracking-tight text-foreground truncate">
            {t('allStories.title')}
          </h1>
          <p className="text-[12.5px] text-muted-foreground">
            {t('allStories.subtitle')}
          </p>
        </div>
        <DensityToggle value={density} onChange={setDensity} />
      </header>

      {/* Filter row + scrollable table region.  Outer wrapper drops the
          max-w-[1400px] cap to match Dashboard's full-bleed table. */}
      <div className="shrink-0 px-6 pt-3 pb-2 flex flex-col gap-3">
        {/* (filter row contents follow — wrapper preserved so the
            existing closing markup downstream stays balanced.) */}
        {/* Filters Row — compact inline. Search bar now lives at the
            far right of the same row (ml-auto pushes it over) so the
            page header stays a single tidy strip instead of stacking. */}
        <div className="flex items-end gap-3 flex-wrap max-[900px]:flex-col max-[900px]:items-stretch">
          <div className="flex flex-col gap-0.5 max-[900px]:min-w-0">
            <Label className="text-[10px] font-medium text-muted-foreground uppercase tracking-[0.04em]">
              {t('allStories.filterByStatus')}
            </Label>
            <SearchableSelect
              triggerClassName="min-w-[120px]"
              value={statusFilter}
              onChange={handleStatusChange}
              placeholder={t('allStories.all')}
              allLabel={t('allStories.all')}
              options={ALL_STATUSES.map((s) => ({
                value: s,
                label: t(`status.${s === 'layout_completed' ? 'layoutCompleted' : s}`),
              }))}
            />
          </div>

          <div className="flex flex-col gap-0.5 max-[900px]:min-w-0">
            <Label className="text-[10px] font-medium text-muted-foreground uppercase tracking-[0.04em]">
              {t('allStories.filterByCategory')}
            </Label>
            <SearchableSelect
              triggerClassName="min-w-[120px]"
              value={categoryFilter}
              onChange={handleCategoryChange}
              placeholder={t('allStories.all')}
              allLabel={t('allStories.all')}
              options={categoryList.map((c) => {
                const localized = t(`categories.${c}`);
                const label = localized !== `categories.${c}` ? localized : c.replace(/_/g, ' ');
                return { value: c, label };
              })}
            />
          </div>

          <div className="flex flex-col gap-0.5 max-[900px]:min-w-0">
            <Label className="text-[10px] font-medium text-muted-foreground uppercase tracking-[0.04em]">
              {t('allStories.filterByReporter')}
            </Label>
            <SearchableSelect
              triggerClassName="min-w-[140px]"
              value={reporterFilter}
              onChange={handleReporterChange}
              placeholder={t('allStories.all')}
              allLabel={t('allStories.all')}
              options={reporters.map((r) => ({ value: String(r.id), label: r.name }))}
            />
          </div>

          {/* #57 — "Assigned to" filter, restored after the rebuild. Backed
              by the same reviewer pool the inline reassign popover uses
              (assignableReviewers(reporters)) so the dropdown can never
              offer a user who can't actually own a story. Maps to the
              backend's `assigned_to` query param (also accepts 'me' but
              we expose explicit user picks here — the dashboard already
              covers the personal queue case). */}
          <div className="flex flex-col gap-0.5 max-[900px]:min-w-0">
            <Label className="text-[10px] font-medium text-muted-foreground uppercase tracking-[0.04em]">
              {t('allStories.filterByAssignee', 'Assigned to')}
            </Label>
            <SearchableSelect
              triggerClassName="min-w-[140px]"
              value={assigneeFilter}
              onChange={handleAssigneeChange}
              placeholder={t('allStories.all')}
              allLabel={t('allStories.all')}
              options={reviewers.map((r) => ({ value: String(r.id), label: r.name }))}
            />
          </div>

          <div className="flex flex-col gap-0.5 max-[900px]:min-w-0">
            <Label className="text-[10px] font-medium text-muted-foreground uppercase tracking-[0.04em]">
              {t('allStories.filterByLocation')}
            </Label>
            <SearchableSelect
              triggerClassName="min-w-[120px]"
              value={locationFilter}
              onChange={handleLocationChange}
              placeholder={t('allStories.all')}
              allLabel={t('allStories.all')}
              options={uniqueLocations.map((loc) => ({ value: loc, label: loc }))}
            />
          </div>

          <div className="flex flex-col gap-0.5 min-w-[120px] max-[900px]:min-w-0">
            <Label className="text-[10px] font-medium text-muted-foreground uppercase tracking-[0.04em]">
              {t('allStories.dateFrom')}
            </Label>
            <Input
              type="date"
              className="h-8 text-xs"
              value={dateFrom}
              onChange={handleDateFromChange}
            />
          </div>

          <div className="flex flex-col gap-0.5 min-w-[120px] max-[900px]:min-w-0">
            <Label className="text-[10px] font-medium text-muted-foreground uppercase tracking-[0.04em]">
              {t('allStories.dateTo')}
            </Label>
            <Input
              type="date"
              className="h-8 text-xs"
              value={dateTo}
              onChange={handleDateToChange}
            />
          </div>

          {hasActiveFilters && (
            <Button
              variant="ghost"
              size="xs"
              onClick={handleClearFilters}
              className="h-8 text-muted-foreground hover:text-foreground"
            >
              <X size={12} />
              {t('allStories.clearFilters')}
            </Button>
          )}

          {/* Search — right-aligned via ml-auto. Submits on Enter only
              (semantic search is metered + slow). The "press ↵" hint and
              "AI searching..." spinner are mutually exclusive: one shows
              what hasn't been applied yet, the other shows what's in
              flight. */}
          <div className="relative ml-auto w-full max-w-[280px] max-[900px]:ml-0 max-[900px]:max-w-none">
            <SearchBar
              value={searchQuery}
              onChange={handleSearch}
              onKeyDown={handleSearchKeyDown}
              placeholder={t('allStories.searchPlaceholder')}
              icon={Sparkles}
            />
            {semanticLoading ? (
              <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1 text-primary">
                <Sparkles size={12} className="animate-pulse" />
                <span className="text-[10px] font-medium">AI…</span>
              </div>
            ) : hasPendingSearch ? (
              <kbd className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                ↵
              </kbd>
            ) : null}
          </div>
        </div>
      </div>

      {/* Scrollable region — same ReviewQueueTable component the
          Dashboard uses, so the 5 base columns (Title / Submitted /
          Category / Reporter / Status) render pixel-identically across
          both pages. Three extra columns (Reviewed by / Assigned to /
          Actions) append after Status via the new extraColumns slot —
          they're the editorial-signal columns All Stories needs that
          the Dashboard doesn't (Dashboard filters to "submitted" only,
          so reviewer + assignee + admin actions don't apply yet). */}
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="flex-1 min-h-0 overflow-auto px-6">
          <ReviewQueueTable
            stories={stories}
            loading={loading}
            density={density}
            extraColumns={[
              {
                // Reviewed by — name on top, time stacked below (same
                // two-line treatment Dashboard uses for Submitted, so
                // metadata-pair columns share a vertical rhythm).
                id: 'reviewed-by',
                header: t('stories.reviewedBy'),
                width: '140px',
                render: (story) => (
                  story.reviewer_name ? (
                    <div className="flex flex-col gap-0.5 min-w-0">
                      <span
                        className="text-[13px] text-foreground truncate"
                        title={story.reviewer_name}
                      >
                        {story.reviewer_name}
                      </span>
                      {story.reviewed_at && (
                        <span className="text-[11px] text-muted-foreground truncate">
                          {formatDate(story.reviewed_at)}
                        </span>
                      )}
                    </div>
                  ) : (
                    <span className="text-xs text-muted-foreground">—</span>
                  )
                ),
              },
              {
                // Assigned to — inline reassign popover. stopRowClick lets
                // the popover handle its own clicks without bubbling up to
                // the row-level navigate(`/review/${id}`) handler.
                id: 'assigned-to',
                header: t('assignment.assignedTo'),
                width: '160px',
                stopRowClick: true,
                render: (story) => (
                  <ReassignPopover
                    assigneeId={story.assignee_id}
                    assigneeName={story.assignee_name}
                    matchReason={story.assigned_match_reason}
                    reviewers={reviewers}
                    onReassign={(userId) => handleReassign(story.id, userId)}
                  />
                ),
              },
              ...(isOrgAdmin
                ? [{
                    // Per-row admin menu (currently just Delete). Conditional
                    // — non-admin users don't get the column at all so the
                    // table tightens up instead of showing an empty cell.
                    id: 'admin-actions',
                    header: '',
                    width: '50px',
                    stopRowClick: true,
                    render: (story) => (
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreHorizontal className="w-4 h-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            onClick={() => handleDeleteStory(story.id)}
                            className="text-destructive focus:text-destructive"
                          >
                            <Trash2 className="w-4 h-4 mr-2" />
                            {t('stories.delete.action')}
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    ),
                  }]
                : []),
            ]}
          />
        </div>


        {/* Pagination — lighter divider (border-border/40) to match
            Dashboard's footer chrome. The result-range count sits left,
            the page navigator right, both inline rather than card-fenced. */}
        {totalStories > 0 && !loading && (
          <div className="shrink-0 flex items-center justify-between border-t border-border/40 px-6 py-2 text-xs text-muted-foreground max-sm:flex-col max-sm:gap-3 max-sm:items-center">
            <span>
              {t('dashboard.showingResults', {
                start: startIndex + 1,
                end: endIndex,
                total: totalStories,
              })}
            </span>
            <Pagination
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={setCurrentPage}
            />
          </div>
        )}
      </div>
    </div>
  );
}
