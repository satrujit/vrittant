import { Droppable } from '@hello-pangea/dnd';
import { Pencil, Check, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import StoryCard from './StoryCard';

/**
 * One page column in the bucket-detail kanban board.
 * Owns its inline title-edit UI and delegates story drag/drop to <Droppable>.
 */
export default function BucketColumn({
  page,
  cards,
  isEditing,
  editTitle,
  setEditTitle,
  onStartEdit,
  onSaveTitle,
  onCancelEdit,
  onDeletePage,
  onCardClick,
  editInputRef,
  t,
}) {
  return (
    <div className="flex-none w-[280px] min-w-[280px] flex flex-col bg-background rounded-xl border border-border overflow-hidden">
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
                if (e.key === 'Enter') onSaveTitle();
                if (e.key === 'Escape') onCancelEdit();
              }}
              onBlur={onSaveTitle}
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
              onClick={onSaveTitle}
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
              onClick={() => onStartEdit(page.id, page.page_name || '')}
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
          onClick={() => onDeletePage(page.id)}
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
                onClick={onCardClick}
                t={t}
              />
            ))}
            {provided.placeholder}
          </div>
        )}
      </Droppable>
    </div>
  );
}
