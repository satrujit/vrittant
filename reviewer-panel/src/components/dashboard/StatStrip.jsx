import { useI18n } from '../../i18n';
import { cn } from '@/lib/utils';

export default function StatStrip({ pending, reviewedToday, totalPublished, loading }) {
  const { t } = useI18n();

  const items = [
    { label: t('dashboard.pendingReview'),  value: pending,         accent: true  },
    { label: t('dashboard.reviewedToday'),  value: reviewedToday,   accent: false },
    { label: t('dashboard.totalPublished'), value: totalPublished,  accent: false },
  ];

  return (
    <div className="flex items-baseline gap-x-6 text-[13px] text-muted-foreground">
      {items.map((item, i) => (
        <div key={item.label} className="flex items-baseline gap-1.5">
          <span
            className={cn(
              'font-semibold tabular-nums text-foreground',
              item.accent && 'text-primary',
              loading && 'opacity-50',
            )}
          >
            {loading ? '—' : (item.value ?? 0).toLocaleString()}
          </span>
          <span>{item.label}</span>
          {i < items.length - 1 && <span className="ml-3 text-muted-foreground/40">·</span>}
        </div>
      ))}
    </div>
  );
}
