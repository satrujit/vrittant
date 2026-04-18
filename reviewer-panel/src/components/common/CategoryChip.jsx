import { getCategoryColor } from '../../utils/helpers';
import { useI18n } from '../../i18n';
import { Badge } from '@/components/ui/badge';

function CategoryChip({ category, minimal = false }) {
  const { t } = useI18n();
  const { color, bg } = getCategoryColor(category);

  // Use localized category name, fallback to formatted English
  const key = (category || '').toLowerCase().replace(/[\s]+/g, '_');
  const localized = t(`categories.${key}`);
  const displayName = localized !== `categories.${key}` ? localized : (category || '').replace(/_/g, ' ');

  // Minimal variant: colored dot + label, no pill background. Used in dense
  // tables to keep rows compact.
  if (minimal) {
    return (
      <span
        className="inline-flex items-center gap-1.5 text-xs font-medium whitespace-nowrap leading-none"
        style={{ color }}
      >
        <span
          className="shrink-0 rounded-full size-[6px]"
          style={{ backgroundColor: color }}
        />
        {displayName}
      </span>
    );
  }

  return (
    <Badge
      variant="ghost"
      className="rounded-full px-1.5 py-px text-[11px] font-medium whitespace-nowrap leading-[1.6]"
      style={{ color, backgroundColor: bg }}
    >
      {displayName}
    </Badge>
  );
}

export default CategoryChip;
