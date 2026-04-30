import { useEffect, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Avatar } from '../common';
import { formatDate } from '../../utils/helpers';
import { useI18n } from '../../i18n';
import { DENSITIES } from '../../hooks/useDensityPreference';
import InlineStatusPill from './InlineStatusPill';
import RowHoverPeek from './RowHoverPeek';

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

  // Track which IDs were on the previous frame so we can highlight new arrivals.
  const prevIdsRef = useRef(new Set());
  // First render is always "all rows are new" against an empty set, which
  // would light up every row in coral on initial load and on every page
  // change. Skip the highlight until we have a real "previous frame" to
  // diff against (i.e. from the second render onward).
  const isFirstRenderRef = useRef(true);

  const arrivedIds = useMemo(() => {
    if (isFirstRenderRef.current) return new Set();
    return new Set(
      stories
        .map((s) => s.id)
        .filter((id) => !prevIdsRef.current.has(id))
    );
  }, [stories]);

  // Side-effect: update the previous-IDs ref AFTER render and flip the
  // first-render flag. Mutating during render breaks StrictMode.
  useEffect(() => {
    prevIdsRef.current = new Set(stories.map((s) => s.id));
    isFirstRenderRef.current = false;
  }, [stories]);

  // Clear the arrival class after the animation duration so re-renders
  // don't re-trigger it.
  useEffect(() => {
    const timers = [...arrivedIds].map((id) =>
      setTimeout(() => {
        const el = document.querySelector(`[data-row-id="${id}"]`);
        el?.classList.remove('vr-row-arrival');
      }, 2200)
    );
    return () => timers.forEach(clearTimeout);
  }, [arrivedIds]);

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
    <div role="grid" className="divide-y divide-border/40">
      {/* Sticky header */}
      <div
        className="sticky top-0 z-10 grid items-center gap-4 bg-background/95 px-4 text-[11px] font-medium uppercase tracking-wider text-muted-foreground backdrop-blur"
        style={{
          gridTemplateColumns: 'minmax(0,2fr) minmax(0,1.4fr) 110px 110px 130px 32px',
          height: 36,
        }}
      >
        <div>{t('table.storyTitle')}</div>
        <div>{t('table.reporterSubject')}</div>
        <div>{t('table.submissionTime')}</div>
        <div>{t('table.category')}</div>
        <div>{t('table.status')}</div>
        <div />
      </div>

      {stories.map((story, idx) => {
        const isFocused = idx === focusedIndex;
        const isArrived = arrivedIds.has(story.id);
        return (
          <RowHoverPeek key={story.id} story={story}>
            <div
              role="row"
              data-row-id={story.id}
              className={cn(
                'group grid cursor-pointer items-center gap-4 px-4 transition-colors',
                'hover:bg-accent/40',
                isFocused && 'bg-primary/[0.04] shadow-[inset_2px_0_0_0_var(--primary)]',
                isArrived && 'vr-row-arrival',
              )}
              style={{
                gridTemplateColumns: 'minmax(0,2fr) minmax(0,1.4fr) 110px 110px 130px 32px',
                height: rowHeight,
              }}
              onClick={() => navigate(`/review/${story.id}`)}
            >
              {/* Story title */}
              <div className="min-w-0">
                <div className="truncate text-[13.5px] font-medium text-foreground">
                  {story.headline || t('table.untitled') || 'Untitled'}
                </div>
                {story.display_id && (
                  <div className="text-[11px] text-primary/80">{story.display_id}</div>
                )}
              </div>

              {/* Reporter */}
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

              {/* Time */}
              <div className="text-xs tabular-nums text-muted-foreground">
                {formatDate(story.submittedAt)}
              </div>

              {/* Category — dot + label */}
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span className="inline-block size-1.5 rounded-full bg-muted-foreground/40 transition-colors group-hover:bg-primary" />
                <span className="truncate">{story.category || '—'}</span>
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
