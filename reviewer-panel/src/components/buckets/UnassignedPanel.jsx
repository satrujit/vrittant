import { Droppable } from '@hello-pangea/dnd';
import { SlidersHorizontal } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import StoryCard from './StoryCard';

/**
 * Fixed-left panel listing unassigned stories with category/location filters.
 */
export default function UnassignedPanel({
  droppableId,
  cards,
  showFilters,
  setShowFilters,
  uniqueCategories,
  uniqueLocations,
  categoryFilter,
  setCategoryFilter,
  locationFilter,
  setLocationFilter,
  hasActiveFilters,
  clearAllFilters,
  onCardClick,
  t,
}) {
  return (
    <div className="flex-none w-[300px] min-w-[300px] flex flex-col bg-accent border-r border-border overflow-visible min-h-0">
      <div className="flex items-center gap-1 py-2 pl-4 pr-2 border-b border-border shrink-0">
        <div className="w-1 h-[22px] rounded-full shrink-0 bg-muted-foreground" />
        <span className="text-sm font-semibold text-foreground flex-1 whitespace-nowrap overflow-hidden text-ellipsis">
          {t('buckets.unassigned')}
        </span>
        <span className="inline-flex items-center justify-center min-w-[22px] h-5 px-1 text-[11px] font-semibold text-muted-foreground bg-muted rounded-full shrink-0">
          {cards.length}
        </span>

        <div className="relative">
          <Button
            variant="ghost"
            size="icon-xs"
            className={cn(
              'w-[26px] h-[26px]',
              'bg-transparent border border-border rounded-md',
              'text-muted-foreground cursor-pointer shrink-0 relative',
              'transition-[background,color,border-color] duration-150',
              'hover:bg-accent hover:text-primary hover:border-primary/40',
              hasActiveFilters && 'text-primary border-primary bg-primary/10'
            )}
            onClick={() => setShowFilters(!showFilters)}
            aria-label={t('buckets.filterTitle')}
            title={t('buckets.filterTitle')}
          >
            <SlidersHorizontal size={14} />
          </Button>

          {showFilters && (
            <div className={cn(
              'absolute top-[calc(100%+8px)] right-0 w-[260px] max-h-[360px]',
              'overflow-y-auto bg-card border border-border rounded-xl',
              'shadow-lg z-50 p-3',
              'flex flex-col gap-3'
            )}>
              <div className="text-sm font-semibold text-foreground">{t('buckets.filterTitle')}</div>

              {uniqueCategories.length > 0 && (
                <div className="flex flex-col gap-1">
                  <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                    {t('buckets.filterByCategory')}
                  </Label>
                  <Select
                    value={categoryFilter || '__all__'}
                    onValueChange={(val) => setCategoryFilter(val === '__all__' ? '' : val)}
                  >
                    <SelectTrigger
                      size="sm"
                      className={cn(
                        'w-full',
                        'font-sans text-sm text-foreground',
                        'bg-card border border-border rounded-lg',
                        'cursor-pointer shadow-none',
                        'transition-[border-color,box-shadow] duration-150',
                        'focus:border-ring focus:ring-2 focus:ring-ring/20'
                      )}
                    >
                      <SelectValue placeholder={t('buckets.allCategories')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__all__">{t('buckets.allCategories')}</SelectItem>
                      {uniqueCategories.map((cat) => (
                        <SelectItem key={cat} value={cat}>
                          {t(`categories.${cat}`) !== `categories.${cat}`
                            ? t(`categories.${cat}`)
                            : cat}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {uniqueLocations.length > 0 && (
                <div className="flex flex-col gap-1">
                  <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                    {t('buckets.filterByLocation')}
                  </Label>
                  <Select
                    value={locationFilter || '__all__'}
                    onValueChange={(val) => setLocationFilter(val === '__all__' ? '' : val)}
                  >
                    <SelectTrigger
                      size="sm"
                      className={cn(
                        'w-full',
                        'font-sans text-sm text-foreground',
                        'bg-card border border-border rounded-lg',
                        'cursor-pointer shadow-none',
                        'transition-[border-color,box-shadow] duration-150',
                        'focus:border-ring focus:ring-2 focus:ring-ring/20'
                      )}
                    >
                      <SelectValue placeholder={t('buckets.allLocations')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__all__">{t('buckets.allLocations')}</SelectItem>
                      {uniqueLocations.map((loc) => (
                        <SelectItem key={loc} value={loc}>{loc}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              <div className="flex items-center justify-between pt-1 border-t border-border">
                <Button
                  variant="ghost"
                  size="xs"
                  className={cn(
                    'font-sans text-xs text-muted-foreground',
                    'cursor-pointer px-1',
                    'transition-colors duration-150',
                    'hover:text-primary hover:bg-transparent'
                  )}
                  onClick={clearAllFilters}
                >
                  {t('buckets.clearFilters')}
                </Button>
                <Button
                  size="xs"
                  className={cn(
                    'font-sans text-xs font-semibold',
                    'text-primary-foreground bg-primary border-none rounded-md',
                    'px-3 cursor-pointer',
                    'transition-[background] duration-150',
                    'hover:bg-primary/80'
                  )}
                  onClick={() => setShowFilters(false)}
                >
                  {t('buckets.applyFilters')}
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="text-[11px] text-muted-foreground px-4 py-1 border-b border-border shrink-0">
        {t('buckets.unassignedDesc')}
      </div>

      <Droppable droppableId={droppableId}>
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
