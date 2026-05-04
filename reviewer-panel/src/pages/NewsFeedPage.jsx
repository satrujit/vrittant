import { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Search, X } from 'lucide-react';
import { useI18n } from '../i18n';
import {
  fetchNewsArticles,
  researchStoryFromArticle,
  confirmResearchedStory,
} from '../services/api';
import { cn } from '@/lib/utils';
import { SearchableSelect } from '../components/common';
import NewsFeedTable from '../components/news_feed/NewsFeedTable';
import StoryPreviewDialog from '../components/StoryPreviewDialog';

// Featured news sources reviewers reach for most often. Each entry has a
// short user-facing label and an array of substring matchers used to find
// the actual source string in the loaded `sources` list (case-insensitive)
// — the canonical strings in the DB sometimes vary (e.g. "Odisha TV" vs
// "OTV", "The Hindu" vs "Hindu"), so we resolve at runtime instead of
// hard-coding which exact string to filter by.
const QUICK_SOURCES = [
  { label: 'Times of India',  matchers: ['times of india', 'toi'] },
  { label: 'The Hindu',       matchers: ['the hindu'] },
  { label: 'Indian Express',  matchers: ['indian express'] },
  { label: 'Hindustan Times', matchers: ['hindustan times'] },
  { label: 'OTV',             matchers: ['odisha tv', 'otv'] },
];

const PAGE_SIZE = 25;

