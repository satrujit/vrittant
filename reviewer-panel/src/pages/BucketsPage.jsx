import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { DragDropContext, Droppable, Draggable } from '@hello-pangea/dnd';
import {
  Search,
  Plus,
  GripVertical,
  ArrowLeft,
  Loader2,
  Pencil,
  Check,
  Trash2,
  SlidersHorizontal,
  Download,
} from 'lucide-react';
import { useI18n } from '../i18n';
import { useAuth } from '../contexts/AuthContext';
import {
  fetchEdition,
  fetchStories,
  transformStory,
  updateEdition,
  addEditionPage,
  updateEditionPage,
  deleteEditionPage,
  assignStoriesToPage,
  exportEditionZip,
} from '../services/api';
import { formatTimeAgo, truncateText, getCategoryColor } from '../utils/helpers';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

/* ----------------------------------------
   Constants
   ---------------------------------------- */
const UNASSIGNED_ID = 'unassigned';


/* ----------------------------------------
   StoryCard sub-component
   ---------------------------------------- */
function StoryCard({ story, index, onClick, t }) {
  const catColor = getCategoryColor(story.category);

  return (
    <Draggable draggableId={String(story.id)} index={index}>
      {(dragProvided, dragSnapshot) => (
        <div
          ref={dragProvided.innerRef}
          {...dragProvided.draggableProps}
          className={cn(
            'group bg-card border border-border rounded-lg',
            'px-3 py-2 mb-1 cursor-pointer select-none',
            'transition-[box-shadow,border-color] duration-150 ease-in-out',
            'hover:border-primary/40 hover:shadow-md',
            dragSnapshot.isDragging && 'shadow-lg border-primary rotate-2'
          )}
          onClick={() => onClick(story.id)}
        >
          <span
            className="inline-flex items-center px-2 py-px text-[10px] font-semibold rounded-md mb-1"
            style={{ color: catColor.color, background: catColor.bg }}
          >
            {t(`categories.${story.category}`) !== `categories.${story.category}`
              ? t(`categories.${story.category}`)
              : story.category}
          </span>
          <div className="text-[13px] font-semibold text-foreground leading-tight mb-0.5 line-clamp-2">
            {story.headline || '(No headline)'}
          </div>
          {story.bodyText && (
            <div className="text-[11px] text-muted-foreground leading-normal line-clamp-2 mb-2">
              {truncateText(story.bodyText, 80)}
            </div>
          )}
          <div className="flex items-center justify-between pt-1 border-t border-border">
            <div className="flex items-center gap-1">
              <div
                className="w-[22px] h-[22px] rounded-full flex items-center justify-center text-[8px] font-bold text-primary-foreground shrink-0"
                style={{ background: story.reporter?.color || 'hsl(var(--primary))' }}
              >
                {story.reporter?.initials || '?'}
              </div>
              <span className="text-[10px] text-muted-foreground">{formatTimeAgo(story.submittedAt)}</span>
            </div>
            <div
              {...dragProvided.dragHandleProps}
              className="text-muted-foreground shrink-0 opacity-40 cursor-grab transition-opacity duration-150 group-hover:opacity-100"
              onClick={(e) => e.stopPropagation()}
            >
              <GripVertical size={16} />
            </div>
          </div>
        </div>
      )}
    </Draggable>
  );
}

/* ----------------------------------------
   BucketsPage Component
   ---------------------------------------- */
