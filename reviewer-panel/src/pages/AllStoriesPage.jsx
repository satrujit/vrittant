import { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
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

const PAGE_SIZE = 10;

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
  const isOrgAdmin = user?.user_type === 'org_admin';
  const categoryList = (config?.categories || []).filter(c => c.is_active).map(c => c.key);
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [reporterFilter, setReporterFilter] = useState('');
  const [locationFilter, setLocationFilter] = useState('');
  // Default to yesterday so the page opens on "last 1 day" of submissions.
  // Personal queue scoping moved to the Dashboard — All Stories is org-wide.
  const [dateFrom, setDateFrom] = useState(getYesterdayISO);
  const [dateTo, setDateTo] = useState('');
  const [currentPage, setCurrentPage] = useState(1);

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
        setReviewers(
          list.filter((u) => u.user_type === 'reviewer' && (u.is_active ?? true))
        );
      })
      .catch(() => {
        setReporters([]);
        setReviewers([]);
      });
  }, []);

  // Debounce search input (300ms)
  const debounceTimer = useRef(null);
  const handleSearch = (e) => {
    const value = e.target.value;
    setSearchQuery(value);
    setCurrentPage(1);
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(() => {
      setDebouncedSearch(value);
    }, 300);
  };

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    };
  }, []);

  // Fetch stories when filters or page change — exclude drafts by default
  const loadStories = useCallback(async () => {
    setLoading(true);
    try {
      const offset = (currentPage - 1) * PAGE_SIZE;
      const hasFilters = statusFilter || categoryFilter || reporterFilter || locationFilter || dateFrom || dateTo;
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
  }, [currentPage, debouncedSearch, statusFilter, categoryFilter, reporterFilter, locationFilter, dateFrom, dateTo]);

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
    locationFilter ||
    dateFrom ||
    dateTo ||
    searchQuery
  );

  const handleClearFilters = () => {
    setStatusFilter('');
    setCategoryFilter('');
    setReporterFilter('');
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
    <div className="flex flex-col gap-5 max-w-[1400px] mx-auto p-6 lg:p-8">
      <PageHeader
        icon={Archive}
        title={t('allStories.title')}
        subtitle={t('allStories.subtitle')}
        className="mb-0"
      />

      <div className="flex flex-col gap-3">
        <div className="relative max-w-[420px]">
          <SearchBar
            value={searchQuery}
            onChange={handleSearch}
            placeholder={t('allStories.searchPlaceholder')}
            icon={Sparkles}
          />
          {semanticLoading && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1.5 text-primary">
              <Sparkles size={14} className="animate-pulse" />
              <span className="text-[11px] font-medium">AI searching...</span>
            </div>
          )}
        </div>

        {/* Filters Row — compact inline */}
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
        </div>
      </div>

      {/* Table Card */}
      <div className="bg-card border border-border rounded-lg overflow-hidden">
        {loading ? (
          <div className="py-12 px-6 text-center text-muted-foreground text-sm">
            <Loader2 size={24} className="animate-spin inline-block" />
          </div>
        ) : stories.length === 0 ? (
          <div className="py-12 px-6 text-center text-muted-foreground text-sm">
            {t('allStories.noResults')}
          </div>
        ) : (
          <Table className="vr-table-dense">
            <TableHeader>
              <TableRow>
                <TableHead className="px-4 py-2 text-[11px] font-semibold text-muted-foreground uppercase tracking-[0.06em] max-sm:px-3 max-sm:py-1.5">
                  {t('table.storyTitle')}
                </TableHead>
                <TableHead className="px-4 py-2 text-[11px] font-semibold text-muted-foreground uppercase tracking-[0.06em] max-sm:px-3 max-sm:py-1.5">
                  {t('table.submissionTime')}
                </TableHead>
                <TableHead className="px-4 py-2 text-[11px] font-semibold text-muted-foreground uppercase tracking-[0.06em] max-sm:px-3 max-sm:py-1.5">
                  {t('table.category')}
                </TableHead>
                <TableHead className="px-4 py-2 text-[11px] font-semibold text-muted-foreground uppercase tracking-[0.06em] max-sm:px-3 max-sm:py-1.5">
                  {t('table.status')}
                </TableHead>
                <TableHead className="px-4 py-2 text-[11px] font-semibold text-muted-foreground uppercase tracking-[0.06em] max-sm:px-3 max-sm:py-1.5">
                  {t('stories.reviewedBy')}
                </TableHead>
                <TableHead className="px-4 py-2 text-[11px] font-semibold text-muted-foreground uppercase tracking-[0.06em] max-sm:px-3 max-sm:py-1.5">
                  {t('assignment.assignedTo')}
                </TableHead>
                {isOrgAdmin && (
                  <TableHead className="px-4 py-2 w-[50px]" aria-label="Row actions" />
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
                  >
                    {/* Story title (clickable) + reporter/location metadata */}
                    <TableCell className="px-4 py-2 max-sm:px-3 max-sm:py-1.5 max-w-[420px]">
                      <div className="flex flex-col gap-1 min-w-[200px]">
                        <Link
                          to={`/review/${story.id}`}
                          className="text-sm font-semibold text-foreground leading-tight line-clamp-1 hover:text-primary transition-colors no-underline"
                        >
                          {story.headline}
                          {story.hasRevision && (
                            <span className="inline-block px-1.5 py-px text-[0.625rem] font-semibold uppercase tracking-[0.05em] bg-green-50 text-green-800 rounded ml-2 align-middle">
                              {t('common.edited')}
                            </span>
                          )}
                        </Link>
                        <div className="flex items-center gap-[5px]">
                          <Avatar
                            initials={story.reporter.initials}
                            color={story.reporter.color}
                            size="sm"
                          />
                          <span className="text-[11px] text-muted-foreground font-medium">
                            {story.reporter.name}
                          </span>
                          {story.location && (
                            <>
                              <span className="text-[11px] text-muted-foreground">
                                &middot;
                              </span>
                              <MapPin size={12} className="text-muted-foreground shrink-0" />
                              <span className="text-[11px] text-muted-foreground">
                                {story.location}
                              </span>
                            </>
                          )}
                        </div>
                      </div>
                    </TableCell>

                    {/* Submission Time — relative only, absolute on hover */}
                    <TableCell className="px-4 py-2 max-sm:px-3 max-sm:py-1.5">
                      <span
                        className="inline-flex items-center gap-1 text-xs text-muted-foreground whitespace-nowrap"
                        title={timePrimary}
                      >
                        <Clock size={11} className="shrink-0" />
                        {timeSecondary || timePrimary}
                      </span>
                    </TableCell>

                    {/* Category — dot + label */}
                    <TableCell className="px-4 py-2 max-sm:px-3 max-sm:py-1.5">
                      <CategoryChip category={story.category} minimal />
                    </TableCell>

                    {/* Status — dot + label */}
                    <TableCell className="px-4 py-2 max-sm:px-3 max-sm:py-1.5">
                      <StatusBadge status={story.status} minimal />
                    </TableCell>

                    {/* Reviewed by — stacked name / date */}
                    <TableCell className="px-4 py-2 max-sm:px-3 max-sm:py-1.5">
                      {story.reviewer_name ? (
                        <div
                          className="flex flex-col gap-0.5 whitespace-nowrap leading-tight"
                          title={story.reviewer_name}
                        >
                          <span className="text-xs text-foreground font-medium">
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

                    {/* Assigned to — inline reassign popover */}
                    <TableCell className="px-4 py-2 max-sm:px-3 max-sm:py-1.5">
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
                      <TableCell className="px-4 py-2 max-sm:px-3 max-sm:py-1.5">
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
        )}

        {/* Pagination */}
        {totalStories > 0 && !loading && (
          <div className="flex items-center justify-between px-4 py-2 border-t border-border max-sm:flex-col max-sm:gap-3 max-sm:items-center">
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
  );
}
