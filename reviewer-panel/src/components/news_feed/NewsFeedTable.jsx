import { CheckCircle2, ExternalLink, Layers, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { categoryDotColor } from '../../utils/categoryColors';
import { useI18n } from '../../i18n';
import ArticleHoverPeek from './ArticleHoverPeek';

// Column geometry — header and rows must use this same string so the
// columns line up. Story title gets the most space; actions sit on the
// right (View Original + Create Story). Source is a coloured chip.
const GRID_COLS =
  'minmax(0,3fr) 100px 130px 130px 200px';

// Same 'time ago' formatter the card view used. Kept inline so the
// table is self-contained and we don't drag a util across the codebase
// for one consumer.
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

export default function NewsFeedTable({
  articles,
  loading,
  createdIds,
  onCreateStory,
}) {
  const { t } = useI18n();

  if (loading && articles.length === 0) {
    return (
      <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
        {t('common.loading') || 'Loading…'}
      </div>
    );
  }

  if (!loading && articles.length === 0) {
    return (
      <div className="flex h-40 flex-col items-center justify-center gap-1 text-sm text-muted-foreground">
        <span className="text-base font-medium text-foreground">
          {t('newsFeed.noArticles') || 'No articles found.'}
        </span>
      </div>
    );
  }

  return (
    <div role="grid" className="divide-y divide-border/80">
      {/* Sticky header — same chrome as the dashboard queue */}
      <div
        className="sticky top-0 z-10 grid items-center gap-4 bg-background/95 px-4 text-[11px] font-medium uppercase tracking-wider text-muted-foreground backdrop-blur"
        style={{ gridTemplateColumns: GRID_COLS, height: 36 }}
      >
        <div>{t('newsFeed.colTitle') || 'Article'}</div>
        <div>{t('newsFeed.colTime') || 'Published'}</div>
        <div>{t('newsFeed.source') || 'Source'}</div>
        <div>{t('newsFeed.colCategory') || 'Category'}</div>
        <div className="text-right">{t('table.action') || 'Actions'}</div>
      </div>

      {articles.map((article) => {
        const isCreated = createdIds?.has(article.id);
        const hasRelated = article.related && article.related.length > 0;
        return (
          <div
            key={article.id}
            role="row"
            data-row-id={article.id}
            className="group grid items-center gap-4 px-4 transition-colors hover:bg-accent/40"
            style={{ gridTemplateColumns: GRID_COLS, minHeight: 56 }}
          >
            {/* Title — hover-peek on the text, coral on direct hover.
                line-clamp-2 lets longer headlines breathe without
                blowing up the row. */}
            <div className="min-w-0 py-2">
              <div className="text-[13.5px] font-medium leading-snug text-foreground">
                <ArticleHoverPeek article={article}>
                  <span className="cursor-pointer transition-colors hover:text-primary line-clamp-2">
                    {article.title}
                  </span>
                </ArticleHoverPeek>
              </div>
              {hasRelated && (
                <div className="mt-0.5 inline-flex items-center gap-1 text-[10px] text-muted-foreground">
                  <Layers size={9} />
                  <span>+{article.related.length} {article.related.length > 1 ? 'sources' : 'source'}</span>
                </div>
              )}
            </div>

            {/* Time */}
            <div className="text-xs tabular-nums text-muted-foreground">
              {timeAgo(article.published_at)}
            </div>

            {/* Source — neutral muted pill. Earlier this used the brand
                coral (bg-primary/10 text-primary) but with 25 rows the
                page read as wall-to-wall orange. The source name is
                informational, not actionable; differentiation by
                article happens in the title + category dot. */}
            <div className="min-w-0">
              {article.source ? (
                <span className="inline-block max-w-full truncate rounded-full border border-border/60 bg-muted/40 px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
                  {article.source}
                </span>
              ) : (
                <span className="text-xs text-muted-foreground">—</span>
              )}
            </div>

            {/* Category — dot + capitalised label */}
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span
                className="inline-block size-1.5 shrink-0 rounded-full"
                style={{ backgroundColor: categoryDotColor(article.category) }}
              />
              <span className="truncate capitalize">{article.category || '—'}</span>
            </div>

            {/* Actions — view original + create story / created badge */}
            <div className="flex items-center justify-end gap-2">
              <a
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-[11px] font-medium text-muted-foreground transition-colors hover:text-foreground"
                onClick={(e) => e.stopPropagation()}
              >
                <ExternalLink size={11} />
                {t('newsFeed.viewOriginal') || 'View'}
              </a>
              {isCreated ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 ring-1 ring-emerald-200/60">
                  <CheckCircle2 size={11} />
                  {t('newsFeed.created') || 'Created'}
                </span>
              ) : (
                // Outline variant — orange Sparkles icon + text, no
                // orange fill. With 25 rows the filled-orange button
                // turned the page into a coral grid; outline keeps the
                // CTA discoverable without dominating.
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 gap-1 border-primary/40 px-2 text-[11px] text-primary hover:bg-primary/10 hover:text-primary"
                  onClick={() => onCreateStory?.(article)}
                >
                  <Sparkles size={11} />
                  {t('newsFeed.createStory') || 'Create Story'}
                </Button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
