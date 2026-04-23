import { ArrowLeft, Check, Loader2, MoreVertical, X, AlertCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useI18n } from '../../i18n';
import { formatDate } from '../../utils/helpers';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

/**
 * ReviewHeader — minimalist top bar.
 *
 * Layout: back arrow on the left; Cancel / Save / Approve cluster on the
 * right with an overflow menu (⋮) for less-frequent actions like Reject.
 * The headline lives directly in the editor body now (one fewer divider).
 *
 * Reviewed-by attribution still appears as a thin sub-bar for terminal
 * statuses so it's visible without scrolling the side panel.
 */
export default function ReviewHeader({
  story,
  status,
  headline,
  setHeadline,
  saving,
  lastSavedAt,
  saveError,
  approveOpen,
  setApproveOpen,
  rejectOpen,
  setRejectOpen,
  rejectReason,
  setRejectReason,
  handleApprove,
  handleReject,
  handleStatusChange,
  handleSaveContent,
}) {
  const { t } = useI18n();
  const navigate = useNavigate();

  return (
    <>
      {/* ── Top bar ── */}
      <div className="flex shrink-0 items-center gap-2 border-b border-border bg-card px-4 py-2">
        <Button
          variant="ghost"
          size="icon"
          className="size-8 shrink-0 text-muted-foreground"
          onClick={() => navigate(-1)}
          aria-label={t('actions.back', 'Back')}
        >
          <ArrowLeft size={16} />
        </Button>

        <div className="flex-1" />

        {/* Save status indicator */}
        {(saving || lastSavedAt || saveError) && (
          <span
            className={
              'mr-1 flex items-center gap-1 text-[11px] ' +
              (saveError
                ? 'text-destructive'
                : saving
                ? 'text-muted-foreground'
                : 'text-emerald-600')
            }
          >
            {saving ? (
              <>
                <Loader2 size={11} className="animate-spin" />
                {t('actions.saving', 'Saving...')}
              </>
            ) : saveError ? (
              <>
                <AlertCircle size={11} />
                {saveError}
              </>
            ) : (
              <>
                <Check size={11} />
                {t('review.savedAt', 'Saved')}{' '}
                {lastSavedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </>
            )}
          </span>
        )}

        {/* ── Right: Cancel / Save / Approve / ⋮ ── */}
        <div className="flex shrink-0 items-center gap-1.5">
          <Button
            variant="ghost"
            size="sm"
            className="h-8 px-3 text-xs text-muted-foreground hover:text-foreground"
            onClick={() => navigate(-1)}
          >
            {t('actions.cancel')}
          </Button>

          <Button
            variant="outline"
            size="sm"
            className="h-8 gap-1 px-3 text-xs"
            onClick={handleSaveContent}
            disabled={saving}
          >
            {saving && <Loader2 size={12} className="animate-spin" />}
            {t('actions.saveDraft')}
          </Button>

          {status === 'approved' && handleStatusChange && (
            <Button
              variant="outline"
              size="sm"
              className="h-8 gap-1 border-indigo-200 px-3 text-xs text-indigo-700 hover:bg-indigo-50"
              onClick={() => handleStatusChange('layout_completed')}
              disabled={saving}
            >
              {t('actions.markLayoutCompleted', 'Mark Layout Completed')}
            </Button>
          )}

          <Popover open={approveOpen} onOpenChange={setApproveOpen}>
            <PopoverTrigger asChild>
              <Button
                size="sm"
                className="h-8 gap-1 bg-emerald-500 px-3 text-xs text-white hover:bg-emerald-600"
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

          {/* Overflow menu — Reject sits here since it's less common than Approve */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="size-8 text-muted-foreground hover:text-foreground"
                aria-label={t('common.more', 'More')}
              >
                <MoreVertical size={16} />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-44">
              <DropdownMenuItem
                className="text-destructive focus:text-destructive"
                onSelect={(e) => {
                  // Don't auto-close — open the reject popover so the user
                  // can type a reason.
                  e.preventDefault();
                  setRejectOpen(true);
                }}
              >
                <X size={14} className="mr-2" />
                {t('actions.reject')}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Hidden anchor for the reject popover so it can position relative
              to the overflow button cluster. We render it always-mounted but
              triggered by the overflow menu item above. */}
          <Popover open={rejectOpen} onOpenChange={setRejectOpen}>
            <PopoverTrigger asChild>
              <span className="sr-only" aria-hidden="true" />
            </PopoverTrigger>
            <PopoverContent align="end" className="w-64 p-3">
              <p className="mb-2 text-xs font-medium text-foreground">
                {t('actions.reject')}?
              </p>
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
        </div>
      </div>

      {/* ── Reviewed-by attribution (only for terminal statuses) ── */}
      {['approved', 'rejected', 'published', 'flagged', 'layout_completed'].includes(status) &&
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

      {/* ── Headline (large, in-body) ── */}
      <div className="shrink-0 bg-background px-6 pt-4 pb-2">
        <input
          type="text"
          className="w-full border-none bg-transparent px-0 text-2xl font-bold leading-tight text-foreground outline-none placeholder:text-muted-foreground/50"
          value={headline}
          onChange={(e) => setHeadline(e.target.value)}
          placeholder={t('review.headlinePlaceholder') || 'Headline...'}
        />
      </div>
    </>
  );
}