export default function NewsFeedPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [articles, setArticles] = useState([]);
  const [total, setTotal] = useState(0);
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [source, setSource] = useState('');
  // Page lives in the URL so opening a story preview and returning here
  // restores the same page (instead of snapping back to page 1).
  const [searchParams, setSearchParams] = useSearchParams();
  const page = Math.max(1, parseInt(searchParams.get('page') || '1', 10) || 1);
  const setPage = useCallback((updater) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      const cur = Math.max(1, parseInt(next.get('page') || '1', 10) || 1);
      const value = typeof updater === 'function' ? updater(cur) : updater;
      if (!value || value === 1) next.delete('page');
      else next.set('page', String(value));
      return next;
    }, { replace: true });
  }, [setSearchParams]);

  // AI research flow (two-phase: configure → generate → preview)
  const [dialogArticle, setDialogArticle] = useState(null); // source article for context
  const [previewData, setPreviewData] = useState(null);
  const [previewArticleId, setPreviewArticleId] = useState(null);
  const [confirming, setConfirming] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [createdIds, setCreatedIds] = useState(new Set());

  const loadArticles = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        offset: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      };
      if (search) params.search = search;
      if (category) params.category = category;
      if (source) params.source = source;

      const data = await fetchNewsArticles(params);
      setArticles(data.articles || []);
      setTotal(data.total || 0);
      if (data.sources) setSources(data.sources);
    } catch (err) {
      console.error('Failed to fetch news articles:', err);
    } finally {
      setLoading(false);
    }
  }, [page, search, category, source]);

  useEffect(() => {
    loadArticles();
  }, [loadArticles]);

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, category, source]);

  // Step 1: Open config dialog (no API call yet)
  const handleOpenConfig = (article) => {
    setDialogArticle(article);
    setPreviewArticleId(article.id);
    setPreviewData(null);
  };

  // Step 2: Generate (called from dialog after user sets instructions + word count + selected articles)
  const handleGenerate = async ({ instructions, wordCount, articleIds }) => {
    if (!previewArticleId) return;
    setGenerating(true);
    setPreviewData(null);
    try {
      // Pass the full selection — backend uses it as-is so the user can
      // deselect the route's primary and pick any other articles as sources.
      const preview = await researchStoryFromArticle(previewArticleId, {
        instructions,
        wordCount,
        sourceArticleIds: articleIds || [],
      });
      setPreviewData(preview);
    } catch (err) {
      console.error('Failed to generate story:', err);
    } finally {
      setGenerating(false);
    }
  };

  // Confirm → save to DB
  const handleConfirm = async () => {
    if (!previewData || !previewArticleId) return;
    setConfirming(true);
    try {
      const paragraphs = [];
      if (previewData.body) {
        paragraphs.push({ text: previewData.body, type: 'text' });
      }
      const result = await confirmResearchedStory(previewArticleId, {
        headline: previewData.headline,
        paragraphs,
        category: previewData.category,
        location: previewData.location,
      });
      setCreatedIds((prev) => new Set(prev).add(previewArticleId));
      setPreviewData(null);
      setPreviewArticleId(null);
      // Close modal and jump straight into reviewing the new story
      if (result?.story_id) {
        navigate(`/review/${result.story_id}`);
      }
    } catch (err) {
      console.error('Failed to confirm story:', err);
    } finally {
      setConfirming(false);
    }
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  const categories = [
    { value: '', label: t('allStories.all', 'All') },
    { value: 'general', label: 'General' },
    { value: 'regional', label: 'Odisha / Regional' },
    { value: 'politics', label: 'Politics' },
    { value: 'sports', label: 'Sports' },
    { value: 'entertainment', label: 'Entertainment' },
    { value: 'business', label: 'Business' },
    { value: 'technology', label: 'Technology' },
    { value: 'crime', label: 'Crime' },
    { value: 'health', label: 'Health' },
    { value: 'education', label: 'Education' },
  ];

  // Resolve each QUICK_SOURCES entry to its actual source string in the
  // loaded list so the chips set the precise value the backend filter
  // expects. Chips with no match get null and are still rendered (so the
  // strip shape stays stable) but disabled with a hint that the source
  // hasn't ingested any articles yet.
  const resolvedQuickSources = useMemo(() => {
    return QUICK_SOURCES.map((qs) => {
      const lower = sources.map((s) => ({ orig: s, low: s.toLowerCase() }));
      const hit = lower.find((s) => qs.matchers.some((m) => s.low.includes(m)));
      return { label: qs.label, value: hit?.orig || null };
    });
  }, [sources]);

  return (
    <div className="flex h-full flex-col">
      {/* Header strip — same shape as the dashboard: title + inline stat
          + filters beneath in a single tight row. */}
      <header className="flex flex-wrap items-center justify-between gap-4 px-6 pt-6">
        <div className="flex flex-col gap-1">
          <h1 className="text-xl font-semibold tracking-tight text-foreground">
            {t('newsFeed.title') || 'News Feed'}
          </h1>
          <div className="flex items-baseline gap-1.5 text-[13px] text-muted-foreground">
            <span className="font-semibold tabular-nums text-foreground">
              {loading ? '—' : (total ?? 0).toLocaleString()}
            </span>
            <span>{t('newsFeed.showingResults', '{total} articles').replace('{total} ', '').replace('{total}', '')}</span>
          </div>
        </div>
      </header>

      {/* Quick-source chips — one-click jump to a featured source.
          Clicking the active chip clears the filter; chips for sources
          that haven't ingested an article yet are disabled. */}
      <div className="flex flex-wrap items-center gap-1.5 px-6 pt-3">
        <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          {t('newsFeed.quickSources') || 'Quick sources'}
        </span>
        <div className="flex items-center gap-0.5 rounded-md border border-border/60 bg-card p-0.5">
          {resolvedQuickSources.map((qs) => {
            const active = qs.value && qs.value === source;
            return (
              <button
                key={qs.label}
                type="button"
                disabled={!qs.value}
                onClick={() => setSource(active ? '' : qs.value)}
                aria-pressed={active}
                className={cn(
                  'rounded-[5px] px-2 py-1 text-[11.5px] font-medium transition-colors',
                  active
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-accent hover:text-foreground',
                  !qs.value && 'cursor-default opacity-40 hover:bg-transparent hover:text-muted-foreground',
                )}
                title={qs.value ? qs.label : `${qs.label} — no articles ingested yet`}
              >
                {qs.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Filter bar — matches Dashboard / All Stories chrome: h-7,
          text-[11.5px], gap-1.5, search-icon left, border-b underline.
          Search left, category + source dropdowns next to it, clear
          button when any filter is set. */}
      <div className="px-6">
        <div className="flex flex-wrap items-center gap-1.5 border-b border-border/60 px-1 py-2.5">
          <div className="relative">
            <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t('newsFeed.searchPlaceholder', 'Search articles...')}
              className="h-7 w-44 rounded-md border border-border/60 bg-card pl-7 pr-7 text-[11.5px] outline-none transition-colors focus:border-ring focus:shadow-[0_0_0_3px_rgba(250,108,56,0.08)]"
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch('')}
                className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-0.5 text-muted-foreground hover:bg-accent"
                aria-label="Clear search"
              >
                <X size={12} />
              </button>
            )}
          </div>

          <SearchableSelect
            triggerClassName="h-7 text-[11.5px] border-border/60 px-2 min-w-[120px]"
            value={category}
            onChange={setCategory}
            placeholder={t('allStories.all', 'All categories')}
            allLabel={t('allStories.all', 'All categories')}
            options={categories
              .filter((c) => c.value)
              .map((c) => ({ value: c.value, label: c.label }))}
          />

          {sources.length > 0 && (
            <SearchableSelect
              triggerClassName="h-7 text-[11.5px] border-border/60 px-2 min-w-[120px] max-w-[160px]"
              value={source}
              onChange={setSource}
              placeholder={t('newsFeed.allSources', 'All sources')}
              allLabel={t('newsFeed.allSources', 'All sources')}
              options={sources.map((s) => ({ value: s, label: s }))}
            />
          )}

          {(category || source || search) && (
            <button
              type="button"
              onClick={() => { setCategory(''); setSource(''); setSearch(''); }}
              className="inline-flex h-7 items-center gap-1 rounded-md px-2 text-[11.5px] text-muted-foreground hover:bg-accent hover:text-foreground"
            >
              <X size={12} />
              {t('allStories.clearFilters', 'Clear')}
            </button>
          )}
        </div>
      </div>

      {/* Table + pagination — table scrolls, pager is sticky below. */}
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="flex-1 overflow-y-auto px-6 pb-6">
          <NewsFeedTable
            articles={articles}
            loading={loading}
            createdIds={createdIds}
            onCreateStory={handleOpenConfig}
          />
        </div>
        {totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-border/40 px-6 py-2 text-xs text-muted-foreground">
            <span>
              {((page - 1) * PAGE_SIZE) + 1}–{Math.min(total, page * PAGE_SIZE)} of {total}
            </span>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                aria-label="Previous page"
                className="rounded-md border border-border/60 bg-card px-2 py-1 transition-colors hover:bg-accent disabled:opacity-40 disabled:hover:bg-card"
              >
                ←
              </button>
              <button
                type="button"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                aria-label="Next page"
                className="rounded-md border border-border/60 bg-card px-2 py-1 transition-colors hover:bg-accent disabled:opacity-40 disabled:hover:bg-card"
              >
                →
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Two-phase dialog: configure → generate → preview */}
      <StoryPreviewDialog
        open={!!dialogArticle || !!previewData || generating}
        onOpenChange={(open) => {
          if (!open) {
            setDialogArticle(null);
            setPreviewData(null);
            setPreviewArticleId(null);
          }
        }}
        article={dialogArticle}
        preview={previewData}
        onGenerate={handleGenerate}
        onConfirm={handleConfirm}
        confirming={confirming}
        generating={generating}
      />
    </div>
  );
}
