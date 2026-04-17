import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

/**
 * Popover for naming and creating a new page in the current edition.
 * Shown anchored to the "New page" button by the parent.
 */
export default function AddPagePopover({
  pageSuggestions,
  newPageName,
  setNewPageName,
  onSubmit,
  onCancel,
  inputRef,
  t,
}) {
  return (
    <div className={cn(
      'absolute top-[calc(100%+8px)] right-0 w-[320px]',
      'bg-card border border-border rounded-xl',
      'shadow-lg z-50 p-5',
      'flex flex-col gap-3'
    )}>
      <div className="text-sm font-semibold text-foreground">{t('buckets.addPageTitle')}</div>

      <div className="text-xs text-muted-foreground font-medium">{t('buckets.pageSuggestions')}</div>
      <div className="flex flex-wrap gap-1">
        {pageSuggestions.map((ps) => {
          const key = ps.key;
          const label = t(`buckets.pageSuggestionNames.${key}`) !== `buckets.pageSuggestionNames.${key}`
            ? t(`buckets.pageSuggestionNames.${key}`)
            : ps.label;
          return (
            <Button
              key={key}
              variant="outline"
              size="xs"
              className={cn(
                'px-2 py-[3px] h-auto',
                'font-sans text-xs text-muted-foreground',
                'bg-background border border-border rounded-full',
                'cursor-pointer transition-all duration-150',
                'shadow-none',
                'hover:text-primary hover:border-primary/40 hover:bg-primary/10'
              )}
              onClick={() => setNewPageName(label)}
            >
              {label}
            </Button>
          );
        })}
      </div>

      <Input
        ref={inputRef}
        type="text"
        className={cn(
          'w-full py-2 px-4 h-auto font-sans text-sm text-foreground',
          'bg-card border border-border rounded-lg outline-none',
          'transition-[border-color,box-shadow] duration-150',
          'shadow-none focus-visible:ring-0',
          'focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/20'
        )}
        placeholder={t('buckets.pageNamePlaceholder')}
        value={newPageName}
        onChange={(e) => setNewPageName(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') onSubmit();
          if (e.key === 'Escape') onCancel();
        }}
      />

      <div className="flex items-center justify-end gap-2">
        <Button
          variant="outline"
          size="sm"
          className={cn(
            'px-5',
            'font-sans text-sm font-medium',
            'text-muted-foreground bg-transparent border border-border rounded-lg',
            'cursor-pointer transition-all duration-150',
            'shadow-none',
            'hover:bg-accent hover:text-foreground'
          )}
          onClick={onCancel}
        >
          {t('buckets.cancel')}
        </Button>
        <Button
          size="sm"
          className={cn(
            'px-5',
            'font-sans text-sm font-semibold',
            'text-primary-foreground bg-primary border-none rounded-lg',
            'cursor-pointer transition-[background] duration-150',
            'hover:not-disabled:bg-primary/80'
          )}
          onClick={onSubmit}
          disabled={!newPageName.trim()}
        >
          {t('buckets.create')}
        </Button>
      </div>
    </div>
  );
}
