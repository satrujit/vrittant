import { Draggable } from '@hello-pangea/dnd';
import { GripVertical, CheckCircle2, ImageIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatTimeAgo, truncateText, getCategoryColor } from '../../utils/helpers';

/**
 * Draggable story card used inside bucket columns (and the unassigned panel).
 *
 * Two glanceable status pips (#47, #48) sit next to the category badge so a
 * layout team can scan a column without opening anything:
 *  - green check  → story is layout_completed
 *  - photo icon   → story has at least one image attached
 */
export default function StoryCard({ story, index, onClick, t }) {
  const catColor = getCategoryColor(story.category);
  // #47 — layout completion is a story-status, not a separate flag
  const isLayoutDone = story.status === 'layout_completed';
  // #48 — story has a photo if any media attachment is image-typed. Mobile
  // emits both `media_type: 'photo'` and (older) untagged photo paths, both
  // of which transformStory normalises to type='photo'.
  const hasPhoto = (story.mediaFiles || []).some((m) => !m?.type || m.type === 'photo' || m.type === 'image');

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
            dragSnapshot.isDragging && 'shadow-lg border-primary rotate-2',
            // Subtle visual cue that a card is "done" — softer ring, not a
            // full disable, since it's still draggable / clickable.
            isLayoutDone && 'border-emerald-300 bg-emerald-50/40'
          )}
          onClick={() => onClick(story.id)}
        >
          <div className="flex items-center gap-1.5 mb-1">
            <span
              className="inline-flex items-center px-2 py-px text-[10px] font-semibold rounded-md"
              style={{ color: catColor.color, background: catColor.bg }}
            >
              {t(`categories.${story.category}`) !== `categories.${story.category}`
                ? t(`categories.${story.category}`)
                : story.category}
            </span>
            {hasPhoto && (
              <span
                className="inline-flex items-center justify-center w-4 h-4 rounded text-muted-foreground"
                title={t('buckets.hasPhoto') || 'Has photo'}
                aria-label={t('buckets.hasPhoto') || 'Has photo'}
              >
                <ImageIcon size={12} />
              </span>
            )}
            {isLayoutDone && (
              <span
                className="inline-flex items-center justify-center w-4 h-4 rounded text-emerald-600"
                title={t('buckets.layoutCompleted') || 'Layout completed'}
                aria-label={t('buckets.layoutCompleted') || 'Layout completed'}
              >
                <CheckCircle2 size={14} />
              </span>
            )}
          </div>
          <div className="text-[13px] font-semibold text-foreground leading-tight mb-0.5 line-clamp-2">
            {story.displayId && (
              <span className="mr-1 inline-block rounded bg-muted px-1 py-px text-[9px] font-mono font-medium text-muted-foreground align-middle">
                {story.displayId}
              </span>
            )}
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
