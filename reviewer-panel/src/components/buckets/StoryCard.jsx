import { Draggable } from '@hello-pangea/dnd';
import { GripVertical } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatTimeAgo, truncateText, getCategoryColor } from '../../utils/helpers';

/**
 * Draggable story card used inside bucket columns (and the unassigned panel).
 */
export default function StoryCard({ story, index, onClick, t }) {
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
