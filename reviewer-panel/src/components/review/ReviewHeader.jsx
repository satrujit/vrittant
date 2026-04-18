import { ArrowLeft, Check, Loader2, Save } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useI18n } from '../../i18n';
import { Avatar } from '../common';
import { formatDate } from '../../utils/helpers';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';
import { Button } from '@/components/ui/button';

/**
 * ReviewHeader — minimalist top bar.
 *
 * Holds only the items that need to stay above the editor: a back button,
 * the reporter chip, the editable headline, and the primary action buttons
 * (Approve / Reject / Save). Everything that used to be a status pill or
 * settings popover has moved to {@link ReviewSidePanel}.
 *
 * Reviewed-by attribution still appears here as a thin sub-bar for terminal
 * statuses so it's visible without scrolling the side panel.
 *
 * State lives in useReviewState; we receive it via props.
 */
export default function ReviewHeader({
  story,
  status,
  headline,
  setHeadline,
  saving,
  approveOpen,
  setApproveOpen,
  rejectOpen,
  setRejectOpen,
  rejectReason,
  setRejectReason,
  handleApprove,
  handleReject,
  handleSaveContent,
}) {
  const { t } = useI18n();
  const navigate = useNavigate();

  return (
    <>
      {/* ── Top bar ── */}
      <div className="flex shrink-0 items-center gap-3 border-b border-border bg-card px-4 py-2">
        <Button
          variant="outline"
          size="icon"
          className="size-7 shrink-0"
          onClick={() => navigate(-1)}
        >
          <ArrowLeft size={14} />
        </Button>

        <div className="flex min-w-0 items-center gap-2">
          <Avatar
            initials={story.reporter.initials}
            color={story.reporter.color}
            size="sm"
          />
          <span className="truncate whitespace-nowrap text-xs font-medium text-foreground">
            {story.reporter.name}
          </span>
        </div>

        {/* Spacer */}
        <div className="flex-1" />

        {/* ── Right: primary actions ── */}
        <div className="flex shrink-0 items-center gap-1.5">
          <Popover open={approveOpen} onOpenChange={setApproveOpen}>
            <PopoverTrigger asChild>
              <Button
                size="sm"
                className="h-7 gap-1 bg-emerald-500 px-2.5 text-xs text-white hover:bg-emerald-600"
              >
                <Check size={14} />
                {t('actions.approve')}
              </Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-56 p-3">
              <p className="mb-2 text-xs font-medium text-foreground">
                {t('actions.approve')}?
              </p>
              <div className="flex gap-1">
                <Button
                  size="sm"
                  className="flex-1 bg-emerald-500 text-white hover:bg-emerald-600"
                  onClick={() => {
                    handleApprove();
                    setApproveOpen(false);
                  }}
                  disabled={saving}
                >
                  {saving ? '...' : t('actions.confirm')}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1"
                  onClick={() => setApproveOpen(false)}
                >
                  {t('actions.cancel')}
                </Button>
              </div>
            </PopoverContent>
          </Popover>

          <Popover open={rejectOpen} onOpenChange={setRejectOpen}>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="h-7 gap-1 border-red-200 px-2.5 text-xs text-red-500 hover:border-red-500 hover:bg-red-50"
              >
                {t('actions.reject')}
              </Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-64 p-3">
              <textarea
                className="mb-2 min-h-12 w-full rounded-md border border-border bg-card px-2 py-1.5 text-xs text-foreground outline-none focus:border-ring"
                placeholder={t('review.rejectPlaceholder')}
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                rows={2}
              />
              <div className="flex gap-1">
                <Button
                  size="sm"
                  className="flex-1 bg-red-500 text-white hover:bg-red-600"
                  onClick={() => {
                    handleReject();
                    setRejectOpen(false);
                  }}
                  disabled={saving}
                >
                  {saving ? '...' : t('actions.confirm')}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1"
                  onClick={() => setRejectOpen(false)}
                >
                  {t('actions.cancel')}
                </Button>
              </div>
            </PopoverContent>
          </Popover>

          <Button
            size="sm"
            className="h-7 gap-1 px-2.5 text-xs"
            onClick={handleSaveContent}
            disabled={saving}
          >
            {saving ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
            {t('actions.saveDraft')}
          </Button>
        </div>
      </div>

      {/* ── Reviewed-by attribution (only for terminal statuses) ── */}
      {['approved', 'rejected', 'published'].includes(status) &&
        story.reviewer_name && (
          <div className="shrink-0 border-b border-border bg-muted/30 px-6 py-1">
            <span className="text-[11px] text-muted-foreground">
              {t('stories.reviewedByOn', {
                name: story.reviewer_name,
                date: formatDate(story.reviewed_at),
              })}
            </span>
          </div>
        )}

      {/* ── Sticky headline ── */}
      <div className="shrink-0 border-b border-border bg-background px-6 py-2">
        <input
          type="text"
          className="w-full border-none bg-transparent px-0 text-xl font-bold leading-tight text-foreground outline-none placeholder:text-muted-foreground/50"
          value={headline}
          onChange={(e) => setHeadline(e.target.value)}
          placeholder={t('review.headlinePlaceholder') || 'Headline...'}
        />
      </div>
    </>
  );
}
