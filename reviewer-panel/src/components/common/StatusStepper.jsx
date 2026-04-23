import { Check } from 'lucide-react';
import { useI18n } from '../../i18n';
import { cn } from '@/lib/utils';

/**
 * StatusStepper — horizontal progress strip showing where a story sits in
 * the editorial pipeline.
 *
 * Stops: Reported → Approved → Layout Placed → Published.
 *
 * `rejected` and `flagged` are off-path terminal states. We render the
 * stepper greyed out and surface the actual status separately (the side
 * panel still shows a StatusBadge underneath).
 *
 * Step matching:
 *   reported            → 0
 *   approved            → 1
 *   layout_completed    → 2
 *   published           → 3
 *   rejected | flagged  → -1  (off-path, no step lit)
 */
const STATUS_TO_STEP = {
  reported: 0,
  approved: 1,
  layout_completed: 2,
  published: 3,
};

export default function StatusStepper({ status, className }) {
  const { t } = useI18n();
  const currentStep = STATUS_TO_STEP[status] ?? -1;
  const offPath = status === 'rejected' || status === 'flagged';

  const steps = [
    { key: 'reported', label: t('status.submitted', 'Reported') },
    { key: 'approved', label: t('status.approved', 'Approved') },
    { key: 'layout_completed', label: t('status.layoutPlaced', 'Layout Placed') },
    { key: 'published', label: t('status.published', 'Published') },
  ];

  return (
    <div className={cn('flex w-full items-start gap-0.5', className)}>
      {steps.map((step, i) => {
        // A status of "approved" means the Approved step is *complete*, not
        // in-progress — so steps up to and including currentStep are done,
        // and the next step (currentStep + 1) is what's currently pending.
        const isDone = !offPath && i <= currentStep;
        const isCurrent = !offPath && i === currentStep + 1;
        const isLast = i === steps.length - 1;

        return (
          <div key={step.key} className="flex min-w-0 flex-1 items-start">
            <div className="flex min-w-0 flex-1 flex-col items-center gap-1">
              <div
                className={cn(
                  'flex size-5 shrink-0 items-center justify-center rounded-full border text-[10px] font-medium transition-colors',
                  isDone && 'border-primary bg-primary text-primary-foreground',
                  isCurrent && 'border-primary bg-primary/10 text-primary',
                  !isDone && !isCurrent && 'border-border bg-muted/40 text-muted-foreground',
                )}
                aria-current={isCurrent ? 'step' : undefined}
              >
                {isDone ? <Check size={11} strokeWidth={3} /> : i + 1}
              </div>
              {/* Labels wrap onto a second line on narrow side panels rather
                  than truncating with an ellipsis — readability beats a
                  single-line strip when the panel is squeezed. */}
              <span
                className={cn(
                  'w-full break-words text-center text-[10px] leading-tight',
                  (isDone || isCurrent) ? 'text-foreground' : 'text-muted-foreground',
                )}
                title={step.label}
              >
                {step.label}
              </span>
            </div>
            {!isLast && (
              <div
                className={cn(
                  'mt-2 h-px flex-1 self-start transition-colors',
                  isDone ? 'bg-primary' : 'bg-border',
                )}
                aria-hidden="true"
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
