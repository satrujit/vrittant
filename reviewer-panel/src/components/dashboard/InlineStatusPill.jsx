import { useState, useCallback } from 'react';
import { ChevronDown } from 'lucide-react';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';
import { cn } from '@/lib/utils';
import { STATUS_ORDER, statusToken } from './inlineStatus';
import { useI18n } from '../../i18n';

const PILL_CLASSES = {
  indigo:  'bg-indigo-50 text-indigo-700 ring-indigo-200/60 hover:bg-indigo-100',
  sky:     'bg-sky-50 text-sky-700 ring-sky-200/60 hover:bg-sky-100',
  emerald: 'bg-emerald-50 text-emerald-700 ring-emerald-200/60 hover:bg-emerald-100',
  rose:    'bg-rose-50 text-rose-700 ring-rose-200/60 hover:bg-rose-100',
  amber:   'bg-amber-50 text-amber-700 ring-amber-200/60 hover:bg-amber-100',
  violet:  'bg-violet-50 text-violet-700 ring-violet-200/60 hover:bg-violet-100',
  slate:   'bg-slate-100 text-slate-700 ring-slate-200/60 hover:bg-slate-200',
};

export default function InlineStatusPill({ status, onChange, disabled = false }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const accent = statusToken(status).accent;

  const select = useCallback((next) => {
    if (next !== status) onChange?.(next);
    setOpen(false);
  }, [status, onChange]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          disabled={disabled}
          aria-haspopup="listbox"
          aria-label={`Status: ${t(`status.${status}`) || status.replace('_', ' ')}, click to change`}
          aria-expanded={open}
          className={cn(
            'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11.5px] font-medium ring-1 transition-all',
            PILL_CLASSES[accent],
            disabled && 'cursor-default opacity-60',
          )}
          onClick={(e) => e.stopPropagation()}
        >
          <span>{t(`status.${status}`) || status.replace('_', ' ')}</span>
          {!disabled && <ChevronDown size={11} className="opacity-60" />}
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" role="listbox" className="w-44 p-1" onClick={(e) => e.stopPropagation()}>
        {STATUS_ORDER.map((s) => (
          <button
            key={s}
            type="button"
            role="option"
            aria-selected={s === status}
            onClick={() => select(s)}
            className={cn(
              'flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-xs transition-colors hover:bg-accent',
              s === status && 'bg-accent/60',
            )}
          >
            <span className="capitalize">{t(`status.${s}`) || s.replace('_', ' ')}</span>
            <span
              className={cn(
                'inline-block size-1.5 rounded-full',
                {
                  indigo: 'bg-indigo-500', sky: 'bg-sky-500', emerald: 'bg-emerald-500',
                  rose: 'bg-rose-500', amber: 'bg-amber-500', violet: 'bg-violet-500',
                  slate: 'bg-slate-400',
                }[statusToken(s).accent]
              )}
            />
          </button>
        ))}
      </PopoverContent>
    </Popover>
  );
}
