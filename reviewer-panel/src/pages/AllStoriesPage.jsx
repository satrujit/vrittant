import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  Sparkles,
  ChevronLeft,
  ChevronRight,
  MapPin,
  Loader2,
  MoreHorizontal,
  Trash2,
  Clock,
  X,
  Archive,
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
import { Avatar, StatusBadge, CategoryChip, SearchBar, SearchableSelect, PageHeader } from '../components/common';
import { formatDate, formatTimeAgo } from '../utils/helpers';
import { assignableReviewers } from '../utils/users';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
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
    <div className="flex h-full flex-col overflow-hidden">
      {/* Fixed top: page header + filter row. The scrollable region
          below contains only the story rows so reviewers can keep the
          filters in view while paging through long lists. */}
      <div className="shrink-0 max-w-[1400px] mx-auto w-full px-6 lg:px-8 pt-6 lg:pt-8 pb-3 flex flex-col gap-4">
        <PageHeader
          icon={Archive}
          title={t('allStories.title')}
          subtitle={t('allStories.subtitle')}
          className="mb-0"
        />
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

      {/* Scrollable region: only the rows scroll. The Table header stays
          pinned via `sticky top-0` against the scroll container below,
          and pagination sits at the bottom of the card (shrink-0). */}
      <div className="flex-1 min-h-0 max-w-[1400px] mx-auto w-full px-6 lg:px-8 pb-6 lg:pb-8 pt-1">
      <div className="bg-card border border-border rounded-lg overflow-hidden h-full flex flex-col">
        {loading ? (
          <div className="py-12 px-6 text-center text-muted-foreground text-sm">
            <Loader2 size={24} className="animate-spin inline-block" />
          </div>
        ) : stories.length === 0 ? (
          <div className="py-12 px-6 text-center text-muted-foreground text-sm">
            {t('allStories.noResults')}
          </div>
        ) : (
          <div className="flex-1 min-h-0 overflow-auto">
          {/* #54 — collapse Reporter, Location, Submission Time back into the
              title cell as a stacked metadata strip beneath the headline.
              The previous flat-grid layout (#51) made every row very wide and
              forced reviewers to scan across many narrow columns; reverting
              the personal-metadata trio under the headline keeps each story's
              identifying info together while leaving the editorial signals
              (Category, Status, Reviewed by, Assigned to) as their own
              columns for at-a-glance scanning across rows.
              vr-table-spaced opts out of the global dense table preset. */}
          <Table className="vr-table-spaced">
            <TableHeader className="sticky top-0 z-10 bg-card shadow-[0_1px_0_0_var(--border)]">
              <TableRow>
                <TableHead className="px-4 py-3 text-[11px] font-semibold text-muted-foreground uppercase tracking-[0.06em] max-sm:px-3 max-sm:py-2">
                  {t('table.storyTitle')}
                </TableHead>
                <TableHead className="px-4 py-3 text-[11px] font-semibold text-muted-foreground uppercase tracking-[0.06em] max-sm:px-3 max-sm:py-2">
                  {t('table.category')}
                </TableHead>
                <TableHead className="px-4 py-3 text-[11px] font-semibold text-muted-foreground uppercase tracking-[0.06em] max-sm:px-3 max-sm:py-2">
                  {t('table.status')}
                </TableHead>
                <TableHead className="px-4 py-3 text-[11px] font-semibold text-muted-foreground uppercase tracking-[0.06em] max-sm:px-3 max-sm:py-2">
                  {t('stories.reviewedBy')}
                </TableHead>
                <TableHead className="px-4 py-3 text-[11px] font-semibold text-muted-foreground uppercase tracking-[0.06em] max-sm:px-3 max-sm:py-2">
                  {t('assignment.assignedTo')}
                </TableHead>
                {isOrgAdmin && (
                  <TableHead className="px-4 py-3 w-[50px]" aria-label="Row actions" />
                )}
              </TableRow>
            </TableHeader>
            <TableBody>
              {stories.map((story) => {
                const timePrimary = formatDate(story.submittedAt || story.createdAt);
                const timeSecondary = formatTimeAgo(story.submittedAt || story.createdAt);

                return (
                  <TableRow
                    key={story.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/review/${story.id}`)}
                  >
                    {/* #54 — Story title with stacked metadata strip
                        underneath: reporter • location • time-ago. Whole
                        row is clickable; the headline stays a real Link
                        so cmd/middle-click still opens in a new tab.
                        Each meta chip uses whitespace-nowrap and the
                        wrapper allows wrap so on narrow screens they
                        stack vertically rather than overflow.
                        max-w-[480px] keeps long Odia headlines from
                        squashing the editorial-signal columns to the right. */}
                    <TableCell className="px-4 py-3.5 max-sm:px-3 max-sm:py-2.5 max-w-[480px] align-middle">
                      <div className="flex flex-col gap-1.5">
                        <Link
                          to={`/review/${story.id}`}
                          onClick={(e) => e.stopPropagation()}
                          className="text-sm font-semibold text-foreground leading-tight line-clamp-2 hover:text-primary transition-colors no-underline"
                        >
                          {story.headline}
                        </Link>
                        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
                          <span className="inline-flex items-center gap-1 whitespace-nowrap">
                            <Avatar
                              initials={story.reporter.initials}
                              color={story.reporter.color}
                              size="xs"
                            />
                            <span className="font-medium text-foreground">
                              {story.reporter.name}
                            </span>
                          </span>
                          {story.location && (
                            <span className="inline-flex items-center gap-1 whitespace-nowrap">
                              <MapPin size={11} className="shrink-0" />
                              {story.location}
                            </span>
                          )}
                          <span
                            className="inline-flex items-center gap-1 whitespace-nowrap"
                            title={timePrimary}
                          >
                            <Clock size={11} className="shrink-0" />
                            {timeSecondary || timePrimary}
                          </span>
                        </div>
                      </div>
                    </TableCell>

                    {/* Category — dot + label */}
                    <TableCell className="px-4 py-3.5 max-sm:px-3 max-sm:py-2.5 align-middle">
                      <CategoryChip category={story.category} minimal />
                    </TableCell>

                    {/* Status — dot + label */}
                    <TableCell className="px-4 py-3.5 max-sm:px-3 max-sm:py-2.5 align-middle">
                      <StatusBadge status={story.status} minimal />
                    </TableCell>

                    {/* Reviewed by — single-line first name + date */}
                    <TableCell className="px-4 py-3.5 max-sm:px-3 max-sm:py-2.5 align-middle">
                      {story.reviewer_name ? (
                        <div className="flex items-center gap-1.5 whitespace-nowrap">
                          <span className="text-xs text-foreground font-medium" title={story.reviewer_name}>
                            {story.reviewer_name.split(' ')[0]}
                          </span>
                          {story.reviewed_at && (
                            <span className="text-[11px] text-muted-foreground">
                              {formatDate(story.reviewed_at)}
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </TableCell>

                    {/* Assigned to — inline reassign popover.
                        stopPropagation so opening the popover or picking a
                        reviewer doesn't also navigate the row. */}
                    <TableCell
                      className="px-4 py-3.5 max-sm:px-3 max-sm:py-2.5 align-middle"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <ReassignPopover
                        assigneeId={story.assignee_id}
                        assigneeName={story.assignee_name}
                        matchReason={story.assigned_match_reason}
                        reviewers={reviewers}
                        onReassign={(userId) => handleReassign(story.id, userId)}
                      />
                    </TableCell>

                    {/* Row actions — org_admin only */}
                    {isOrgAdmin && (
                      <TableCell
                        className="px-4 py-3.5 max-sm:px-3 max-sm:py-2.5 align-middle"
                        onClick={(e) => e.stopPropagation()}
                      >
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
                      </TableCell>
                    )}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
          </div>
        )}

        {/* Pagination */}
        {totalStories > 0 && !loading && (
          <div className="shrink-0 flex items-center justify-between px-4 py-2 border-t border-border max-sm:flex-col max-sm:gap-3 max-sm:items-center">
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
                size="icon-xs"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                aria-label="Previous page"
              >
                <ChevronLeft size={16} />
              </Button>
              {Array.from({ length: totalPages }, (_, i) => i + 1)
                .filter((page) => {
                  if (page === 1 || page === totalPages) return true;
                  if (Math.abs(page - currentPage) <= 1) return true;
                  return false;
                })
                .reduce((acc, page, i, arr) => {
                  if (i > 0 && page - arr[i - 1] > 1) {
                    acc.push({ type: 'ellipsis', key: `e-${page}` });
                  }
                  acc.push({ type: 'page', page, key: page });
                  return acc;
                }, [])
                .map((item) =>
                  item.type === 'ellipsis' ? (
                    <span
                      key={item.key}
                      className="inline-flex items-center justify-center min-w-[24px] text-xs text-muted-foreground select-none"
                    >
                      ...
                    </span>
                  ) : (
                    <Button
                      key={item.key}
                      variant={item.page === currentPage ? 'default' : 'outline'}
                      size="xs"
                      onClick={() => setCurrentPage(item.page)}
                    >
                      {item.page}
                    </Button>
                  )
                )}
              <Button
                variant="outline"
                size="icon-xs"
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
    </div>
  );
}
