import { getCategoryColor } from '../../utils/helpers';
import { useI18n } from '../../i18n';
import { Badge } from '@/components/ui/badge';

function CategoryChip({ category }) {
  const { t } = useI18n();
  const { color, bg } = getCategoryColor(category);

  // Use localized category name, fallback to formatted English
  const key = (category || '').toLowerCase().replace(/[\s]+/g, '_');
  const localized = t(`categories.${key}`);
  const displayName = localized !== `categories.${key}` ? localized : (category || '').replace(/_/g, ' ');

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
