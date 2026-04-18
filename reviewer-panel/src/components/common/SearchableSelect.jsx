import { useMemo, useState } from 'react';
import { ChevronDown, Search, Check } from 'lucide-react';
import { useI18n } from '../../i18n';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';
import { cn } from '@/lib/utils';

/**
 * SearchableSelect — compact, scrollable, searchable dropdown.
 *
 * Single source of truth for filter dropdowns where the option list might
 * be long (reporters, locations, categories). Modeled after
 * ReassignPopover so behavior is consistent across the app.
 *
 * Props:
 *   options:   [{ value, label }]
 *   value:     current selected value (string)
 *   onChange:  (newValue) => void
 *   placeholder: trigger label when no value selected
 *   allLabel:  label for the "clear / all" option (omits filter)
 *   searchable: show the search input (default true; auto-hidden if ≤6 options)
 *   triggerClassName / contentClassName: pass-through styling
 */
export default function SearchableSelect({
  options,
  value,
  onChange,
  placeholder,
  allLabel,
  searchable = true,
  triggerClassName,
  contentClassName,
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');

  const showSearch = searchable && options.length > 6;

  const filtered = useMemo(() => {
    if (!query.trim()) return options;
    const q = query.trim().toLowerCase();
    return options.filter((o) =>
      String(o.label || '').toLowerCase().includes(q)
    );
  }, [options, query]);

  const selectedLabel = useMemo(() => {
    if (!value) return allLabel || placeholder;
    const match = options.find((o) => String(o.value) === String(value));
    return match ? match.label : placeholder;
  }, [value, options, placeholder, allLabel]);

  const pick = (newValue) => {
    setOpen(false);
    setQuery('');
    onChange(newValue);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={cn(
            'flex h-8 items-center justify-between gap-2 rounded-md border border-input bg-card px-2.5 text-xs font-medium text-foreground shadow-xs transition-colors hover:bg-accent/40 focus:outline-none focus:ring-1 focus:ring-ring',
            triggerClassName
          )}
        >
          <span className={cn('truncate', !value && 'text-muted-foreground font-normal')}>
            {selectedLabel}
          </span>
          <ChevronDown size={12} className="shrink-0 text-muted-foreground" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className={cn('w-56 p-0', contentClassName)}
      >
        {showSearch && (
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
                placeholder={t('common.search')}
                autoFocus
                className="w-full rounded border border-border bg-background py-1 pl-7 pr-2 text-xs focus:outline-none focus:ring-1 focus:ring-primary/40"
              />
            </div>
          </div>
        )}
        <div className="flex max-h-56 flex-col overflow-y-auto p-1">
          {allLabel && (
            <button
              type="button"
              onClick={() => pick('')}
              className={cn(
                'flex items-center justify-between rounded px-2 py-1.5 text-left text-xs transition-colors hover:bg-accent',
                !value && 'bg-accent/60 font-medium'
              )}
            >
              <span>{allLabel}</span>
              {!value && <Check size={12} className="text-primary" />}
            </button>
          )}
          {filtered.length === 0 ? (
            <div className="px-2 py-3 text-center text-xs text-muted-foreground">—</div>
          ) : (
            filtered.map((o) => {
              const isCurrent = String(o.value) === String(value);
              return (
                <button
                  key={o.value}
                  type="button"
                  onClick={() => pick(o.value)}
                  className={cn(
                    'flex items-center justify-between rounded px-2 py-1.5 text-left text-xs transition-colors hover:bg-accent',
                    isCurrent && 'bg-accent/60 font-medium'
                  )}
                >
                  <span className="truncate">{o.label}</span>
                  {isCurrent && <Check size={12} className="shrink-0 text-primary" />}
                </button>
              );
            })
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
