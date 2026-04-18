import { useMemo, useState } from 'react';
import { ChevronDown, Search } from 'lucide-react';
import { useI18n } from '../../i18n';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

/**
 * ReassignPopover — single source of truth for the inline assignee
 * picker. Compact trigger + searchable + scrollable reviewer list.
 *
 * Variants:
 *   - default ("cell"):  shows assignee_name + match-reason badge as trigger
 *   - compact ("chip"):  trigger is just "Reassign"-style — no current
 *                        assignee shown (used in dashboard pending queue
 *                        where the column isn't there)
 */
export default function ReassignPopover({
  assigneeId,
  assigneeName,
  matchReason,
  reviewers,
  onReassign,
  variant = 'cell',
  triggerClassName,
}) {
  const { t } = useI18n();
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);

  const filtered = useMemo(() => {
    if (!query.trim()) return reviewers;
    const q = query.trim().toLowerCase();
    return reviewers.filter((r) => (r.name || '').toLowerCase().includes(q));
  }, [reviewers, query]);

  const handlePick = async (userId) => {
    setOpen(false);
    setQuery('');
    await onReassign(userId);
  };

  const trigger = variant === 'chip' ? (
    <button
      type="button"
      className={cn(
        'inline-flex items-center gap-1 rounded border border-border bg-card px-2 py-1 text-xs font-medium text-foreground transition-colors hover:bg-accent',
        triggerClassName
      )}
    >
      {assigneeName || t('assignment.reassign')}
      <ChevronDown size={12} className="text-muted-foreground" />
    </button>
  ) : (
    <button
      type="button"
      className={cn(
        'flex flex-col items-start gap-0.5 text-left hover:bg-accent/40 rounded px-1.5 py-1 -mx-1.5 -my-1 transition-colors min-w-[120px]',
        triggerClassName
      )}
    >
      {assigneeName ? (
        <>
          <span className="text-xs text-foreground whitespace-nowrap">{assigneeName}</span>
          {matchReason && (
            <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4 font-normal">
              {t(`assignment.matchReason.${matchReason}`)}
            </Badge>
          )}
        </>
      ) : (
        <span className="text-xs text-muted-foreground">{t('assignment.unassigned')}</span>
      )}
    </button>
  );

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>{trigger}</PopoverTrigger>
      <PopoverContent align="start" className="w-60 p-0">
        {reviewers.length === 0 ? (
          <div className="px-3 py-3 text-xs text-muted-foreground">
            {t('assignment.noReviewersAvailable')}
          </div>
        ) : (
          <>
            <div className="border-b border-border p-2">
              <div className="relative">
                <Search
                  size={12}
                  className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground"
                />
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={t('assignment.searchReviewers')}
                  autoFocus
                  className="w-full rounded border border-border bg-background py-1 pl-7 pr-2 text-xs focus:outline-none focus:ring-1 focus:ring-primary/40"
                />
              </div>
            </div>
            <div className="px-2 pb-1 pt-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              {t('assignment.reassignTo')}
            </div>
            <div className="flex max-h-56 flex-col overflow-y-auto px-1 pb-1">
              {filtered.length === 0 ? (
                <div className="px-2 py-3 text-center text-xs text-muted-foreground">
                  {t('assignment.noMatches') || '—'}
                </div>
              ) : (
                filtered.map((r) => {
                  const isCurrent = String(r.id) === String(assigneeId);
                  return (
                    <button
                      key={r.id}
                      type="button"
                      disabled={isCurrent}
                      onClick={() => handlePick(r.id)}
                      className={cn(
                        'rounded px-2 py-1.5 text-left text-xs transition-colors hover:bg-accent',
                        isCurrent && 'cursor-default bg-accent/60 text-muted-foreground'
                      )}
                    >
                      {r.name}
                    </button>
                  );
                })
              )}
            </div>
          </>
        )}
      </PopoverContent>
    </Popover>
  );
}
