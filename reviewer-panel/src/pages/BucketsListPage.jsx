import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Calendar, Newspaper, Loader2, Trash2, FileText, BookOpen, Pencil, ChevronRight, ChevronDown, Columns3, X } from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useI18n } from '../i18n';
import { useAuth } from '../contexts/AuthContext';
import { Modal, SearchableSelect, PageHeader, SearchBar } from '../components/common';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { fetchEditions, createEdition, updateEdition, deleteEdition } from '../services/api';
import { cn } from '@/lib/utils';

function getTodayDate() {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

function getTomorrowDate() {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

// Default visible window for the buckets table — past 2 days, today,
// and the next 7 (the canonical rolling window). 10 days total. The
// reviewer can widen via the date inputs in the filter row when they
// need historical context.
function getDateOffsetISO(deltaDays) {
  const d = new Date();
  d.setDate(d.getDate() + deltaDays);
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}
const DEFAULT_DATE_FROM_OFFSET = -2;
const DEFAULT_DATE_TO_OFFSET = 7;

// Sort comparator for the buckets list. Editor-friendly priority:
//   1. Tomorrow (today + 1) at the very top — that's the paper being
//      actively prepared right now (newspaper convention).
//   2. Day-after-tomorrow forward, ascending — early planning row.
//   3. Today and earlier dates, descending — historical reference.
// Within a date, fall back to title to keep the canonical 6 in a
// stable order (no jitter on re-render).
function compareEditionsForBuckets(a, b, tomorrow) {
  const aDate = a.publication_date || '';
  const bDate = b.publication_date || '';
  const aFuture = aDate >= tomorrow;
  const bFuture = bDate >= tomorrow;
  if (aFuture !== bFuture) return aFuture ? -1 : 1;
  if (aDate !== bDate) {
    return aFuture ? aDate.localeCompare(bDate) : bDate.localeCompare(aDate);
  }
  return (a.title || '').localeCompare(b.title || '');
}

// Human-readable bucket label for the date-group header rows.
// Keeps "Tomorrow" / "Today" / "Yesterday" as anchors and falls back
// to the formatted date for everything else.
function getRelativeDayLabel(dateStr, today, tomorrow, t) {
  if (!dateStr) return '';
  if (dateStr === tomorrow) return t('buckets.relative.tomorrow', 'Tomorrow');
  if (dateStr === today) return t('buckets.relative.today', 'Today');
  // yesterday
  const y = new Date(today + 'T00:00:00');
  y.setDate(y.getDate() - 1);
  const yyyy = y.getFullYear();
  const mm = String(y.getMonth() + 1).padStart(2, '0');
  const dd = String(y.getDate()).padStart(2, '0');
  if (dateStr === `${yyyy}-${mm}-${dd}`) return t('buckets.relative.yesterday', 'Yesterday');
  return null;
}

function formatDisplayDate(dateStr) {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

function getEditionTitle(edition, t) {
  // Prefer the explicit edition title when one is set (e.g. the
  // canonical geographic names like "Bhubaneswar"). Falls back to the
  // synthesized "Daily - 26 Apr 2026" so legacy unnamed editions still
  // surface a useful label in the search/filter.
  if (edition?.title && edition.title.trim()) return edition.title;
  const typeLabel = t(`buckets.paperTypes.${edition.paper_type}`) !== `buckets.paperTypes.${edition.paper_type}`
    ? t(`buckets.paperTypes.${edition.paper_type}`)
    : edition.paper_type;
  const dateStr = formatDisplayDate(edition.publication_date);
  return `${typeLabel} - ${dateStr}`;
}

function getStatusKey(status) {
  if (status === 'finalized') return 'finalized';
  if (status === 'published') return 'published';
  return 'draft';
}

const STATUS_COLORS = {
  draft: {
    color: '#A8A29E',
    background: '#F5F5F4',
  },
  finalized: {
    color: '#10B981',
    background: '#D1FAE5',
  },
  published: {
    color: '#10B981',
    background: '#D1FAE5',
  },
};

// Reusable table for both the active and published edition sections.
// Stops row-click navigation propagating from interactive cells (status,
// edit, delete) so those controls work without sending the user away.
//
// Visual grouping: a thin date-band row is inserted before the first
// edition of each new date so 6 same-day rows read as one cluster
// without dominating the table. The "Tomorrow" group is highlighted
// because that's the paper currently being prepared.
function EditionTable({ editions, t, onRowClick, onEdit, onDelete, onStatusChange, bordered = true }) {
  const today = getTodayDate();
  const tomorrow = getTomorrowDate();

  // Pre-group editions by date so the accordion knows which rows
  // belong under each header. Editions arrive pre-sorted (tomorrow
  // first, then ascending future, then past descending), so iterating
  // preserves that order in the Map.
  const groups = useMemo(() => {
    const map = new Map();
    for (const ed of editions) {
      const d = ed.publication_date || '';
      if (!map.has(d)) map.set(d, []);
      map.get(d).push(ed);
    }
    return Array.from(map.entries());
  }, [editions]);

  // Accordion state. null = "user hasn't interacted yet" → derive
  // default (first group expanded) inline. Once they click anything,
  // we lock in their explicit choices and stop tracking the default.
  const [expandedDates, setExpandedDates] = useState(null);
  const effectiveExpanded =
    expandedDates ?? new Set(groups.length > 0 ? [groups[0][0]] : []);
  const toggleDate = (date) => {
    setExpandedDates((prev) => {
      const next = new Set(prev ?? (groups.length > 0 ? [groups[0][0]] : []));
      if (next.has(date)) next.delete(date);
      else next.add(date);
      return next;
    });
  };

  const renderEditionRow = (edition, index) => {
    const statusKey = getStatusKey(edition.status);
    const pageCount = edition.pages?.length ?? edition.page_count ?? 0;
    const storyCount = edition.story_count ?? 0;
    const statusStyle = STATUS_COLORS[statusKey] || STATUS_COLORS.draft;
    const paperLabel = t(`buckets.paperTypes.${edition.paper_type}`) !== `buckets.paperTypes.${edition.paper_type}`
      ? t(`buckets.paperTypes.${edition.paper_type}`)
      : edition.paper_type;
    const editionLabel = t('buckets.editionNumber', { n: index + 1 });

    return (
      <TableRow
        key={edition.id}
        className="cursor-pointer group"
        onClick={() => onRowClick(edition.id)}
      >
        <TableCell className="px-4 py-2">
          <span className="inline-flex items-center gap-1.5 text-sm font-medium text-foreground">
            <Newspaper size={13} className="text-primary/70 shrink-0" />
            {editionLabel}
          </span>
        </TableCell>
        <TableCell className="px-4 py-2 text-xs text-muted-foreground">
          {paperLabel}
        </TableCell>
        <TableCell className="px-4 py-2">
          <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground whitespace-nowrap">
            <Calendar size={12} className="shrink-0" />
            {formatDisplayDate(edition.publication_date)}
          </span>
        </TableCell>
        <TableCell className="px-4 py-2 text-xs text-foreground">
          <span className="inline-flex items-center gap-1">
            <FileText size={12} className="text-muted-foreground" />
            {pageCount}
          </span>
        </TableCell>
        <TableCell className="px-4 py-2 text-xs text-foreground">
          {storyCount}
        </TableCell>
        <TableCell className="px-4 py-2">
          <Select
            value={statusKey}
            onValueChange={(val) => onStatusChange(edition.id, val)}
          >
            <SelectTrigger
              className="h-auto w-auto gap-1 border-none bg-transparent p-0 px-2 py-[2px] text-[11px] font-semibold rounded-full shadow-none focus:ring-0"
              style={{ color: statusStyle.color, backgroundColor: statusStyle.background }}
              onClick={(e) => e.stopPropagation()}
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="draft">{t('buckets.editionStatus.draft')}</SelectItem>
              <SelectItem value="finalized">{t('buckets.editionStatus.finalized')}</SelectItem>
              <SelectItem value="published">{t('buckets.editionStatus.published')}</SelectItem>
            </SelectContent>
          </Select>
        </TableCell>
        <TableCell className="px-4 py-2">
          <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
            <Button
              variant="ghost"
              size="icon-sm"
              className="text-muted-foreground hover:bg-accent hover:text-primary"
              onClick={(e) => onEdit(e, edition)}
              aria-label={t('buckets.editEdition')}
              title={t('buckets.editEdition')}
            >
              <Pencil size={14} />
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              className="text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
              onClick={(e) => onDelete(e, edition.id)}
              aria-label={t('buckets.deleteEdition')}
              title={t('buckets.deleteEdition')}
            >
              <Trash2 size={14} />
            </Button>
          </div>
        </TableCell>
      </TableRow>
    );
  };

  return (
    <div
      className={cn(
        'bg-card overflow-hidden',
        bordered && 'border border-border rounded-lg shadow-sm'
      )}
    >
      <Table>
        <TableHeader className="sticky top-0 z-10 bg-card shadow-[0_1px_0_0_var(--border)]">
          <TableRow>
            <TableHead className="px-4 py-2 text-[11px] font-semibold text-muted-foreground uppercase tracking-[0.06em]">
              {t('buckets.editionColumn', 'Edition')}
            </TableHead>
            <TableHead className="px-4 py-2 text-[11px] font-semibold text-muted-foreground uppercase tracking-[0.06em]">
              {t('buckets.paperType')}
            </TableHead>
            <TableHead className="px-4 py-2 text-[11px] font-semibold text-muted-foreground uppercase tracking-[0.06em]">
              {t('buckets.publicationDate')}
            </TableHead>
            <TableHead className="px-4 py-2 text-[11px] font-semibold text-muted-foreground uppercase tracking-[0.06em]">
              {t('buckets.pages')}
            </TableHead>
            <TableHead className="px-4 py-2 text-[11px] font-semibold text-muted-foreground uppercase tracking-[0.06em]">
              {t('buckets.stories')}
            </TableHead>
            <TableHead className="px-4 py-2 text-[11px] font-semibold text-muted-foreground uppercase tracking-[0.06em]">
              {t('table.status')}
            </TableHead>
            <TableHead className="px-4 py-2 w-[80px]" aria-label="Row actions" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {groups.flatMap(([date, group]) => {
            const relative = getRelativeDayLabel(date, today, tomorrow, t);
            const isTomorrow = date === tomorrow;
            const isOpen = effectiveExpanded.has(date);
            const headerRow = (
              <TableRow
                key={`group-${date}`}
                className={cn(
                  'cursor-pointer border-b border-border/60 hover:brightness-95',
                  isTomorrow ? 'bg-primary/5' : 'bg-muted/40'
                )}
                onClick={() => toggleDate(date)}
              >
                <TableCell
                  colSpan={7}
                  className="px-4 py-1 text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground"
                >
                  <span className="inline-flex w-full items-center gap-2">
                    {isOpen ? (
                      <ChevronDown size={12} className={cn('shrink-0', isTomorrow && 'text-primary')} />
                    ) : (
                      <ChevronRight size={12} className={cn('shrink-0', isTomorrow && 'text-primary')} />
                    )}
                    <Calendar size={11} className={cn('shrink-0', isTomorrow && 'text-primary')} />
                    <span className={cn(isTomorrow && 'text-primary')}>
                      {formatDisplayDate(date)}
                    </span>
                    {relative && (
                      <span
                        className={cn(
                          'rounded-full px-1.5 py-px text-[10px] font-medium normal-case tracking-normal',
                          isTomorrow
                            ? 'bg-primary/15 text-primary'
                            : 'bg-muted text-muted-foreground'
                        )}
                      >
                        {relative}
                      </span>
                    )}
                    {/* Group count sits at the right edge — it's the
                        only signal of group size when collapsed, so
                        promote it past the muted text-foreground. */}
                    <span className="ml-auto normal-case tracking-normal text-[11px] text-muted-foreground">
                      {group.length}
                    </span>
                  </span>
                </TableCell>
              </TableRow>
            );
            return isOpen
              ? [headerRow, ...group.map((ed, i) => renderEditionRow(ed, i))]
              : [headerRow];
          })}
        </TableBody>
      </Table>
    </div>
  );
}

export default function BucketsListPage() {
  const { t } = useI18n();
  const { config } = useAuth();
  const navigate = useNavigate();

  const pubTypes = (config?.publication_types || []).filter(p => p.is_active);
  // Org's geographic edition names (e.g. Bhubaneswar, Coastal Odisha).
  // Backed by OrgConfig.edition_names — when populated, the same list
  // also drives the auto-rolling 7-day seeder on the backend, so the
  // dropdown here mirrors what reviewers see in Page Arrangement.
  const editionNames = useMemo(
    () => (config?.edition_names || []).filter((n) => typeof n === 'string' && n.trim()),
    [config?.edition_names]
  );

  const [editions, setEditions] = useState([]);
  const [loading, setLoading] = useState(true);

  // Sentinel used when the user picks "Custom…" from the name dropdown
  // instead of a canonical name. Anything else is the literal title.
  const CUSTOM_NAME_SENTINEL = '__custom__';

  // Create modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newDate, setNewDate] = useState(getTodayDate());
  const [newPaperType, setNewPaperType] = useState('');
  // Default to the first canonical name when one exists, otherwise sit
  // on the custom sentinel so the free-text fallback is exposed.
  const [newName, setNewName] = useState('');
  const [newCustomName, setNewCustomName] = useState('');
  const [creating, setCreating] = useState(false);

  // Edit modal state
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingEdition, setEditingEdition] = useState(null);
  const [editDate, setEditDate] = useState('');
  const [editPaperType, setEditPaperType] = useState('');
  const [saving, setSaving] = useState(false);

  // Search and filter state
  const [search, setSearch] = useState('');
  const [filterPaperType, setFilterPaperType] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  // Default to a 10-day window: past 2 + today + next 7. Pure
  // frontend filter — the API still returns up to 200 editions and
  // the cache makes revisits instant. Reviewer can widen by editing
  // either input.
  const [dateFrom, setDateFrom] = useState(() => getDateOffsetISO(DEFAULT_DATE_FROM_OFFSET));
  const [dateTo, setDateTo] = useState(() => getDateOffsetISO(DEFAULT_DATE_TO_OFFSET));

  // Published-section toggle (collapsed by default — keeps focus on active editions)
  const [publishedExpanded, setPublishedExpanded] = useState(false);

  // Hit the backend's max page size (200) for the buckets list. The
  // rolling 7-day canonical window alone is 6×7=42 rows per org, plus
  // any manual editions and historical/published rows. The default
  // backend limit (50) was truncating the window — the most-recent
  // canonical day was only showing a partial set of editions.
  // Until we add real pagination here, request the full cap.
  const EDITIONS_PAGE_SIZE = 200;

  // SWR-style: the cache returns stale data immediately so the table
  // paints on the second visit without a spinner; `onUpdate` fires
  // when the background revalidation completes and we swap in the
  // fresh list.
  const loadEditions = async () => {
    setLoading(true);
    try {
      const data = await fetchEditions(
        { limit: EDITIONS_PAGE_SIZE },
        { onUpdate: (fresh) => setEditions(fresh.editions || []) }
      );
      setEditions(data.editions || []);
    } catch (err) {
      console.error('Failed to fetch editions:', err);
      setEditions([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchEditions(
      { limit: EDITIONS_PAGE_SIZE },
      {
        onUpdate: (fresh) => {
          if (!cancelled) setEditions(fresh.editions || []);
        },
      }
    )
      .then((data) => {
        if (!cancelled) {
          setEditions(data.editions || []);
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error('Failed to fetch editions:', err);
        if (!cancelled) {
          setEditions([]);
          setLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, []);

  // Filtered editions
  const filteredEditions = useMemo(() => {
    let result = editions;
    const q = search.toLowerCase().trim();

    if (q) {
      result = result.filter((edition) => {
        const title = getEditionTitle(edition, t).toLowerCase();
        const dateStr = formatDisplayDate(edition.publication_date).toLowerCase();
        return title.includes(q) || dateStr.includes(q) || (edition.paper_type || '').toLowerCase().includes(q);
      });
    }

    if (filterPaperType) {
      result = result.filter((e) => e.paper_type === filterPaperType);
    }

    if (filterStatus) {
      result = result.filter((e) => getStatusKey(e.status) === filterStatus);
    }

    // Date-range gate. ISO yyyy-mm-dd strings compare lexicographically
    // so no Date parsing needed. Open-ended on either side when the
    // input is blank.
    if (dateFrom) {
      result = result.filter((e) => (e.publication_date || '') >= dateFrom);
    }
    if (dateTo) {
      result = result.filter((e) => (e.publication_date || '') <= dateTo);
    }

    // Sort tomorrow-first so the actively-prepared paper sits at the
    // top, then ascending into the future, then today + past dates.
    // .slice() because Array.prototype.sort mutates and `editions`
    // came straight from state.
    const tomorrow = getTomorrowDate();
    return result.slice().sort((a, b) => compareEditionsForBuckets(a, b, tomorrow));
  }, [editions, search, filterPaperType, filterStatus, dateFrom, dateTo, t]);

  // Split into active (draft + finalized) and published.
  // Active stays expanded; published collapses behind a toggle so the page
  // doesn't drown in historical editions.
  const { activeEditions, publishedEditions } = useMemo(() => {
    const active = [];
    const published = [];
    for (const e of filteredEditions) {
      if (getStatusKey(e.status) === 'published') published.push(e);
      else active.push(e);
    }
    return { activeEditions: active, publishedEditions: published };
  }, [filteredEditions]);

  const handleCreate = async () => {
    setCreating(true);
    try {
      // Resolve the title: a canonical name (if picked) wins; otherwise
      // pass the custom string when non-empty, or omit the field so the
      // backend falls back to its auto-generated "Daily - 26 Apr 2026".
      let title;
      if (newName === CUSTOM_NAME_SENTINEL) {
        const trimmed = newCustomName.trim();
        if (trimmed) title = trimmed;
      } else if (newName) {
        title = newName;
      }
      const payload = { publication_date: newDate, paper_type: newPaperType };
      if (title) payload.title = title;
      await createEdition(payload);
      await loadEditions();
      setShowCreateModal(false);
      setNewDate(getTodayDate());
      setNewPaperType(pubTypes[0]?.key || '');
      setNewName(editionNames[0] || CUSTOM_NAME_SENTINEL);
      setNewCustomName('');
    } catch (err) {
      console.error('Failed to create edition:', err);
    } finally {
      setCreating(false);
    }
  };

  const handleEdit = (e, edition) => {
    e.stopPropagation();
    setEditingEdition(edition);
    setEditDate(edition.publication_date);
    setEditPaperType(edition.paper_type);
    setShowEditModal(true);
  };

  const handleSaveEdit = async () => {
    if (!editingEdition) return;
    setSaving(true);
    try {
      await updateEdition(editingEdition.id, {
        publication_date: editDate,
        paper_type: editPaperType,
      });
      await loadEditions();
      setShowEditModal(false);
      setEditingEdition(null);
    } catch (err) {
      console.error('Failed to update edition:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (e, id) => {
    e.stopPropagation();
    if (window.confirm(t('buckets.deleteEditionConfirm'))) {
      try {
        await deleteEdition(id);
        await loadEditions();
      } catch (err) {
        console.error('Failed to delete edition:', err);
      }
    }
  };

  const handleStatusChange = async (editionId, newStatus) => {
    try {
      await updateEdition(editionId, { status: newStatus });
      await loadEditions();
    } catch (err) {
      console.error('Failed to update edition status:', err);
    }
  };

  const handleCardClick = (id) => {
    navigate(`/buckets/${id}`);
  };

  const openCreateModal = () => {
    setNewDate(getTodayDate());
    setNewPaperType(pubTypes[0]?.key || '');
    setNewName(editionNames[0] || CUSTOM_NAME_SENTINEL);
    setNewCustomName('');
    setShowCreateModal(true);
  };

  const closeCreateModal = () => {
    setShowCreateModal(false);
    setNewDate(getTodayDate());
    setNewPaperType(pubTypes[0]?.key || '');
    setNewName(editionNames[0] || CUSTOM_NAME_SENTINEL);
    setNewCustomName('');
  };

  const closeEditModal = () => {
    setShowEditModal(false);
    setEditingEdition(null);
    setEditDate('');
    setEditPaperType('');
  };

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Fixed top: page header + filter bar. Only the editions list
          scrolls below; the inner EditionTable headers stay sticky. */}
      <div className="shrink-0 max-w-[1400px] mx-auto w-full px-6 lg:px-8 pt-6 lg:pt-8 pb-3 flex flex-col gap-4">
      <PageHeader
        icon={Columns3}
        title={t('buckets.title')}
        subtitle={t('buckets.subtitle')}
        actions={
          <Button onClick={openCreateModal}>
            <Plus size={16} />
            {t('buckets.newEdition')}
          </Button>
        }
        className="mb-0"
      />

      {/* Search & Filter bar — canonical pattern: filters left, search
          right (ml-auto), clear button appears between when any filter
          is active. Mirrors AllStoriesPage. */}
      <div className="flex items-end gap-3 flex-wrap">
        <div className="flex flex-col gap-0.5">
          <Label className="text-[10px] font-medium text-muted-foreground uppercase tracking-[0.04em]">
            {t('buckets.filterByPaperType')}
          </Label>
          <SearchableSelect
            triggerClassName="min-w-[150px]"
            value={filterPaperType}
            onChange={setFilterPaperType}
            placeholder={t('buckets.allPaperTypes', 'All paper types')}
            allLabel={t('buckets.allPaperTypes', 'All paper types')}
            options={pubTypes.map(pt => ({
              value: pt.key,
              label: t(`buckets.paperTypes.${pt.key}`) !== `buckets.paperTypes.${pt.key}`
                ? t(`buckets.paperTypes.${pt.key}`)
                : pt.label,
            }))}
          />
        </div>

        <div className="flex flex-col gap-0.5">
          <Label className="text-[10px] font-medium text-muted-foreground uppercase tracking-[0.04em]">
            {t('buckets.filterByStatus')}
          </Label>
          <SearchableSelect
            triggerClassName="min-w-[150px]"
            value={filterStatus}
            onChange={setFilterStatus}
            placeholder={t('allStories.allStatuses', 'All statuses')}
            allLabel={t('allStories.allStatuses', 'All statuses')}
            options={[
              { value: 'draft', label: t('buckets.editionStatus.draft') },
              { value: 'finalized', label: t('buckets.editionStatus.finalized') },
              { value: 'published', label: t('buckets.editionStatus.published') },
            ]}
          />
        </div>

        {/* Date window. Defaults to past 2 + today + next 7 = 10 days
            so the table opens on a focused, actionable view. Reviewer
            can widen either end (or clear both) to dig into history. */}
        <div className="flex flex-col gap-0.5 min-w-[120px]">
          <Label className="text-[10px] font-medium text-muted-foreground uppercase tracking-[0.04em]">
            {t('allStories.dateFrom', 'From')}
          </Label>
          <Input
            type="date"
            className="h-8 text-xs"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-0.5 min-w-[120px]">
          <Label className="text-[10px] font-medium text-muted-foreground uppercase tracking-[0.04em]">
            {t('allStories.dateTo', 'To')}
          </Label>
          <Input
            type="date"
            className="h-8 text-xs"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
          />
        </div>

        {(filterPaperType
          || filterStatus
          || search
          || dateFrom !== getDateOffsetISO(DEFAULT_DATE_FROM_OFFSET)
          || dateTo !== getDateOffsetISO(DEFAULT_DATE_TO_OFFSET)) && (
          <Button
            variant="ghost"
            size="xs"
            onClick={() => {
              setFilterPaperType('');
              setFilterStatus('');
              setSearch('');
              setDateFrom(getDateOffsetISO(DEFAULT_DATE_FROM_OFFSET));
              setDateTo(getDateOffsetISO(DEFAULT_DATE_TO_OFFSET));
            }}
            className="h-8 text-muted-foreground hover:text-foreground"
          >
            <X size={12} />
            {t('allStories.clearFilters', 'Clear')}
          </Button>
        )}

        <div className="ml-auto w-full max-w-[280px]">
          <SearchBar
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t('buckets.searchEditionsPlaceholder')}
          />
        </div>
      </div>
      </div>

      {/* Scrollable region — only the editions list scrolls. */}
      <div className="flex-1 min-h-0 overflow-auto">
      <div className="max-w-[1400px] mx-auto w-full px-6 lg:px-8 pb-6 lg:pb-8 pt-3">
      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center p-16 flex-1">
          <Loader2 size={24} className="animate-spin text-muted-foreground" />
        </div>
      ) : filteredEditions.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-5 px-6 py-16 flex-1">
          <BookOpen size={48} className="text-muted-foreground opacity-50" />
          <p className="text-sm text-muted-foreground text-center max-w-[360px] leading-normal">
            {editions.length === 0 ? t('buckets.noEditions') : t('allStories.noResults')}
          </p>
          {editions.length === 0 && (
            <Button
              className="bg-primary text-primary-foreground hover:bg-primary/80 hover:-translate-y-px active:translate-y-0 rounded-lg px-5 font-semibold"
              onClick={openCreateModal}
            >
              <Plus size={16} />
              {t('buckets.newEdition')}
            </Button>
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-5">
          {/* Active editions (draft + finalized) — always expanded */}
          {activeEditions.length > 0 && (
            <EditionTable
              editions={activeEditions}
              t={t}
              onRowClick={handleCardClick}
              onEdit={handleEdit}
              onDelete={handleDelete}
              onStatusChange={handleStatusChange}
            />
          )}

          {/* Published editions — collapsed by default */}
          {publishedEditions.length > 0 && (
            <div className="bg-card border border-border rounded-lg shadow-sm overflow-hidden">
              <button
                type="button"
                onClick={() => setPublishedExpanded((v) => !v)}
                className="w-full flex items-center justify-between gap-3 px-4 py-2.5 text-left hover:bg-accent/40 transition-colors"
              >
                <span className="inline-flex items-center gap-2 text-sm font-semibold text-foreground">
                  {publishedExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                  {t('buckets.editionStatus.published')}
                  <span className="text-xs font-normal text-muted-foreground">
                    ({publishedEditions.length})
                  </span>
                </span>
              </button>
              {publishedExpanded && (
                <EditionTable
                  editions={publishedEditions}
                  t={t}
                  onRowClick={handleCardClick}
                  onEdit={handleEdit}
                  onDelete={handleDelete}
                  onStatusChange={handleStatusChange}
                  bordered={false}
                />
              )}
            </div>
          )}

          {/* Edge case: filters left only published, but it's collapsed */}
          {activeEditions.length === 0 && publishedEditions.length === 0 && (
            <div className="text-center text-sm text-muted-foreground py-6">
              {t('allStories.noResults')}
            </div>
          )}
        </div>
      )}
      </div>
      </div>

      {/* Create Edition Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={closeCreateModal}
        title={t('buckets.createEditionTitle')}
      >
        <div className="flex flex-col gap-5">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="edition-date">
              {t('buckets.publicationDate')}
            </Label>
            <Input
              id="edition-date"
              type="date"
              value={newDate}
              onChange={(e) => setNewDate(e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="edition-paper-type">
              {t('buckets.paperType')}
            </Label>
            <Select value={newPaperType} onValueChange={setNewPaperType}>
              <SelectTrigger id="edition-paper-type" className="w-full rounded-lg bg-card border-border text-foreground">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {pubTypes.map(pt => (
                  <SelectItem key={pt.key} value={pt.key}>
                    {t(`buckets.paperTypes.${pt.key}`) !== `buckets.paperTypes.${pt.key}`
                      ? t(`buckets.paperTypes.${pt.key}`)
                      : pt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Edition name picker. Shown only when the org has configured
              canonical names (Pragativadi has 6: Bhubaneswar etc.).
              "Custom…" lets the reviewer create one-off editions
              alongside the auto-rolling canonical set. */}
          {editionNames.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="edition-name">
                {t('buckets.editionName', 'Edition name')}
              </Label>
              <Select value={newName} onValueChange={setNewName}>
                <SelectTrigger id="edition-name" className="w-full rounded-lg bg-card border-border text-foreground">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {editionNames.map((name) => (
                    <SelectItem key={name} value={name}>{name}</SelectItem>
                  ))}
                  <SelectItem value={CUSTOM_NAME_SENTINEL}>
                    {t('buckets.editionNameCustom', 'Custom…')}
                  </SelectItem>
                </SelectContent>
              </Select>
              {newName === CUSTOM_NAME_SENTINEL && (
                <Input
                  id="edition-name-custom"
                  className="mt-1.5"
                  placeholder={t('buckets.editionNameCustomPlaceholder', 'Enter a custom edition name')}
                  value={newCustomName}
                  onChange={(e) => setNewCustomName(e.target.value)}
                />
              )}
            </div>
          )}

          <div className="flex items-center justify-end gap-2 pt-2">
            <Button
              variant="outline"
              className="rounded-lg text-muted-foreground border-border hover:bg-accent hover:text-foreground px-5"
              onClick={closeCreateModal}
              type="button"
            >
              {t('buckets.cancel')}
            </Button>
            <Button
              className="bg-primary text-primary-foreground hover:bg-primary/80 hover:-translate-y-px active:translate-y-0 rounded-lg px-6 font-semibold"
              onClick={handleCreate}
              disabled={creating || !newDate}
              type="button"
            >
              {creating && <Loader2 size={14} className="animate-spin" />}
              {t('buckets.create')}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Edit Edition Modal */}
      <Modal
        isOpen={showEditModal}
        onClose={closeEditModal}
        title={t('buckets.editEditionTitle')}
      >
        <div className="flex flex-col gap-5">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="edit-edition-date">
              {t('buckets.publicationDate')}
            </Label>
            <Input
              id="edit-edition-date"
              type="date"
              value={editDate}
              onChange={(e) => setEditDate(e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="edit-edition-paper-type">
              {t('buckets.paperType')}
            </Label>
            <Select value={editPaperType} onValueChange={setEditPaperType}>
              <SelectTrigger id="edit-edition-paper-type" className="w-full rounded-lg bg-card border-border text-foreground">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {pubTypes.map(pt => (
                  <SelectItem key={pt.key} value={pt.key}>
                    {t(`buckets.paperTypes.${pt.key}`) !== `buckets.paperTypes.${pt.key}`
                      ? t(`buckets.paperTypes.${pt.key}`)
                      : pt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center justify-end gap-2 pt-2">
            <Button
              variant="outline"
              className="rounded-lg text-muted-foreground border-border hover:bg-accent hover:text-foreground px-5"
              onClick={closeEditModal}
              type="button"
            >
              {t('buckets.cancel')}
            </Button>
            <Button
              className="bg-primary text-primary-foreground hover:bg-primary/80 hover:-translate-y-px active:translate-y-0 rounded-lg px-6 font-semibold"
              onClick={handleSaveEdit}
              disabled={saving || !editDate}
              type="button"
            >
              {saving && <Loader2 size={14} className="animate-spin" />}
              {t('buckets.save')}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
