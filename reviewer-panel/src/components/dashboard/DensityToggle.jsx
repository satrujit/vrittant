import { LayoutList, Rows3, Square } from 'lucide-react';
import { cn } from '@/lib/utils';
import { DENSITIES } from '../../hooks/useDensityPreference';
import { useI18n } from '../../i18n';

const ICONS = {
  compact:     LayoutList,
  comfortable: Rows3,
  cozy:        Square,
};

export default function DensityToggle({ value, onChange }) {
  const { t } = useI18n();
  return (
    <div className="flex items-center gap-0.5 rounded-md border border-border/60 bg-card p-0.5">
      {Object.entries(DENSITIES).map(([key, d]) => {
        const Icon = ICONS[key];
        const active = value === key;
        return (
          <button
            key={key}
            type="button"
            onClick={() => onChange(key)}
            className={cn(
              'flex size-7 items-center justify-center rounded-[5px] transition-colors',
              active ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:bg-accent hover:text-foreground',
            )}
            title={t(`dashboard.density.${key}`) || d.label}
          >
            <Icon size={14} />
          </button>
        );
      })}
    </div>
  );
}
