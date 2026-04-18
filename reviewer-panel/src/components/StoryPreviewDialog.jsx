import { useState, useEffect, useMemo } from 'react';
import { Loader2, ExternalLink, RefreshCw, Sparkles, Check, ChevronDown, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { fetchRelatedArticles } from '../services/api';
import { useSidebarCollapsed } from '../hooks/useSidebarCollapsed';

const WORD_PRESETS = [200, 400, 600, 800, 1000];
const MAX_SOURCES = 3;

/**
 * StoryPreviewDialog — split-panel story generator.
 *   Left: source articles (auto-fetched related) with full content, toggleable
 *   Right: generated Odia article preview
 */
export default function StoryPreviewDialog({
  open,
  onOpenChange,
  article,
  preview,
  onGenerate,
  onConfirm,
  confirming,
  generating,
}) {
  const [collapsed] = useSidebarCollapsed();
  const [instructions, setInstructions] = useState('');
  const [wordCount, setWordCount] = useState(400);
  const [relatedArticles, setRelatedArticles] = useState([]);
  const [loadingRelated, setLoadingRelated] = useState(false);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [expandedId, setExpandedId] = useState(null);

  // Fetch related articles when dialog opens with a new article
  useEffect(() => {
    if (!article?.id || !open) return;
    setLoadingRelated(true);
    setRelatedArticles([]);
    setSelectedIds(new Set([article.id]));
    setExpandedId(article.id);
    fetchRelatedArticles(article.id)
      .then((data) => {
        const related = Array.isArray(data) ? data : [];
        setRelatedArticles(related);
        // Auto-select up to MAX_SOURCES related articles
        const autoSelected = related.slice(0, MAX_SOURCES - 1).map((r) => r.id);
        setSelectedIds(new Set([article.id, ...autoSelected]));
      })
      .catch((err) => {
        console.error('Failed to fetch related articles:', err);
      })
      .finally(() => setLoadingRelated(false));
  }, [article?.id, open]);

  // Reset state when dialog closes
  useEffect(() => {
    if (!open) {
      setInstructions('');
      setWordCount(400);
      setExpandedId(null);
    }
  }, [open]);

  // All sources: lead article + related
  const allSources = useMemo(() => {
    if (!article) return [];
    return [article, ...relatedArticles];
  }, [article, relatedArticles]);

  const toggleSource = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        if (next.size <= 1) return prev;
        next.delete(id);
      } else {
        if (next.size >= MAX_SOURCES) return prev; // enforce max
        next.add(id);
      }
      return next;
    });
  };

  if (!article || !open) return null;

  const handleGenerate = () => {
    const ids = Array.from(selectedIds);
    onGenerate?.({
      instructions: instructions.trim() || undefined,
      wordCount,
      articleIds: ids,
    });
  };

  const selectedCount = selectedIds.size;

  return (
    <div
      className={cn(
        'fixed inset-y-0 right-0 z-[90] bg-background flex flex-col transition-[left] duration-200',
        collapsed ? 'left-[64px]' : 'left-[240px]'
      )}
    >
      {/* Close button */}
      <button
        onClick={() => onOpenChange(false)}
        className="absolute top-4 right-4 z-10 size-8 rounded-md flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-accent transition-colors cursor-pointer bg-transparent border-none"
        aria-label="Close"
      >
        <X size={18} />
      </button>

      {/* Split panel */}
      <div className="flex flex-1 min-h-0">
          {/* LEFT — Source articles reader */}
          <div className="w-[480px] shrink-0 border-r border-border flex flex-col overflow-hidden bg-muted/20">
            {/* Header */}
            <div className="px-4 pt-4 pb-2 border-b border-border bg-background">
              <h2 className="text-sm font-semibold text-foreground">
                Source Articles
                {!loadingRelated && (
                  <span className="text-muted-foreground font-normal ml-1">
                    ({selectedCount}/{MAX_SOURCES} selected)
                  </span>
                )}
              </h2>
              {loadingRelated && (
                <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                  <Loader2 size={10} className="animate-spin" />
                  Finding related articles...
                </p>
              )}
            </div>

            {/* Scrollable article list */}
            <div className="flex-1 overflow-y-auto">
              {allSources.map((src, idx) => {
                const isSelected = selectedIds.has(src.id);
                const isExpanded = expandedId === src.id;
                const isLead = idx === 0;

                return (
                  <div
                    key={src.id}
                    className={cn(
                      'border-b border-border transition-colors',
                      isSelected ? 'bg-background' : 'bg-muted/30 opacity-60'
                    )}
                  >
                    {/* Article header — click to expand */}
                    <div
                      className="flex items-start gap-2 px-4 py-3 cursor-pointer hover:bg-accent/50 transition-colors"
                      onClick={() => setExpandedId(isExpanded ? null : src.id)}
                    >
                      {/* Checkbox */}
                      <button
                        onClick={(e) => { e.stopPropagation(); toggleSource(src.id); }}
                        className={cn(
                          'size-4 rounded border flex items-center justify-center shrink-0 mt-0.5 transition-colors cursor-pointer bg-transparent',
                          isSelected
                            ? 'bg-primary border-primary text-white'
                            : 'border-muted-foreground/40'
                        )}
                      >
                        {isSelected && <Check size={10} strokeWidth={3} />}
                      </button>

                      <div className="flex-1 min-w-0">
                        <p className="text-[13px] font-semibold text-foreground leading-snug">
                          {src.title}
                        </p>
                        <div className="flex items-center gap-2 mt-1">
                          {src.source && (
                            <span className="rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                              {src.source}
                            </span>
                          )}
                          {isLead && (
                            <span className="rounded-full bg-foreground/10 px-1.5 py-0.5 text-[10px] font-medium text-foreground">
                              Primary
                            </span>
                          )}
                        </div>
                      </div>

                      <ChevronDown
                        size={14}
                        className={cn(
                          'shrink-0 text-muted-foreground transition-transform mt-1',
                          isExpanded && 'rotate-180'
                        )}
                      />
                    </div>

                    {/* Expanded content — full article text */}
                    {isExpanded && (
                      <div className="px-4 pb-4 pl-10">
                        {src.image_url && (
                          <img
                            src={src.image_url}
                            alt=""
                            className="w-full max-h-[140px] object-cover rounded-lg mb-3"
                            onError={(e) => { e.target.style.display = 'none'; }}
                          />
                        )}
                        {src.description ? (
                          <p className="text-xs leading-relaxed text-muted-foreground whitespace-pre-wrap">
                            {src.description}
                          </p>
                        ) : (
                          <p className="text-xs text-muted-foreground/50 italic">
                            No description available
                          </p>
                        )}
                        <a
                          href={src.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 mt-2 text-[11px] font-medium text-primary hover:underline"
                        >
                          <ExternalLink size={10} />
                          Read full article
                        </a>
                      </div>
                    )}
                  </div>
                );
              })}

              {!loadingRelated && allSources.length === 1 && (
                <div className="px-4 py-6 text-center text-xs text-muted-foreground italic">
                  No related articles found from other sources.
                </div>
              )}
            </div>

            {/* Config + Generate */}
            <div className="border-t border-border p-4 space-y-3 bg-background">
              {/* Word count */}
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-foreground shrink-0">Words:</span>
                <div className="inline-flex items-center bg-muted rounded-lg p-0.5 gap-0.5">
                  {WORD_PRESETS.map((w) => (
                    <button
                      key={w}
                      onClick={() => setWordCount(w)}
                      className={cn(
                        'px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors cursor-pointer border-none',
                        wordCount === w
                          ? 'bg-background text-foreground shadow-sm'
                          : 'text-muted-foreground hover:text-foreground bg-transparent'
                      )}
                    >
                      {w}
                    </button>
                  ))}
                </div>
              </div>

              {/* Instructions */}
              <textarea
                className="w-full h-14 rounded-lg border border-border bg-background px-3 py-2 text-xs text-foreground outline-none placeholder:text-muted-foreground/50 focus:border-primary resize-none"
                placeholder="Instructions: Focus on Odisha angle, include quotes, political context..."
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
              />

              {/* Generate / Regenerate button */}
              <Button
                className="w-full gap-1.5"
                onClick={handleGenerate}
                disabled={generating || selectedCount === 0}
              >
                {generating ? (
                  <>
                    <Loader2 size={14} className="animate-spin" />
                    Generating...
                  </>
                ) : preview ? (
                  <>
                    <RefreshCw size={14} />
                    Regenerate
                  </>
                ) : (
                  <>
                    <Sparkles size={14} />
                    Generate ({selectedCount} source{selectedCount > 1 ? 's' : ''})
                  </>
                )}
              </Button>
            </div>
          </div>

          {/* RIGHT — Generated article preview */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {!preview && !generating ? (
              <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground gap-3 p-8">
                <Sparkles size={36} className="opacity-15" />
                <div className="text-center space-y-1">
                  <p className="text-sm font-medium">Generated Article</p>
                  <p className="text-xs">
                    Read through the sources on the left, then click Generate.
                  </p>
                </div>
              </div>
            ) : generating ? (
              <div className="flex-1 flex flex-col items-center justify-center gap-3 text-muted-foreground p-8">
                <Loader2 size={28} className="animate-spin text-primary" />
                <p className="text-sm">
                  Generating {wordCount}-word article from {selectedCount} source{selectedCount > 1 ? 's' : ''}...
                </p>
              </div>
            ) : (
              <>
                <div className="flex-1 overflow-y-auto p-6 space-y-4">
                  {/* Category + Location */}
                  <div className="flex flex-wrap items-center gap-2">
                    {preview.category && (
                      <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary capitalize">
                        {preview.category}
                      </span>
                    )}
                    {preview.location && (
                      <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs text-muted-foreground">
                        {preview.location}
                      </span>
                    )}
                  </div>

                  {preview.image_url && (
                    <div className="w-full overflow-hidden rounded-lg bg-muted">
                      <img
                        src={preview.image_url}
                        alt=""
                        className="w-full max-h-[180px] object-cover"
                        onError={(e) => { e.target.parentElement.style.display = 'none'; }}
                      />
                    </div>
                  )}

                  <h2 className="text-xl font-bold leading-snug text-foreground">
                    {preview.headline}
                  </h2>

                  <div className="text-[15px] leading-relaxed text-foreground whitespace-pre-wrap">
                    {preview.body}
                  </div>
                </div>

                {/* Submit footer */}
                <div className="border-t border-border px-6 py-3 flex justify-end gap-2 bg-background">
                  <Button variant="outline" onClick={() => onOpenChange(false)} disabled={confirming}>
                    Cancel
                  </Button>
                  <Button onClick={onConfirm} disabled={confirming}>
                    {confirming ? (
                      <>
                        <Loader2 size={14} className="animate-spin mr-1" />
                        Saving...
                      </>
                    ) : (
                      'Submit Story'
                    )}
                  </Button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
  );
}
