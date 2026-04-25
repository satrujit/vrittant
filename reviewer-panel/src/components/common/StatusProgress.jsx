import StatusBadge from './StatusBadge';
import { cn } from '@/lib/utils';

/**
 * StatusProgress — replaces the four-circle stepper with a single status pill
 * on top and a thin progress bar underneath. Same information (where the
 * story is in the pipeline) but reads in one glance instead of forcing the
 * eye to parse four truncated labels.
 *
 * Pipeline: reported → approved → layout_completed → published.
 * Off-path statuses (rejected/flagged) render the pill but leave the bar at
 * 0% in destructive colour so it doesn't look like in-progress.
 */
const STATUS_TO_STEP = {
  reported: 0,
  submitted: 0,
  approved: 1,
  layout_completed: 2,
  published: 3,
};

const TOTAL_STEPS = 4;

export default function StatusProgress({ status, className }) {
  const offPath = status === 'rejected' || status === 'flagged';
  const currentStep = STATUS_TO_STEP[status] ?? -1;
  // Status of "approved" means the Approved step is complete → 2/4 done.
  const pct = offPath ? 100 : Math.max(0, ((currentStep + 1) / TOTAL_STEPS) * 100);

  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      <StatusBadge status={status} size="sm" />
      <div
        className="h-1 w-full overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className={cn(
            'h-full transition-[width] duration-300',
            offPath ? 'bg-destructive/60' : 'bg-primary',
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