export default function BucketsPage() {
  const { t } = useI18n();
  const { config } = useAuth();
  const navigate = useNavigate();
  const { editionId } = useParams();
  const pageSuggestions = (config?.page_suggestions || []).filter(p => p.is_active);

  // State
  const [edition, setEdition] = useState(null);
  const [pages, setPages] = useState([]);
  const [allStories, setAllStories] = useState([]);
  const [assignments, setAssignments] = useState({});
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [showAddPage, setShowAddPage] = useState(false);
  const [newPageName, setNewPageName] = useState('');
  const [editingPageId, setEditingPageId] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const [editingEditionTitle, setEditingEditionTitle] = useState(false);
  const [editionTitleDraft, setEditionTitleDraft] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState('');
  const [locationFilter, setLocationFilter] = useState('');
  const [exporting, setExporting] = useState(false);

  const editInputRef = useRef(null);
  const editionTitleInputRef = useRef(null);
  const addPageInputRef = useRef(null);

  // ── Load data on mount ──
  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    Promise.all([
      fetchEdition(editionId),
      fetchStories({ status: 'approved', limit: 500, available_for_edition: editionId }),
    ])
      .then(([editionData, storiesData]) => {
        if (cancelled) return;

        const transformedStories = (storiesData.stories || []).map(transformStory);
        const storyMap = {};
        transformedStories.forEach((s) => { storyMap[s.id] = s; });

        const editionPages = editionData.pages || [];
        const assignmentMap = {};
        const assignedIds = new Set();

        editionPages.forEach((page) => {
          const pageStories = (page.story_assignments || [])
            .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))
            .map((sa) => storyMap[sa.story_id])
            .filter(Boolean);
          assignmentMap[page.id] = pageStories;
          pageStories.forEach((s) => assignedIds.add(s.id));
        });

        const unassigned = transformedStories.filter((s) => !assignedIds.has(s.id));
        assignmentMap[UNASSIGNED_ID] = unassigned;

        setEdition(editionData);
        setPages(editionPages);
        setAllStories(transformedStories);
        setAssignments(assignmentMap);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load edition data:', err);
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [editionId]);

  // ── Focus edit inputs ──
  useEffect(() => {
    if (editingPageId && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editingPageId]);

  useEffect(() => {
    if (editingEditionTitle && editionTitleInputRef.current) {
      editionTitleInputRef.current.focus();
      editionTitleInputRef.current.select();
    }
  }, [editingEditionTitle]);

  useEffect(() => {
    if (showAddPage && addPageInputRef.current) {
      addPageInputRef.current.focus();
    }
  }, [showAddPage]);

  // ── Derive unique categories and locations from allStories ──
  const uniqueCategories = useMemo(() => {
    const cats = new Set();
    allStories.forEach((s) => { if (s.category) cats.add(s.category); });
    return [...cats].sort();
  }, [allStories]);

  const uniqueLocations = useMemo(() => {
    const locs = new Set();
    allStories.forEach((s) => { if (s.location) locs.add(s.location); });
    return [...locs].sort();
  }, [allStories]);

  // ── Filtered assignments ──
  const filteredAssignments = useMemo(() => {
    const result = {};
    const q = search.toLowerCase().trim();
    const hasFilters = categoryFilter || locationFilter;

    Object.entries(assignments).forEach(([pageId, cards]) => {
      let filtered = cards;

      // Search applies to ALL columns
      if (q) {
        filtered = filtered.filter(
          (c) =>
            c.headline?.toLowerCase().includes(q) ||
            c.reporter?.name?.toLowerCase().includes(q) ||
            c.bodyText?.toLowerCase().includes(q)
        );
      }

      // Category/location filters apply ONLY to unassigned
      if (pageId === UNASSIGNED_ID && hasFilters) {
        filtered = filtered.filter((c) => {
          const catMatch = !categoryFilter || c.category === categoryFilter;
          const locMatch = !locationFilter || c.location === locationFilter;
          return catMatch && locMatch;
        });
      }

      result[pageId] = filtered;
    });

    return result;
  }, [assignments, search, categoryFilter, locationFilter]);

  // ── Drag & Drop handler ──
  const onDragEnd = useCallback((result) => {
    const { source, destination } = result;
    if (!destination) return;
    if (source.droppableId === destination.droppableId && source.index === destination.index) return;

    setAssignments((prev) => {
      const next = { ...prev };
      const srcCol = [...(next[source.droppableId] || [])];
      const destCol =
        source.droppableId === destination.droppableId
          ? srcCol
          : [...(next[destination.droppableId] || [])];

      const [moved] = srcCol.splice(source.index, 1);
      destCol.splice(destination.index, 0, moved);

      next[source.droppableId] = srcCol;
      if (source.droppableId !== destination.droppableId) {
        next[destination.droppableId] = destCol;
      }
      return next;
    });

    // API calls for persistence
    const destPageId = destination.droppableId;
    const srcPageId = source.droppableId;

    // Update destination page (if it's a real page, not unassigned)
    if (destPageId !== UNASSIGNED_ID) {
      // We need to compute the new story IDs for the destination after the move
      setAssignments((current) => {
        const destStoryIds = (current[destPageId] || []).map((s) => s.id);
        assignStoriesToPage(editionId, destPageId, destStoryIds).catch((err) => {
          console.error('Failed to assign stories to page:', err);
        });
        return current;
      });
    }

    // Update source page (if it's a real page, not unassigned)
    if (srcPageId !== UNASSIGNED_ID && srcPageId !== destPageId) {
      setAssignments((current) => {
        const srcStoryIds = (current[srcPageId] || []).map((s) => s.id);
        assignStoriesToPage(editionId, srcPageId, srcStoryIds).catch((err) => {
          console.error('Failed to update source page:', err);
        });
        return current;
      });
    }
  }, [editionId]);

  // ── Add Page ──
  const handleAddPage = useCallback(async () => {
    if (!newPageName.trim()) return;
    try {
      const newPage = await addEditionPage(editionId, { page_name: newPageName.trim() });
      setPages((prev) => [...prev, newPage]);
      setAssignments((prev) => ({ ...prev, [newPage.id]: [] }));
      setNewPageName('');
      setShowAddPage(false);
    } catch (err) {
      console.error('Failed to add page:', err);
    }
  }, [editionId, newPageName]);

  // ── Delete Page ──
  const handleDeletePage = useCallback(async (pageId) => {
    try {
      await deleteEditionPage(editionId, pageId);
      setAssignments((prev) => {
        const next = { ...prev };
        const storiesOnPage = next[pageId] || [];
        next[UNASSIGNED_ID] = [...(next[UNASSIGNED_ID] || []), ...storiesOnPage];
        delete next[pageId];
        return next;
      });
      setPages((prev) => prev.filter((p) => p.id !== pageId));
    } catch (err) {
      console.error('Failed to delete page:', err);
    }
  }, [editionId]);

  // ── Edit Page Title ──
  const startEditTitle = (pageId, currentTitle) => {
    setEditingPageId(pageId);
    setEditTitle(currentTitle);
  };

  const savePageTitle = useCallback(async () => {
    if (editingPageId && editTitle.trim()) {
      try {
        await updateEditionPage(editionId, editingPageId, { page_name: editTitle.trim() });
        setPages((prev) =>
          prev.map((p) =>
            p.id === editingPageId ? { ...p, page_name: editTitle.trim() } : p
          )
        );
      } catch (err) {
        console.error('Failed to update page title:', err);
      }
    }
    setEditingPageId(null);
    setEditTitle('');
  }, [editionId, editingPageId, editTitle]);

  // ── Edit Edition Title ──
  const startEditEditionTitle = () => {
    setEditingEditionTitle(true);
    setEditionTitleDraft(edition?.title || '');
  };

  const saveEditionTitle = useCallback(async () => {
    if (editionTitleDraft.trim() && edition) {
      try {
        await updateEdition(editionId, { title: editionTitleDraft.trim() });
        setEdition((prev) => ({ ...prev, title: editionTitleDraft.trim() }));
      } catch (err) {
        console.error('Failed to update edition title:', err);
      }
    }
    setEditingEditionTitle(false);
    setEditionTitleDraft('');
  }, [editionId, editionTitleDraft, edition]);

  // ── Filter helpers ──
  const clearAllFilters = () => {
    setCategoryFilter('');
    setLocationFilter('');
  };

  // ── Navigate to review ──
  const handleCardClick = (storyId) => {
    navigate(`/review/${storyId}`);
  };

  const unassignedCards = filteredAssignments[UNASSIGNED_ID] || [];
  const hasActiveFilters = !!categoryFilter || !!locationFilter;

  // Generate display title from paper_type + date (same as EditionsPage)
  const editionDisplayTitle = useMemo(() => {
    if (!edition) return t('buckets.editionTitle');
    const typeLabel = t(`buckets.paperTypes.${edition.paper_type}`) !== `buckets.paperTypes.${edition.paper_type}`
      ? t(`buckets.paperTypes.${edition.paper_type}`)
      : edition.paper_type;
    if (edition.publication_date) {
      try {
        const dateStr = edition.publication_date;
        const d = new Date(dateStr + (dateStr.includes('T') ? '' : 'T00:00:00'));
        const formatted = d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
        return `${typeLabel} - ${formatted}`;
      } catch {
        return `${typeLabel} - ${edition.publication_date}`;
      }
    }
    return edition.title || t('buckets.editionTitle');
  }, [edition, t]);

  // ── Render ──
  if (loading) {
    return (
      <div className="flex flex-col h-full min-h-0 overflow-hidden">
        <div className="flex items-center justify-center p-12 flex-1">
          <Loader2 size={24} className="animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full min-h-0 overflow-hidden">
      {/* ── Header ── */}
      <div className="flex items-center justify-between gap-5 px-6 pt-5 pb-3 border-b border-border shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <Button
            variant="ghost"
            size="icon"
            className={cn(
              'w-[34px] h-[34px]',
              'bg-accent border border-border rounded-lg',
              'text-muted-foreground cursor-pointer shrink-0',
              'transition-[background,color,border-color] duration-150',
              'hover:bg-primary/10 hover:text-primary hover:border-primary/40'
            )}
            onClick={() => navigate('/buckets')}
            aria-label={t('buckets.backToEditions')}
            title={t('buckets.backToEditions')}
          >
            <ArrowLeft size={18} />
          </Button>

          {editingEditionTitle ? (
            <div className="flex items-center gap-1 min-w-0">
              <Input
                ref={editionTitleInputRef}
                className={cn(
                  'min-w-[200px] px-2 py-1 h-auto',
                  'text-xl font-bold text-foreground',
                  'bg-card border border-primary rounded-md outline-none',
                  'shadow-none focus-visible:ring-0 focus-visible:border-primary'
                )}
                value={editionTitleDraft}
                onChange={(e) => setEditionTitleDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') saveEditionTitle();
                  if (e.key === 'Escape') {
                    setEditingEditionTitle(false);
                    setEditionTitleDraft('');
                  }
                }}
                onBlur={saveEditionTitle}
              />
              <Button
                variant="ghost"
                size="icon-xs"
                className={cn(
                  'w-7 h-7',
                  'bg-primary border-none rounded-md',
                  'text-primary-foreground cursor-pointer shrink-0',
                  'hover:bg-primary/80 hover:text-primary-foreground'
                )}
                onMouseDown={(e) => e.preventDefault()}
                onClick={saveEditionTitle}
              >
                <Check size={14} />
              </Button>
            </div>
          ) : (
            <div className="group/title flex items-center gap-1 min-w-0">
              <h1 className={cn(
                'text-xl font-bold',
                'text-foreground leading-tight',
                'whitespace-nowrap overflow-hidden text-ellipsis'
              )}>
                {editionDisplayTitle}
              </h1>
              <Button
                variant="ghost"
                size="icon-xs"
                className={cn(
                  'text-muted-foreground cursor-pointer shrink-0',
                  'opacity-0 transition-[opacity,background,color] duration-150',
                  'group-hover/title:opacity-100',
                  'hover:bg-accent hover:text-primary'
                )}
                onClick={startEditEditionTitle}
                aria-label="Edit edition title"
              >
                <Pencil size={14} />
              </Button>
            </div>
          )}
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <div className="relative flex items-center">
            <Search size={16} className="absolute left-3 text-muted-foreground pointer-events-none" />
            <Input
              type="text"
              className={cn(
                'w-[220px] py-2 pr-4 pl-[38px] h-auto',
                'font-sans text-sm text-foreground',
                'bg-card border border-border rounded-lg outline-none',
                'transition-[border-color,box-shadow] duration-150',
                'placeholder:text-muted-foreground',
                'shadow-none focus-visible:ring-0',
                'focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/20'
              )}
              placeholder={t('buckets.searchPlaceholder')}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <Button
            variant="outline"
            className="gap-1.5 px-4 font-semibold rounded-lg hover:-translate-y-px active:translate-y-0"
            disabled={exporting || pages.length === 0}
            onClick={async () => {
              setExporting(true);
              try {
                await exportEditionZip(editionId);
              } catch (err) {
                console.error('Export failed:', err);
                alert(err.message || 'Export failed');
              } finally {
                setExporting(false);
              }
            }}
          >
            {exporting ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
            {exporting ? t('buckets.exporting', 'Exporting...') : t('buckets.downloadZip', 'Download ZIP')}
          </Button>

          <div className="relative">
            <Button
              className="px-5 font-semibold rounded-lg hover:-translate-y-px active:translate-y-0"
              onClick={() => setShowAddPage(!showAddPage)}
            >
              <Plus size={16} />
              {t('buckets.newPage')}
            </Button>

            {showAddPage && (
              <div className={cn(
                'absolute top-[calc(100%+8px)] right-0 w-[320px]',
                'bg-card border border-border rounded-xl',
                'shadow-lg z-50 p-5',
                'flex flex-col gap-3'
              )}>
                <div className="text-sm font-semibold text-foreground">{t('buckets.addPageTitle')}</div>

                <div className="text-xs text-muted-foreground font-medium">{t('buckets.pageSuggestions')}</div>
                <div className="flex flex-wrap gap-1">
                  {pageSuggestions.map((ps) => {
                    const key = ps.key;
                    const label = t(`buckets.pageSuggestionNames.${key}`) !== `buckets.pageSuggestionNames.${key}`
                      ? t(`buckets.pageSuggestionNames.${key}`)
                      : ps.label;
                    return (
                      <Button
                        key={key}
                        variant="outline"
                        size="xs"
                        className={cn(
                          'px-2 py-[3px] h-auto',
                          'font-sans text-xs text-muted-foreground',
                          'bg-background border border-border rounded-full',
                          'cursor-pointer transition-all duration-150',
                          'shadow-none',
                          'hover:text-primary hover:border-primary/40 hover:bg-primary/10'
                        )}
                        onClick={() => setNewPageName(label)}
                      >
                        {label}
                      </Button>
                    );
                  })}
                </div>

                <Input
                  ref={addPageInputRef}
                  type="text"
                  className={cn(
                    'w-full py-2 px-4 h-auto font-sans text-sm text-foreground',
                    'bg-card border border-border rounded-lg outline-none',
                    'transition-[border-color,box-shadow] duration-150',
                    'shadow-none focus-visible:ring-0',
                    'focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/20'
                  )}
                  placeholder={t('buckets.pageNamePlaceholder')}
                  value={newPageName}
                  onChange={(e) => setNewPageName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleAddPage();
                    if (e.key === 'Escape') {
                      setShowAddPage(false);
                      setNewPageName('');
                    }
                  }}
                />

                <div className="flex items-center justify-end gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className={cn(
                      'px-5',
                      'font-sans text-sm font-medium',
                      'text-muted-foreground bg-transparent border border-border rounded-lg',
                      'cursor-pointer transition-all duration-150',
                      'shadow-none',
                      'hover:bg-accent hover:text-foreground'
                    )}
                    onClick={() => { setShowAddPage(false); setNewPageName(''); }}
                  >
                    {t('buckets.cancel')}
                  </Button>
                  <Button
                    size="sm"
                    className={cn(
                      'px-5',
                      'font-sans text-sm font-semibold',
                      'text-primary-foreground bg-primary border-none rounded-lg',
                      'cursor-pointer transition-[background] duration-150',
                      'hover:not-disabled:bg-primary/80'
                    )}
                    onClick={handleAddPage}
                    disabled={!newPageName.trim()}
                  >
                    {t('buckets.create')}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Board ── */}
      <DragDropContext onDragEnd={onDragEnd}>
        <div className="flex flex-1 min-h-0 overflow-x-auto overflow-y-hidden">
          {/* Fixed unassigned panel (left) */}
          <div className="flex-none w-[300px] min-w-[300px] flex flex-col bg-accent border-r border-border overflow-visible min-h-0">
            <div className="flex items-center gap-1 py-2 pl-4 pr-2 border-b border-border shrink-0">
              <div className="w-1 h-[22px] rounded-full shrink-0 bg-muted-foreground" />
              <span className="text-sm font-semibold text-foreground flex-1 whitespace-nowrap overflow-hidden text-ellipsis">
                {t('buckets.unassigned')}
              </span>
              <span className="inline-flex items-center justify-center min-w-[22px] h-5 px-1 text-[11px] font-semibold text-muted-foreground bg-muted rounded-full shrink-0">
                {unassignedCards.length}
              </span>

              <div className="relative">
                <Button
                  variant="ghost"
                  size="icon-xs"
                  className={cn(
                    'w-[26px] h-[26px]',
                    'bg-transparent border border-border rounded-md',
                    'text-muted-foreground cursor-pointer shrink-0 relative',
                    'transition-[background,color,border-color] duration-150',
                    'hover:bg-accent hover:text-primary hover:border-primary/40',
                    hasActiveFilters && 'text-primary border-primary bg-primary/10'
                  )}
                  onClick={() => setShowFilters(!showFilters)}
                  aria-label={t('buckets.filterTitle')}
                  title={t('buckets.filterTitle')}
                >
                  <SlidersHorizontal size={14} />
                </Button>

                {showFilters && (
                  <div className={cn(
                    'absolute top-[calc(100%+8px)] right-0 w-[260px] max-h-[360px]',
                    'overflow-y-auto bg-card border border-border rounded-xl',
                    'shadow-lg z-50 p-3',
                    'flex flex-col gap-3'
                  )}>
                    <div className="text-sm font-semibold text-foreground">{t('buckets.filterTitle')}</div>

                    {/* Category dropdown */}
                    {uniqueCategories.length > 0 && (
                      <div className="flex flex-col gap-1">
                        <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                          {t('buckets.filterByCategory')}
                        </Label>
                        <Select
                          value={categoryFilter || '__all__'}
                          onValueChange={(val) => setCategoryFilter(val === '__all__' ? '' : val)}
                        >
                          <SelectTrigger
                            size="sm"
                            className={cn(
                              'w-full',
                              'font-sans text-sm text-foreground',
                              'bg-card border border-border rounded-lg',
                              'cursor-pointer shadow-none',
                              'transition-[border-color,box-shadow] duration-150',
                              'focus:border-ring focus:ring-2 focus:ring-ring/20'
                            )}
                          >
                            <SelectValue placeholder={t('buckets.allCategories')} />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="__all__">{t('buckets.allCategories')}</SelectItem>
                            {uniqueCategories.map((cat) => (
                              <SelectItem key={cat} value={cat}>
                                {t(`categories.${cat}`) !== `categories.${cat}`
                                  ? t(`categories.${cat}`)
                                  : cat}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    )}

                    {/* Location dropdown */}
                    {uniqueLocations.length > 0 && (
                      <div className="flex flex-col gap-1">
                        <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                          {t('buckets.filterByLocation')}
                        </Label>
                        <Select
                          value={locationFilter || '__all__'}
                          onValueChange={(val) => setLocationFilter(val === '__all__' ? '' : val)}
                        >
                          <SelectTrigger
                            size="sm"
                            className={cn(
                              'w-full',
                              'font-sans text-sm text-foreground',
                              'bg-card border border-border rounded-lg',
                              'cursor-pointer shadow-none',
                              'transition-[border-color,box-shadow] duration-150',
                              'focus:border-ring focus:ring-2 focus:ring-ring/20'
                            )}
                          >
                            <SelectValue placeholder={t('buckets.allLocations')} />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="__all__">{t('buckets.allLocations')}</SelectItem>
                            {uniqueLocations.map((loc) => (
                              <SelectItem key={loc} value={loc}>{loc}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    )}

                    <div className="flex items-center justify-between pt-1 border-t border-border">
                      <Button
                        variant="ghost"
                        size="xs"
                        className={cn(
                          'font-sans text-xs text-muted-foreground',
                          'cursor-pointer px-1',
                          'transition-colors duration-150',
                          'hover:text-primary hover:bg-transparent'
                        )}
                        onClick={clearAllFilters}
                      >
                        {t('buckets.clearFilters')}
                      </Button>
                      <Button
                        size="xs"
                        className={cn(
                          'font-sans text-xs font-semibold',
                          'text-primary-foreground bg-primary border-none rounded-md',
                          'px-3 cursor-pointer',
                          'transition-[background] duration-150',
                          'hover:bg-primary/80'
                        )}
                        onClick={() => setShowFilters(false)}
                      >
                        {t('buckets.applyFilters')}
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="text-[11px] text-muted-foreground px-4 py-1 border-b border-border shrink-0">
              {t('buckets.unassignedDesc')}
            </div>

            <Droppable droppableId={UNASSIGNED_ID}>
              {(provided, snapshot) => (
                <div
                  ref={provided.innerRef}
                  {...provided.droppableProps}
                  className={cn(
                    'flex-1 overflow-y-auto p-1 min-h-[60px] transition-[background] duration-150',
                    snapshot.isDraggingOver && 'bg-primary/10'
                  )}
                >
                  {unassignedCards.length === 0 && (
                    <div className="flex items-center justify-center px-4 py-8 text-xs text-muted-foreground italic">
                      {t('buckets.empty')}
                    </div>
                  )}
                  {unassignedCards.map((story, index) => (
                    <StoryCard
                      key={story.id}
                      story={story}
                      index={index}
                      onClick={handleCardClick}
                      t={t}
                    />
                  ))}
                  {provided.placeholder}
                </div>
              )}
            </Droppable>
          </div>

          {/* Scrollable pages area (right) */}
          <div className="flex gap-3 overflow-x-auto overflow-y-hidden flex-1 min-h-0 p-3 items-stretch scroll-smooth [&::-webkit-scrollbar]:h-1.5 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-muted-foreground [&::-webkit-scrollbar-thumb]:rounded-full">
            {pages.map((page) => {
              const cards = filteredAssignments[page.id] || [];
              const isEditing = editingPageId === page.id;

              return (
                <div className="flex-none w-[280px] min-w-[280px] flex flex-col bg-background rounded-xl border border-border overflow-hidden" key={page.id}>
                  <div className="group/colheader flex items-center gap-1 py-2 pl-4 pr-2 border-b border-border shrink-0">
                    <div className="w-1 h-[22px] rounded-full shrink-0 bg-primary" />

                    {isEditing ? (
                      <div className="flex items-center gap-1 flex-1 min-w-0">
                        <Input
                          ref={editInputRef}
                          className={cn(
                            'flex-1 min-w-0 px-1 py-0.5 h-auto',
                            'font-sans text-sm font-semibold text-foreground',
                            'bg-card border border-primary rounded-md outline-none',
                            'shadow-none focus-visible:ring-0 focus-visible:border-primary'
                          )}
                          value={editTitle}
                          onChange={(e) => setEditTitle(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') savePageTitle();
                            if (e.key === 'Escape') {
                              setEditingPageId(null);
                              setEditTitle('');
                            }
                          }}
                          onBlur={savePageTitle}
                        />
                        <Button
                          variant="ghost"
                          size="icon-xs"
                          className={cn(
                            'w-[22px] h-[22px]',
                            'bg-primary border-none rounded-md',
                            'text-primary-foreground cursor-pointer shrink-0',
                            'hover:bg-primary/80 hover:text-primary-foreground'
                          )}
                          onMouseDown={(e) => e.preventDefault()}
                          onClick={savePageTitle}
                        >
                          <Check size={14} />
                        </Button>
                      </div>
                    ) : (
                      <>
                        <span className="text-sm font-semibold text-foreground flex-1 whitespace-nowrap overflow-hidden text-ellipsis">
                          {page.page_name || `Page ${page.page_number}`}
                        </span>
                        <Button
                          variant="ghost"
                          size="icon-xs"
                          className={cn(
                            'w-[22px] h-[22px]',
                            'text-muted-foreground cursor-pointer shrink-0',
                            'opacity-0 transition-[opacity,background] duration-150',
                            'group-hover/colheader:opacity-100',
                            'hover:bg-accent hover:text-primary'
                          )}
                          onClick={() => startEditTitle(page.id, page.page_name || '')}
                          aria-label="Edit page title"
                        >
                          <Pencil size={12} />
                        </Button>
                      </>
                    )}

                    <span className="inline-flex items-center justify-center min-w-[22px] h-5 px-1 text-[11px] font-semibold text-muted-foreground bg-muted rounded-full shrink-0">
                      {cards.length}
                    </span>
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      className={cn(
                        'w-6 h-6',
                        'text-muted-foreground cursor-pointer shrink-0',
                        'opacity-0 transition-[opacity,background,color] duration-150',
                        'group-hover/colheader:opacity-100',
                        'hover:bg-[#FEE2E2] hover:text-[#EF4444]'
                      )}
                      onClick={() => handleDeletePage(page.id)}
                      aria-label="Delete page"
                      title="Delete page"
                    >
                      <Trash2 size={14} />
                    </Button>
                  </div>

                  <Droppable droppableId={String(page.id)}>
                    {(provided, snapshot) => (
                      <div
                        ref={provided.innerRef}
                        {...provided.droppableProps}
                        className={cn(
                          'flex-1 overflow-y-auto p-1 min-h-[60px] transition-[background] duration-150',
                          snapshot.isDraggingOver && 'bg-primary/10'
                        )}
                      >
                        {cards.length === 0 && (
                          <div className="flex items-center justify-center px-4 py-8 text-xs text-muted-foreground italic">
                            {t('buckets.empty')}
                          </div>
                        )}
                        {cards.map((story, index) => (
                          <StoryCard
                            key={story.id}
                            story={story}
                            index={index}
                            onClick={handleCardClick}
                            t={t}
                          />
                        ))}
                        {provided.placeholder}
                      </div>
                    )}
                  </Droppable>
                </div>
              );
            })}
          </div>
        </div>
      </DragDropContext>
    </div>
  );
}
