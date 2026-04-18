import { useEffect, useState } from 'react';
import { History, Loader2, UserCircle2 } from 'lucide-react';
import { useI18n } from '../../i18n';
import { fetchReporters, reassignStory, getAssignmentLog } from '../../services/api';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import ReassignPopover from '../assignment/ReassignPopover';
import { formatDate, formatTimeAgo } from '../../utils/helpers';

/**
 * AssigneeBar — assignee display + inline reassign popover + history dialog.
 *
 * Mirrors the assignee cell pattern from AllStoriesPage (commit 5c8795f) but
 * laid out as a horizontal bar suited to the ReviewPage header area.
 *
 * Story is updated optimistically through `setStory` and then refetched (via
 * the parent calling fetchStory) — but for simplicity we patch the same
 * fields the backend would return. The next page load will reconcile.
 */
export default function AssigneeBar({ storyId, story, setStory }) {
  const { t } = useI18n();
  const [reviewers, setReviewers] = useState([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [logEntries, setLogEntries] = useState(null);
  const [logLoading, setLogLoading] = useState(false);

  // Fetch active reviewers — same derivation as AllStoriesPage.
  useEffect(() => {
    fetchReporters()
      .then((data) => {
        const list = data.reporters || [];
        setReviewers(
          list.filter((u) => u.user_type === 'reviewer' && (u.is_active ?? true))
        );
      })
      .catch(() => setReviewers([]));
  }, []);

  // Lazy-load history when the dialog opens.
  useEffect(() => {
    if (!historyOpen) return;
    setLogLoading(true);
    getAssignmentLog(storyId)
      .then((entries) => setLogEntries(Array.isArray(entries) ? entries : []))
      .catch(() => setLogEntries([]))
      .finally(() => setLogLoading(false));
  }, [historyOpen, storyId]);

  const handleReassign = async (userId) => {
    const reviewer = reviewers.find((r) => String(r.id) === String(userId));
    // Optimistic patch.
    setStory((prev) =>
      prev
        ? {
            ...prev,
            assigned_to: userId,
            assignee_id: userId,
            assignee_name: reviewer?.name || prev.assignee_name,
            assigned_match_reason: 'manual',
          }
        : prev
    );
    try {
      await reassignStory(storyId, userId);
    } catch (err) {
      console.error('Failed to reassign story:', err);
    }
  };

  const currentAssigneeId = story?.assignee_id ?? story?.assigned_to;

  return (
    <div className="flex shrink-0 items-center gap-2 border-b border-border bg-muted/20 px-4 py-1.5">
      <UserCircle2 size={14} className="text-muted-foreground" />
      <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {t('assignment.assignedTo')}
      </span>

      {/* Assignee + reassign popover */}
      <ReassignPopover
        assigneeId={currentAssigneeId}
        assigneeName={story?.assignee_name}
        matchReason={story?.assigned_match_reason}
        reviewers={reviewers}
        onReassign={handleReassign}
      />

      {/* History dialog */}
      <Dialog open={historyOpen} onOpenChange={setHistoryOpen}>
        <DialogTrigger asChild>
          <Button variant="ghost" size="sm" className="ml-auto h-6 gap-1 px-2 text-xs">
            <History size={12} />
            {t('assignment.history')}
          </Button>
        </DialogTrigger>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t('assignment.history')}</DialogTitle>
          </DialogHeader>
          <div className="max-h-[60vh] overflow-y-auto">
            {logLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 size={20} className="animate-spin text-muted-foreground" />
              </div>
            ) : !logEntries || logEntries.length === 0 ? (
              <div className="py-8 text-center text-sm text-muted-foreground">
                {t('assignment.historyEmpty')}
              </div>
            ) : (
              <ol className="flex flex-col gap-2">
                {logEntries.map((e) => {
                  const fromLabel = e.from_user_name || t('assignment.autoAssigned');
                  const toLabel = e.to_user_name || '—';
                  let reasonLabel;
                  if (e.reason === 'redistribute') {
                    reasonLabel = t('assignment.redistributed');
                  } else if (e.reason === 'manual') {
                    reasonLabel = e.assigned_by_name
                      ? `${t('assignment.matchReason.manual')} — by ${e.assigned_by_name}`
                      : t('assignment.matchReason.manual');
                  } else {
                    const key = `assignment.matchReason.${e.reason}`;
                    const localized = t(key);
                    reasonLabel = localized !== key ? localized : e.reason;
                  }
                  return (
                    <li
                      key={e.id}
                      className="rounded-md border border-border bg-card px-3 py-2"
                    >
                      <div className="text-xs text-foreground">
                        <span className="font-medium">{fromLabel}</span>
                        <span className="mx-1.5 text-muted-foreground">→</span>
                        <span className="font-medium">{toLabel}</span>
                        <span className="ml-1.5 text-muted-foreground">
                          ({reasonLabel})
                        </span>
                      </div>
                      <div
                        className="mt-0.5 text-[11px] text-muted-foreground"
                        title={formatDate(e.created_at)}
                      >
                        {formatTimeAgo(e.created_at)} · {formatDate(e.created_at)}
                      </div>
                    </li>
                  );
                })}
              </ol>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
