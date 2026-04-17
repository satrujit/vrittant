import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { DragDropContext } from '@hello-pangea/dnd';
import { Loader2 } from 'lucide-react';
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
} from '../services/api';
import UnassignedPanel from '../components/buckets/UnassignedPanel';
import BucketColumn from '../components/buckets/BucketColumn';
import BucketDetailHeader from '../components/buckets/BucketDetailHeader';
import { buildEditionDisplayTitle } from '../components/buckets/editionTitle';

const UNASSIGNED_ID = 'unassigned';

/**
 * Detail view for a single edition: kanban-style page columns + unassigned panel.
 * Mounted at `/buckets/:editionId`.
 */
export default function BucketDetailPage() {
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

      if (q) {
        filtered = filtered.filter(
          (c) =>
            c.headline?.toLowerCase().includes(q) ||
            c.reporter?.name?.toLowerCase().includes(q) ||
            c.bodyText?.toLowerCase().includes(q)
        );
      }

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

    const destPageId = destination.droppableId;
    const srcPageId = source.droppableId;

    if (destPageId !== UNASSIGNED_ID) {
      setAssignments((current) => {
        const destStoryIds = (current[destPageId] || []).map((s) => s.id);
        assignStoriesToPage(editionId, destPageId, destStoryIds).catch((err) => {
          console.error('Failed to assign stories to page:', err);
        });
        return current;
      });
    }

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

  const cancelEditTitle = () => {
    setEditingPageId(null);
    setEditTitle('');
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

  const cancelEditEditionTitle = () => {
    setEditingEditionTitle(false);
    setEditionTitleDraft('');
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

  const cancelAddPage = () => {
    setShowAddPage(false);
    setNewPageName('');
  };

  const unassignedCards = filteredAssignments[UNASSIGNED_ID] || [];
  const hasActiveFilters = !!categoryFilter || !!locationFilter;

  const editionDisplayTitle = useMemo(
    () => buildEditionDisplayTitle(edition, t, t('buckets.editionTitle')),
    [edition, t]
  );

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
      <BucketDetailHeader
        editionDisplayTitle={editionDisplayTitle}
        editingEditionTitle={editingEditionTitle}
        editionTitleDraft={editionTitleDraft}
        setEditionTitleDraft={setEditionTitleDraft}
        editionTitleInputRef={editionTitleInputRef}
        onStartEditEditionTitle={startEditEditionTitle}
        onSaveEditionTitle={saveEditionTitle}
        onCancelEditEditionTitle={cancelEditEditionTitle}
        onBack={() => navigate('/buckets')}
        search={search}
        setSearch={setSearch}
        showAddPage={showAddPage}
        setShowAddPage={setShowAddPage}
        pageSuggestions={pageSuggestions}
        newPageName={newPageName}
        setNewPageName={setNewPageName}
        addPageInputRef={addPageInputRef}
        onAddPage={handleAddPage}
        onCancelAddPage={cancelAddPage}
        t={t}
      />

      {/* ── Board ── */}
      <DragDropContext onDragEnd={onDragEnd}>
        <div className="flex flex-1 min-h-0 overflow-x-auto overflow-y-hidden">
          <UnassignedPanel
            droppableId={UNASSIGNED_ID}
            cards={unassignedCards}
            showFilters={showFilters}
            setShowFilters={setShowFilters}
            uniqueCategories={uniqueCategories}
            uniqueLocations={uniqueLocations}
            categoryFilter={categoryFilter}
            setCategoryFilter={setCategoryFilter}
            locationFilter={locationFilter}
            setLocationFilter={setLocationFilter}
            hasActiveFilters={hasActiveFilters}
            clearAllFilters={clearAllFilters}
            onCardClick={handleCardClick}
            t={t}
          />

          <div className="flex gap-3 overflow-x-auto overflow-y-hidden flex-1 min-h-0 p-3 items-stretch scroll-smooth [&::-webkit-scrollbar]:h-1.5 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-muted-foreground [&::-webkit-scrollbar-thumb]:rounded-full">
            {pages.map((page) => (
              <BucketColumn
                key={page.id}
                page={page}
                cards={filteredAssignments[page.id] || []}
                isEditing={editingPageId === page.id}
                editTitle={editTitle}
                setEditTitle={setEditTitle}
                onStartEdit={startEditTitle}
                onSaveTitle={savePageTitle}
                onCancelEdit={cancelEditTitle}
                onDeletePage={handleDeletePage}
                onCardClick={handleCardClick}
                editInputRef={editInputRef}
                t={t}
              />
            ))}
          </div>
        </div>
      </DragDropContext>
    </div>
  );
}
