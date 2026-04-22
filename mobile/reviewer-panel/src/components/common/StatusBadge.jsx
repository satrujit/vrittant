import { useI18n } from '../../i18n';
import { getStatusColor } from '../../utils/helpers';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

const STATUS_I18N_MAP = {
  submitted: 'status.submitted',
  pending: 'status.pendingReview',
  pending_review: 'status.pendingReview',
  in_progress: 'status.inProgress',
  approved: 'status.approved',
  rejected: 'status.rejected',
  flagged: 'status.flagged',
  published: 'status.published',
  draft: 'status.draft',
};

const SIZE_CLASSES = {
  sm: 'h-[22px] px-2 py-0.5 text-xs gap-1',
  md: 'h-7 px-3 py-1 text-sm gap-1',
};

const DOT_SIZES = {
  sm: 'size-[5px]',
  md: 'size-1.5',
};

function StatusBadge({ status, size = 'md' }) {
  const { t } = useI18n();
  const { color, bg, dot } = getStatusColor(status);
  const i18nKey = STATUS_I18N_MAP[status] || 'status.draft';

  return (
    <Badge
      variant="ghost"
      className={cn(
        'rounded-full font-medium whitespace-nowrap leading-none',
        SIZE_CLASSES[size] || SIZE_CLASSES.md
      )}
      style={{ color, backgroundColor: bg }}
    >
      <span
        className={cn('shrink-0 rounded-full', DOT_SIZES[size] || DOT_SIZES.md)}
        style={{ backgroundColor: dot }}
      />
      {t(i18nKey)}
    </Badge>
  );
}

export default StatusBadge;
