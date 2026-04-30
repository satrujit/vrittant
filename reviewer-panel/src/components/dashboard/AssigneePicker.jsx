import { useMemo, useState } from 'react';
import { Check, UserPlus } from 'lucide-react';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';
import { Avatar } from '../common';
import { getAvatarColor, getInitialsFromName } from '../../services/api';
import { cn } from '@/lib/utils';
import { useI18n } from '../../i18n';

/**
 * AssigneePicker — small avatar+name pill that opens a popover listing
 * eligible reviewers. Used in the dashboard queue so an org admin can
 * reassign a story without opening the review page.
 *
 * Props:
 *   currentId       — current assigned_to user id (null when unassigned)
 *   currentName     — current assignee_name (for the pill label)
 *   reviewers       — array of { id, name } eligible to be assigned
 *   onChange(id)    — fire-and-forget; parent does optimistic update + API call
 *   disabled        — render the pill non-interactive (e.g. while saving)
 */
export default function AssigneePicker({
  currentId, currentName,
  reviewers = [],
  onChange,
  disabled = false,
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState('');

  const filteredReviewers = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return reviewers;
    return reviewers.filter((r) => (r.name || '').toLowerCase().includes(q));
  }, [reviewers, filter]);

  const select = (next) => {
    setOpen(false);
    setFilter('');
    if (next !== currentId) onChange?.(next);
  };

  const initials = currentName ? getInitialsFromName(currentName) : null;
  const color = currentName ? getAvatarColor(currentName) : null;

  return (
    <Popover open={open} onOpenChange={(v) => { setOpen(v); if (!v) setFilter(''); }}>
      <PopoverTrigger asChild>
        <button
          type="button"
          disabled={disabled}
          onClick={(e) => e.stopPropagation()}
          aria-label={`${t('dashboard.assignedTo') || 'Assigned to'}: ${currentName || t('dashboard.unassigned') || 'Unassigned'}`}
          className={cn(
            'flex max-w-full min-w-0 items-center gap-1.5 rounded-md px-1.5 py-1 text-left transition-colors',
            'hover:bg-accent',
            disabled && 'cursor-default opacity-60',
          )}
        >
          {currentName ? (
            <>
              <Avatar initials={initials} color={color} size="xs" />
              <span className="truncate text-[12px] text-foreground">{currentName}</span>
            </>
          ) : (
            <>
              <span className="flex size-[18px] shrink-0 items-center justify-center rounded-full border border-dashed border-muted-foreground/40 text-muted-foreground/60">
                <UserPlus size={11} />
              </span>
              <span className="truncate text-[12px] italic text-muted-foreground">
                {t('dashboard.unassigned') || 'Unassigned'}
              </span>
            </>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="end"
        className="w-60 p-0"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-border p-2">
          <input
            autoFocus
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Search reviewers…"
            className="h-7 w-full rounded-md border border-border/60 bg-background px-2 text-xs outline-none focus:border-ring"
          />
        </div>
        <div className="max-h-64 overflow-y-auto p-1">
          {/* Allow clearing the assignee */}
          <button
            type="button"
            onClick={() => select(null)}
            className={cn(
              'flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-xs transition-colors hover:bg-accent',
              !currentId && 'bg-accent/60',
            )}
          >
            <span className="italic text-muted-foreground">
              {t('dashboard.unassigned') || 'Unassigned'}
            </span>
            {!currentId && <Check size={12} className="text-primary" />}
          </button>
          {filteredReviewers.length === 0 && (
            <div className="px-2 py-2 text-center text-[11px] text-muted-foreground">
              No reviewers match
            </div>
          )}
          {filteredReviewers.map((r) => (
            <button
              key={r.id}
              type="button"
              onClick={() => select(r.id)}
              className={cn(
                'flex w-full items-center justify-between gap-2 rounded-md px-2 py-1.5 text-left text-xs transition-colors hover:bg-accent',
                r.id === currentId && 'bg-accent/60',
              )}
            >
              <span className="flex min-w-0 items-center gap-2">
                <Avatar
                  initials={getInitialsFromName(r.name)}
                  color={getAvatarColor(r.name)}
                  size="xs"
                />
                <span className="truncate">{r.name}</span>
              </span>
              {r.id === currentId && <Check size={12} className="shrink-0 text-primary" />}
            </button>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}
