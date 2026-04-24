import { Plus, ArrowLeft, Pencil, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { SearchBar } from '../common';
import AddPagePopover from './AddPagePopover';

/**
 * Header bar for the bucket-detail page: back-button, edition title (with inline edit),
 * search, and the new-page popover trigger.
 */
export default function BucketDetailHeader({
  // edition title
  editionDisplayTitle,
  editingEditionTitle,
  editionTitleDraft,
  setEditionTitleDraft,
  editionTitleInputRef,
  onStartEditEditionTitle,
  onSaveEditionTitle,
  onCancelEditEditionTitle,
  // navigation
  onBack,
  // search
  search,
  setSearch,
  // add-page popover
  showAddPage,
  setShowAddPage,
  pageSuggestions,
  newPageName,
  setNewPageName,
  addPageInputRef,
  onAddPage,
  onCancelAddPage,
  // i18n
  t,
}) {
  return (
    <div className="flex items-center justify-between gap-5 px-6 pt-5 pb-3 border-b border-border shrink-0">
      <div className="flex items-center gap-3 min-w-0">
        <Button
          variant="ghost"
          size="icon"
          className={cn(
            'w-[34px] h-[34px]',
            'bg-accent border border-border rounded-lg',
            'text-muted-foreground cursor-pointer shrink-0',
            'transition-[background,color,border-color] duration-150',
            'hover:bg-primary/10 hover:text-primary hover:border-primary/40'
          )}
          onClick={onBack}
          aria-label={t('buckets.backToEditions')}
          title={t('buckets.backToEditions')}
        >
          <ArrowLeft size={18} />
        </Button>

        {editingEditionTitle ? (
          <div className="flex items-center gap-1 min-w-0">
            <Input
              ref={editionTitleInputRef}
              className={cn(
                'min-w-[200px] px-2 py-1 h-auto',
                'text-xl font-bold text-foreground',
                'bg-card border border-primary rounded-md outline-none',
                'shadow-none focus-visible:ring-0 focus-visible:border-primary'
              )}
              value={editionTitleDraft}
              onChange={(e) => setEditionTitleDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') onSaveEditionTitle();
                if (e.key === 'Escape') onCancelEditEditionTitle();
              }}
              onBlur={onSaveEditionTitle}
            />
            <Button
              variant="ghost"
              size="icon-xs"
              className={cn(
                'w-7 h-7',
                'bg-primary border-none rounded-md',
                'text-primary-foreground cursor-pointer shrink-0',
                'hover:bg-primary/80 hover:text-primary-foreground'
              )}
              onMouseDown={(e) => e.preventDefault()}
              onClick={onSaveEditionTitle}
            >
              <Check size={14} />
            </Button>
          </div>
        ) : (
          <div className="group/title flex items-center gap-1 min-w-0">
            <h1 className={cn(
              'text-xl font-bold',
              'text-foreground leading-tight',
              'whitespace-nowrap overflow-hidden text-ellipsis'
            )}>
              {editionDisplayTitle}
            </h1>
            <Button
              variant="ghost"
              size="icon-xs"
              className={cn(
                'text-muted-foreground cursor-pointer shrink-0',
                'opacity-0 transition-[opacity,background,color] duration-150',
                'group-hover/title:opacity-100',
                'hover:bg-accent hover:text-primary'
              )}
              onClick={onStartEditEditionTitle}
              aria-label="Edit edition title"
            >
              <Pencil size={14} />
            </Button>
          </div>
        )}
      </div>

      <div className="flex items-center gap-3 shrink-0">
        {/* Canonical SearchBar (h-8, 14px icon, text-[13px]) — same shape
            as Dashboard / AllStories / Reporters / NewsFeed. */}
        <SearchBar
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t('buckets.searchPlaceholder')}
          className="w-[220px]"
        />

        <div className="relative">
          <Button
            className="px-5 font-semibold rounded-lg hover:-translate-y-px active:translate-y-0"
            onClick={() => setShowAddPage(!showAddPage)}
          >
            <Plus size={16} />
            {t('buckets.newPage')}
          </Button>

          {showAddPage && (
            <AddPagePopover
              pageSuggestions={pageSuggestions}
              newPageName={newPageName}
              setNewPageName={setNewPageName}
              onSubmit={onAddPage}
              onCancel={onCancelAddPage}
              inputRef={addPageInputRef}
              t={t}
            />
          )}
        </div>
      </div>
    </div>
  );
}
