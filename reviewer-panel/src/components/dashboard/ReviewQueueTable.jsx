import { useNavigate } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Avatar } from '../common';
import { formatDate } from '../../utils/helpers';
import { useI18n } from '../../i18n';
import { DENSITIES } from '../../hooks/useDensityPreference';
import InlineStatusPill from './InlineStatusPill';
import RowHoverPeek from './RowHoverPeek';

// Per-category dot colour. Stable mapping so the same category always reads
// the same hue across the panel. Falls back to slate for unknown categories.
const CATEGORY_DOT = {
  general:        '#94a3b8', // slate
  crime:          '#ef4444', // red
  governance:     '#3b82f6', // blue
  politics:       '#f59e0b', // amber
  science:        '#10b981', // emerald
  business:       '#8b5cf6', // violet
  entertainment:  '#ec4899', // pink
  sports:         '#f97316', // orange
  health:         '#14b8a6', // teal
  education:      '#06b6d4', // cyan
  weather:        '#0ea5e9', // sky
};
function categoryDotColor(category) {
  if (!category) return '#cbd5e1'; // slate-300 for empty
  return CATEGORY_DOT[String(category).toLowerCase()] || '#94a3b8';
}

// Column geometry — kept identical between header and rows so they line up.
// Story gets the most space; reporter sits AFTER submitted/category so the
// title is the first thing the eye lands on.
const GRID_COLS =
  'minmax(0,3fr) 100px 130px minmax(0,1.4fr) 130px 32px';

export default function ReviewQueueTable({
  stories,
  loading,
  density = 'comfortable',
  focusedIndex = -1,
  onRowFocus,
}) {
  const navigate = useNavigate();
  const { t } = useI18n();
  const rowHeight = DENSITIES[density].rowHeight;

  if (loading && stories.length === 0) {
    return (
      <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
        {t('common.loading') || 'Loading…'}
      </div>
    );
  }

  if (!loading && stories.length === 0) {
    return (
      <div className="flex h-40 flex-col items-center justify-center gap-1 text-sm text-muted-foreground">
        <span className="text-base font-medium text-foreground">{t('dashboard.noReports')}</span>
        <span className="text-xs">{t('dashboard.noReportsHint') || 'New submissions will appear here.'}</span>
      </div>
    );
  }

  return (
    <div role="grid" className="divide-y divide-border/80">
      {/* Sticky header */}
      <div
        className="sticky top-0 z-10 grid items-center gap-4 bg-background/95 px-4 text-[11px] font-medium uppercase tracking-wider text-muted-foreground backdrop-blur"
        style={{ gridTemplateColumns: GRID_COLS, height: 36 }}
      >
        <div>{t('table.storyTitle')}</div>
        <div>{t('table.submissionTime')}</div>
        <div>{t('table.category')}</div>
        <div>{t('table.reporterSubject')}</div>
        <div>{t('table.status')}</div>
        <div />
      </div>

      {stories.map((story, idx) => {
        const isFocused = idx === focusedIndex;
        return (
          <RowHoverPeek key={story.id} story={story}>
            <div
              role="row"
              data-row-id={story.id}
              className={cn(
                'group grid cursor-pointer items-center gap-4 px-4 transition-colors',
                'hover:bg-accent/40',
                isFocused && 'bg-primary/[0.04] shadow-[inset_2px_0_0_0_var(--primary)]',
              )}
              style={{ gridTemplateColumns: GRID_COLS, height: rowHeight }}
              onClick={() => navigate(`/review/${story.id}`)}
            >
              {/* Story title — gets the most horizontal space */}
              <div className="min-w-0">
                <div className="truncate text-[13.5px] font-medium text-foreground">
                  {story.headline || t('table.untitled') || 'Untitled'}
                </div>
                {story.display_id && (
                  <div className="text-[11px] font-medium text-blue-600">{story.display_id}</div>
                )}
              </div>

              {/* Submitted time */}
              <div className="text-xs tabular-nums text-muted-foreground">
                {formatDate(story.submittedAt)}
              </div>

              {/* Category — coloured dot + capitalised label */}
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span
                  className="inline-block size-1.5 shrink-0 rounded-full"
                  style={{ backgroundColor: categoryDotColor(story.category) }}
                />
                <span className="truncate capitalize">{story.category || '—'}</span>
              </div>

              {/* Reporter — pushed right of category */}
              <div className="flex min-w-0 items-center gap-2">
                <Avatar
                  initials={story.reporter?.initials}
                  color={story.reporter?.color}
                  size="sm"
                />
                <div className="min-w-0">
                  <div className="truncate text-[13px] text-foreground">
                    {story.reporter?.name || '—'}
                  </div>
                  {story.reporter?.area_name && (
                    <div className="truncate text-[11px] text-muted-foreground">
                      {story.reporter.area_name}
                    </div>
                  )}
                </div>
              </div>

              {/* Status pill — read-only on the queue table.
                  Clicking through to the review page is the only path for
                  changing status; inline edit on a long table makes
                  accidental approvals/rejections too easy. */}
              <div>
                <InlineStatusPill status={story.status} disabled />
              </div>

              {/* Action chevron */}
              <div className="text-muted-foreground/60 transition-colors group-hover:text-primary">
                <ChevronRight size={16} />
              </div>
            </div>
          </RowHoverPeek>
        );
      })}
    </div>
  );
}
