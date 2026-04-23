import { useI18n } from '../../i18n';
import { cn } from '@/lib/utils';

// All status colour rules live in src/styles/redesign.css under
// the `.vr-pill--*` classes. This component picks the right modifier
// for the status string and renders a calm dot+text pill — no
// background fill, no inline styles.

const STATUS_I18N_MAP = {
  submitted: 'status.submitted',
  pending: 'status.pendingReview',
  pending_review: 'status.pendingReview',
  approved: 'status.approved',
  rejected: 'status.rejected',
  flagged: 'status.flagged',
  layout_completed: 'status.layoutCompleted',
  published: 'status.published',
  draft: 'status.draft',
};

const VARIANT_MAP = {
  submitted: 'submitted',
  pending: 'pending',
  pending_review: 'pending',
  approved: 'approved',
  rejected: 'rejected',
  flagged: 'flagged',
  layout_completed: 'layout-completed',
  published: 'published',
  draft: 'draft',
};

function StatusBadge({ status, size = 'md', minimal = false, className }) {
  const { t } = useI18n();
  const key = (status || 'draft').toString();
  const variant = VARIANT_MAP[key] || 'draft';
  const i18nKey = STATUS_I18N_MAP[key] || 'status.draft';

  // `minimal` is retained for API compatibility — the new pill is
  // already minimal (no fill), so both modes render the same.
  void minimal;

  return (
    <span className={cn('vr-pill', `vr-pill--${variant}`, className)} data-size={size}>
      <span className="vr-pill__dot" />
      {t(i18nKey)}
    </span>
  );
}

export default StatusBadge;
