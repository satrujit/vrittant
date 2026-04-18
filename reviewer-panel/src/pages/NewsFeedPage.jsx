import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  ExternalLink,
  Loader2,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Newspaper,
  CheckCircle2,
  Plus,
  Sparkles,
  Image as ImageIcon,
  Layers,
} from 'lucide-react';
import { useI18n } from '../i18n';
import {
  fetchNewsArticles,
  researchStoryFromArticle,
  confirmResearchedStory,
  createBlankStory,
} from '../services/api';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from '@/components/ui/tooltip';
import StoryPreviewDialog from '../components/StoryPreviewDialog';

const PAGE_SIZE = 16;

function timeAgo(dateStr) {
  if (!dateStr) return '';
  const now = new Date();
  const d = new Date(dateStr);
  const diffMs = now - d;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'Just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH}h ago`;
  const diffD = Math.floor(diffH / 24);
  if (diffD < 7) return `${diffD}d ago`;
  return d.toLocaleDateString();
}

/** Expandable cluster badge showing related articles from other sources */
function RelatedArticles({ related }) {
  const [expanded, setExpanded] = useState(false);

  if (!related || related.length === 0) return null;

  return (
    <div className="border-t border-border mt-1.5 pt-1.5">
      <button
        onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
        className="flex items-center gap-1 text-[10px] font-medium text-muted-foreground hover:text-foreground transition-colors cursor-pointer bg-transparent border-none p-0 w-full"
      >
        <Layers size={10} />
        <span>{related.length} more source{related.length > 1 ? 's' : ''}</span>
        <ChevronDown size={10} className={cn('ml-auto transition-transform', expanded && 'rotate-180')} />
      </button>
      {expanded && (
        <div className="mt-1 space-y-1">
          {related.map((r) => (
            <a
              key={r.id}
              href={r.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-[10px] text-muted-foreground hover:text-foreground transition-colors no-underline"
              onClick={(e) => e.stopPropagation()}
            >
              {r.source && (
                <span className="rounded-full bg-muted px-1.5 py-0.5 font-medium truncate max-w-[80px] shrink-0">
                  {r.source}
                </span>
              )}
              <span className="truncate">{r.title}</span>
              <ExternalLink size={8} className="shrink-0 ml-auto" />
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

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
  const [page, setPage] = useState(1);

  // AI research flow (two-phase: configure → generate → preview)
  const [dialogArticle, setDialogArticle] = useState(null); // source article for context
  const [previewData, setPreviewData] = useState(null);
  const [previewArticleId, setPreviewArticleId] = useState(null);
  const [confirming, setConfirming] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [createdIds, setCreatedIds] = useState(new Set());

  // New story creation
  const [creatingBlank, setCreatingBlank] = useState(false);

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
      // Primary article is the lead; additional are the rest
      const additionalIds = (articleIds || []).filter((id) => id !== previewArticleId);
      const preview = await researchStoryFromArticle(previewArticleId, {
        instructions,
        wordCount,
        additionalArticleIds: additionalIds,
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

  // New blank story
  const handleNewStory = async () => {
    setCreatingBlank(true);
    try {
      const result = await createBlankStory();
      if (result?.story_id) {
        navigate(`/review/${result.story_id}`);
      }
    } catch (err) {
      console.error('Failed to create blank story:', err);
    } finally {
      setCreatingBlank(false);
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

  return (
    <div className="flex flex-col gap-4 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t('newsFeed.title', 'News Feed')}</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">{t('newsFeed.subtitle', 'Latest news articles — create stories from any article.')}</p>
        </div>
        <Button onClick={handleNewStory} disabled={creatingBlank} className="gap-1.5">
          {creatingBlank ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
          {t('newsFeed.newStory', '+ New Story')}
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            className="h-8 w-full rounded-lg border border-border bg-background pl-8 pr-3 text-sm text-foreground outline-none placeholder:text-muted-foreground/60 focus:border-primary focus:shadow-[0_0_0_2px_rgba(250,108,56,0.1)]"
            placeholder={t('newsFeed.searchPlaceholder', 'Search articles...')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          className="h-8 rounded-lg border border-border bg-background px-2.5 text-sm text-foreground outline-none focus:border-primary"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          {categories.map((c) => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>
        {sources.length > 0 && (
          <select
            className="h-8 rounded-lg border border-border bg-background px-2.5 text-sm text-foreground outline-none focus:border-primary"
            value={source}
            onChange={(e) => setSource(e.target.value)}
          >
            <option value="">{t('newsFeed.allSources', 'All Sources')}</option>
            {sources.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        )}
        <div className="ml-auto text-xs text-muted-foreground">
          {!loading && t('newsFeed.showingResults', '{total} articles').replace('{total}', total)}
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 size={24} className="animate-spin text-primary" />
        </div>
      )}

      {/* Empty */}
      {!loading && articles.length === 0 && (
        <div className="flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground">
          <Newspaper size={36} />
          <p className="text-sm">{t('newsFeed.noArticles', 'No articles found.')}</p>
        </div>
      )}

      {/* Card grid */}
      {!loading && articles.length > 0 && (
        <TooltipProvider delayDuration={300}>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {articles.map((article) => {
            const isCreated = createdIds.has(article.id);
            const hasRelated = article.related && article.related.length > 0;

            return (
              <Card
                key={article.id}
                className={cn(
                  'flex flex-col overflow-hidden border bg-card transition-shadow hover:shadow-md',
                  hasRelated ? 'border-primary/30' : 'border-border'
                )}
              >
                {/* Image */}
                <div className="h-[110px] w-full overflow-hidden bg-muted relative">
                  {article.image_url ? (
                    <img
                      src={article.image_url}
                      alt=""
                      className="size-full object-cover"
                      onError={(e) => {
                        const parent = e.target.parentElement;
                        e.target.style.display = 'none';
                        if (!parent.querySelector('.img-placeholder')) {
                          const ph = document.createElement('div');
                          ph.className = 'img-placeholder flex size-full items-center justify-center';
                          ph.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="text-muted-foreground/30"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg>`;
                          parent.appendChild(ph);
                        }
                      }}
                    />
                  ) : (
                    <div className="flex size-full items-center justify-center bg-gradient-to-br from-muted to-muted/60">
                      <ImageIcon size={28} className="text-muted-foreground/25" />
                    </div>
                  )}

                  {/* Cluster badge overlay */}
                  {hasRelated && (
                    <div className="absolute top-1.5 right-1.5 inline-flex items-center gap-1 rounded-full bg-black/60 px-1.5 py-0.5 text-[10px] font-medium text-white backdrop-blur-sm">
                      <Layers size={9} />
                      {article.related.length + 1}
                    </div>
                  )}
                </div>

                <div className="flex flex-1 flex-col gap-1.5 p-3">
                  {/* Source + Category + Time */}
                  <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                    {article.source && (
                      <span className="rounded-full bg-primary/10 px-1.5 py-0.5 font-medium text-primary truncate max-w-[100px]">
                        {article.source}
                      </span>
                    )}
                    {article.category && (
                      <span className="rounded-full bg-muted px-1.5 py-0.5 text-muted-foreground capitalize">
                        {article.category}
                      </span>
                    )}
                    <span className="ml-auto text-muted-foreground whitespace-nowrap">
                      {timeAgo(article.published_at)}
                    </span>
                  </div>

                  {/* Title */}
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <h3 className="line-clamp-2 cursor-default text-[13px] font-semibold leading-snug text-foreground">
                        {article.title}
                      </h3>
                    </TooltipTrigger>
                    <TooltipContent
                      side="bottom"
                      sideOffset={6}
                      className="max-w-[320px] rounded-xl border border-border/50 bg-popover px-4 py-3 text-[13px] font-medium leading-relaxed text-popover-foreground shadow-xl shadow-black/10 backdrop-blur-sm"
                    >
                      {article.title}
                    </TooltipContent>
                  </Tooltip>

                  {/* Description */}
                  {article.description && (
                    <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                      {article.description}
                    </p>
                  )}

                  {/* Related articles (clustered) */}
                  <RelatedArticles related={article.related} />

                  {/* Spacer */}
                  <div className="flex-1" />

                  {/* Actions */}
                  <div className="flex items-center gap-2 pt-1.5 border-t border-border">
                    <a
                      href={article.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-[11px] font-medium text-muted-foreground hover:text-foreground transition-colors"
                    >
                      <ExternalLink size={11} />
                      View Original
                    </a>

                    <div className="ml-auto">
                      {isCreated ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-green-50 px-2 py-0.5 text-[11px] font-medium text-green-700">
                          <CheckCircle2 size={11} />
                          Story Created
                        </span>
                      ) : (
                        <Button
                          size="sm"
                          className="h-6 gap-1 px-2 text-[11px]"
                          onClick={() => handleOpenConfig(article)}
                        >
                          <Sparkles size={11} />
                          Create Story
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
        </TooltipProvider>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 py-1">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
          >
            <ChevronLeft size={14} />
          </Button>
          <span className="text-sm text-muted-foreground">
            {page} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
          >
            <ChevronRight size={14} />
          </Button>
        </div>
      )}

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
