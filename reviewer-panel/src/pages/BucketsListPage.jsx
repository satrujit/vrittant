import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Calendar, Newspaper, Loader2, Trash2, FileText, BookOpen, Search, Pencil, ChevronRight, ChevronDown, Columns3 } from 'lucide-react';
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
import { Modal, SearchableSelect, PageHeader } from '../components/common';
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
function EditionTable({ editions, t, onRowClick, onEdit, onDelete, onStatusChange, bordered = true }) {
  return (
    <div
      className={cn(
        'bg-card overflow-hidden',
        bordered && 'border border-border rounded-lg shadow-sm'
      )}
    >
      <Table>
        <TableHeader>
          <TableRow>
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
          {editions.map((edition) => {
            const statusKey = getStatusKey(edition.status);
            const pageCount = edition.pages?.length ?? edition.page_count ?? 0;
            const storyCount = edition.story_count ?? 0;
            const statusStyle = STATUS_COLORS[statusKey] || STATUS_COLORS.draft;
            const paperLabel = t(`buckets.paperTypes.${edition.paper_type}`) !== `buckets.paperTypes.${edition.paper_type}`
              ? t(`buckets.paperTypes.${edition.paper_type}`)
              : edition.paper_type;

            return (
              <TableRow
                key={edition.id}
                className="cursor-pointer group"
                onClick={() => onRowClick(edition.id)}
              >
                <TableCell className="px-4 py-2">
                  <span className="inline-flex items-center gap-1.5 text-sm font-medium text-foreground">
                    <Newspaper size={13} className="text-primary/70 shrink-0" />
                    {paperLabel}
                  </span>
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

  const [editions, setEditions] = useState([]);
  const [loading, setLoading] = useState(true);

  // Create modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newDate, setNewDate] = useState(getTodayDate());
  const [newPaperType, setNewPaperType] = useState('');
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

  // Published-section toggle (collapsed by default — keeps focus on active editions)
  const [publishedExpanded, setPublishedExpanded] = useState(false);

  const loadEditions = async () => {
    setLoading(true);
    try {
      const data = await fetchEditions();
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
    fetchEditions()
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

    return result;
  }, [editions, search, filterPaperType, filterStatus, t]);

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
      await createEdition({ publication_date: newDate, paper_type: newPaperType });
      await loadEditions();
      setShowCreateModal(false);
      setNewDate(getTodayDate());
      setNewPaperType(pubTypes[0]?.key || '');
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
    setShowCreateModal(true);
  };

  const closeCreateModal = () => {
    setShowCreateModal(false);
    setNewDate(getTodayDate());
    setNewPaperType(pubTypes[0]?.key || '');
  };

  const closeEditModal = () => {
    setShowEditModal(false);
    setEditingEdition(null);
    setEditDate('');
    setEditPaperType('');
  };

  return (
    <div className="flex flex-col gap-5 max-w-[1400px] mx-auto p-6 lg:p-8 min-h-full">
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

      {/* Search & Filter bar */}
      <div className="flex items-center gap-3 flex-wrap max-md:flex-col max-md:items-stretch">
        <div className="relative flex items-center flex-1 min-w-[200px] max-w-[360px] max-md:max-w-none">
          <Search size={16} className="absolute left-3 text-muted-foreground pointer-events-none z-10" />
          <Input
            type="text"
            className="pl-[38px] rounded-lg bg-card border-border text-foreground placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-primary/10"
            placeholder={t('buckets.searchEditionsPlaceholder')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <SearchableSelect
          triggerClassName="min-w-[150px]"
          value={filterPaperType}
          onChange={setFilterPaperType}
          placeholder={t('buckets.filterByPaperType')}
          allLabel={t('buckets.filterByPaperType')}
          options={pubTypes.map(pt => ({
            value: pt.key,
            label: t(`buckets.paperTypes.${pt.key}`) !== `buckets.paperTypes.${pt.key}`
              ? t(`buckets.paperTypes.${pt.key}`)
              : pt.label,
          }))}
        />

        <SearchableSelect
          triggerClassName="min-w-[150px]"
          value={filterStatus}
          onChange={setFilterStatus}
          placeholder={t('buckets.filterByStatus')}
          allLabel={t('buckets.filterByStatus')}
          options={[
            { value: 'draft', label: t('buckets.editionStatus.draft') },
            { value: 'finalized', label: t('buckets.editionStatus.finalized') },
            { value: 'published', label: t('buckets.editionStatus.published') },
          ]}
        />
      </div>

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
