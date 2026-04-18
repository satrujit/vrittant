import { useEffect, useState, useRef } from 'react';
import {
  AlertTriangle,
  BookOpen,
  Calendar,
  Check,
  Clock,
  ExternalLink,
  FileText,
  History,
  Info,
  Loader2,
  MapPin,
  MessageSquare,
  Send,
  UserCircle2,
  X,
} from 'lucide-react';
import { useI18n } from '../../i18n';
import { useAuth } from '../../contexts/AuthContext';
import {
  fetchReporters,
  fetchStoryComments,
  getAssignmentLog,
  postStoryComment,
  reassignStory,
  updateStory,
} from '../../services/api';
import { Avatar, StatusBadge, CategoryChip } from '../common';
import { formatDate, formatTimeAgo } from '../../utils/helpers';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import ReassignPopover from '../assignment/ReassignPopover';

const PRIORITY_COLORS = {
  normal: '#3B82F6',
  urgent: '#F59E0B',
  breaking: '#EF4444',
};

/**
 * Card-style section wrapper. Groups related controls under a small
 * uppercase header so the side panel reads as a stack of self-contained
 * blocks rather than one continuous scroll.
 */
function Section({ icon: Icon, title, children, className }) {
  return (
    <section
      className={cn(
        'rounded-lg border border-border bg-background/50 mx-3 mb-3 overflow-hidden',
        className
      )}
    >
      <header className="flex items-center gap-1.5 px-3 pt-2.5 pb-1.5">
        {Icon && <Icon size={11} className="text-muted-foreground" />}
        <span className="text-[10px] font-semibold uppercase tracking-[0.06em] text-muted-foreground">
          {title}
        </span>
      </header>
      <div className="pb-1.5">{children}</div>
    </section>
  );
}

/**
 * One settings row — label on the left, value/control on the right.
 */
function Row({ label, children }) {
  return (
    <div className="flex items-center justify-between gap-2 px-3 py-1.5 text-xs">
      <span className="shrink-0 text-muted-foreground">{label}</span>
      <div className="flex min-w-0 items-center gap-1 text-foreground">{children}</div>
    </div>
  );
}

/**
 * ReviewSidePanel — fixed right panel on the ReviewPage.
 *
 * Holds everything that used to live in the cluttered top metadata bar
 * (status, priority, category, location, date, source, edition assignment)
 * plus the assignee selector and a per-story comment thread.
 *
 * Layout: scroll-y, sections stacked top-to-bottom, comments anchored at
 * the bottom and grow to fill remaining height.
 */
export default function ReviewSidePanel({
  id,
  story,
  setStory,
  // settings (mirrored from useReviewState)
  category,
  setCategory,
  status,
  priority,
  setPriority,
  // editions
  editions,
  selectedEdition,
  setSelectedEdition,
  selectedPage,
  setSelectedPage,
  editionPages,
  assigningToEdition,
  editionAssignments,
  handleAssignToEdition,
  handleRemoveFromEdition,
}) {
  const { t } = useI18n();
  const { config, user } = useAuth();

  const priorityLevels = (config?.priority_levels || [])
    .filter((p) => p.is_active)
    .map((p) => p.key);
  const activePriorities =
    priorityLevels.length > 0 ? priorityLevels : ['normal', 'urgent', 'breaking'];

  // ── Assignment ─────────────────────────────────────────────────────────
  const [reviewers, setReviewers] = useState([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [logEntries, setLogEntries] = useState(null);
  const [logLoading, setLogLoading] = useState(false);

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

  useEffect(() => {
    if (!historyOpen) return;
    setLogLoading(true);
    getAssignmentLog(id)
      .then((entries) => setLogEntries(Array.isArray(entries) ? entries : []))
      .catch(() => setLogEntries([]))
      .finally(() => setLogLoading(false));
  }, [historyOpen, id]);

  const handleReassign = async (userId) => {
    const reviewer = reviewers.find((r) => String(r.id) === String(userId));
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
      await reassignStory(id, userId);
    } catch (err) {
      console.error('Failed to reassign story:', err);
    }
  };

  const currentAssigneeId = story?.assignee_id ?? story?.assigned_to;

  // ── Comments ───────────────────────────────────────────────────────────
  const [comments, setComments] = useState([]);
  const [commentsLoading, setCommentsLoading] = useState(true);
  const [commentDraft, setCommentDraft] = useState('');
  const [posting, setPosting] = useState(false);
  const commentsEndRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    setCommentsLoading(true);
    fetchStoryComments(id)
      .then((rows) => {
        if (cancelled) return;
        setComments(Array.isArray(rows) ? rows : []);
      })
      .catch(() => !cancelled && setComments([]))
      .finally(() => !cancelled && setCommentsLoading(false));
    return () => {
      cancelled = true;
    };
  }, [id]);

  useEffect(() => {
    // Auto-scroll to bottom when new comments arrive.
    commentsEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [comments.length]);

  const handlePostComment = async () => {
    const body = commentDraft.trim();
    if (!body || posting) return;
    setPosting(true);
    // Optimistic insert with a temp id; we replace it with the server row on success.
    const tempId = `tmp-${Date.now()}`;
    const optimistic = {
      id: tempId,
      author_id: user?.id || '',
      author_name: user?.name || '',
      body,
      created_at: new Date().toISOString(),
      _pending: true,
    };
    setComments((prev) => [...prev, optimistic]);
    setCommentDraft('');
    try {
      const saved = await postStoryComment(id, body);
      setComments((prev) => prev.map((c) => (c.id === tempId ? saved : c)));
    } catch (err) {
      console.error('Failed to post comment:', err);
      // Roll back optimistic insert + restore draft so the user can retry.
      setComments((prev) => prev.filter((c) => c.id !== tempId));
      setCommentDraft(body);
    } finally {
      setPosting(false);
    }
  };

  return (
    <aside className="flex h-full w-[320px] shrink-0 flex-col overflow-hidden border-l border-border bg-card">
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* ─────────── Settings (scrolls) ─────────── */}
        <div className="overflow-y-auto border-b border-border pt-3">
          <Section icon={Info} title={t('review.sidePanel.details', 'Details')}>
          <Row label={t('table.status', 'Status')}>
            <StatusBadge status={status} size="sm" />
          </Row>

          {/* Category */}
          <Row label={t('table.category', 'Category')}>
            <Popover>
              <PopoverTrigger asChild>
                <button className="cursor-pointer border-none bg-transparent p-0">
                  <CategoryChip category={category || story.category} />
                </button>
              </PopoverTrigger>
              <PopoverContent align="end" className="max-h-60 w-48 overflow-y-auto p-2">
                {(config?.categories?.filter((c) => c.is_active) || []).map((c) => (
                  <button
                    key={c.key}
                    className={cn(
                      'flex w-full rounded-md border-none bg-transparent px-2 py-1 text-left text-xs transition-colors hover:bg-accent',
                      category === c.key && 'bg-primary/10 font-semibold'
                    )}
                    onClick={async () => {
                      setCategory(c.key);
                      try {
                        await updateStory(id, { category: c.key });
                      } catch (err) {
                        console.error('Failed to update category:', err);
                      }
                    }}
                  >
                    {t(`categories.${c.key}`, c.label || c.key)}
                  </button>
                ))}
              </PopoverContent>
            </Popover>
          </Row>

          {/* Priority */}
          <Row label={t('review.priority', 'Priority')}>
            <Popover>
              <PopoverTrigger asChild>
                <button
                  className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold text-white"
                  style={{ backgroundColor: PRIORITY_COLORS[priority] || PRIORITY_COLORS.normal }}
                >
                  {priority === 'breaking' && <AlertTriangle size={10} />}
                  {priority === 'urgent' && <Clock size={10} />}
                  {t(`priority.${priority}`, priority)}
                </button>
              </PopoverTrigger>
              <PopoverContent align="end" className="w-36 p-2">
                {activePriorities.map((level) => (
                  <button
                    key={level}
                    className={cn(
                      'flex w-full items-center gap-2 rounded-md border-none bg-transparent px-2 py-1.5 text-left text-xs transition-colors hover:bg-accent',
                      priority === level && 'bg-primary/10 font-semibold'
                    )}
                    onClick={async () => {
                      setPriority(level);
                      try {
                        await updateStory(id, { priority: level });
                      } catch (err) {
                        console.error('Failed to update priority:', err);
                      }
                    }}
                  >
                    <span
                      className="size-2.5 rounded-full"
                      style={{ backgroundColor: PRIORITY_COLORS[level] }}
                    />
                    {t(`priority.${level}`, level)}
                  </button>
                ))}
              </PopoverContent>
            </Popover>
          </Row>

          {story.location && (
            <Row label={t('review.locationLabel', 'Location')}>
              <MapPin size={11} className="text-muted-foreground" />
              <span className="truncate">{story.location}</span>
            </Row>
          )}

          <Row label={t('review.dateLabel', 'Submitted')}>
            <Calendar size={11} className="text-muted-foreground" />
            <span className="truncate">{formatDate(story.submittedAt)}</span>
          </Row>

          {story.source && (
            <Row label={t('review.sourceLabel', 'Source')}>
              {story.source.startsWith('http') ? (
                <a
                  href={story.source}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 truncate text-primary hover:underline"
                  title={story.source}
                >
                  <ExternalLink size={11} />
                  {t('review.source', 'Source')}
                </a>
              ) : (
                <span className="inline-flex items-center gap-1 truncate">
                  <FileText size={11} className="text-muted-foreground" />
                  {story.source === 'Reporter Submitted'
                    ? t('review.reporterSubmitted', 'Reporter Submitted')
                    : story.source === 'Editor Created'
                    ? t('review.editorCreated', 'Editor Created')
                    : story.source}
                </span>
              )}
            </Row>
          )}
          </Section>

          {/* ─────────── Edition assignment ─────────── */}
          <Section icon={BookOpen} title={t('review.assignEditionShort', 'Edition')}>
          <div className="px-3 pb-1">
            {editionAssignments.length > 0 && (
              <div className="mb-2 flex flex-col gap-1">
                {editionAssignments.map((a, i) => (
                  <div
                    key={`${a.edition_id}-${a.page_id}-${i}`}
                    className="flex items-center justify-between gap-1 rounded-md bg-muted/50 px-2 py-1"
                  >
                    <span className="truncate text-xs text-foreground">
                      {a.edition_title} &rarr; {a.page_name}
                    </span>
                    <button
                      className="shrink-0 rounded p-0.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                      onClick={() => handleRemoveFromEdition(a.edition_id, a.page_id)}
                      title="Remove"
                    >
                      <X size={11} />
                    </button>
                  </div>
                ))}
              </div>
            )}
            <select
              className="mb-1.5 w-full rounded-md border border-border bg-card px-2 py-1.5 text-xs text-foreground outline-none focus:border-ring"
              value={selectedEdition || ''}
              onChange={(e) => setSelectedEdition(e.target.value || null)}
            >
              <option value="">{t('review.chooseEdition')}</option>
              {editions.map((ed) => (
                <option key={ed.id} value={ed.id}>
                  {ed.title} ({ed.publication_date})
                </option>
              ))}
            </select>
            {selectedEdition && (
              <select
                className="mb-1.5 w-full rounded-md border border-border bg-card px-2 py-1.5 text-xs text-foreground outline-none focus:border-ring"
                value={selectedPage || ''}
                onChange={(e) => setSelectedPage(e.target.value || null)}
              >
                <option value="">{t('review.choosePage')}</option>
                {editionPages.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.page_name}
                  </option>
                ))}
              </select>
            )}
            <Button
              size="sm"
              className="h-7 w-full text-xs"
              disabled={!selectedEdition || !selectedPage || assigningToEdition}
              onClick={handleAssignToEdition}
            >
              {assigningToEdition && <Loader2 size={12} className="animate-spin" />}
              {assigningToEdition ? '...' : t('review.assignButton')}
            </Button>
          </div>
          </Section>

          {/* ─────────── Assignment ─────────── */}
          <Section icon={UserCircle2} title={t('assignment.assignedTo', 'Assigned to')}>
            <div className="flex items-center justify-between gap-2 px-3 pb-1">
              <ReassignPopover
                assigneeId={currentAssigneeId}
                assigneeName={story?.assignee_name}
                matchReason={story?.assigned_match_reason}
                reviewers={reviewers}
                onReassign={handleReassign}
              />
              <Dialog open={historyOpen} onOpenChange={setHistoryOpen}>
                <DialogTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 gap-1 px-1.5 text-[11px]"
                    title={t('assignment.history')}
                  >
                    <History size={12} />
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
                          const fromLabel =
                            e.from_user_name || t('assignment.autoAssigned');
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
          </Section>
        </div>

        {/* ─────────── Comments (fills remaining height) ─────────── */}
        <div className="flex min-h-0 flex-1 flex-col">
          <div className="flex items-center gap-1.5 px-4 pt-3 pb-1.5">
            <MessageSquare size={11} className="text-muted-foreground" />
            <span className="text-[10px] font-semibold uppercase tracking-[0.06em] text-muted-foreground">
              {t('review.comments.title', 'Comments')}
              {comments.length > 0 && (
                <span className="ml-1 normal-case tracking-normal text-muted-foreground/60">
                  ({comments.length})
                </span>
              )}
            </span>
          </div>
          <div className="flex-1 overflow-y-auto px-3 pb-2">
            {commentsLoading ? (
              <div className="flex items-center justify-center py-6">
                <Loader2 size={16} className="animate-spin text-muted-foreground" />
              </div>
            ) : comments.length === 0 ? (
              <p className="py-4 text-center text-xs italic text-muted-foreground">
                {t('review.comments.empty', 'No comments yet')}
              </p>
            ) : (
              <ol className="flex flex-col gap-2">
                {comments.map((c) => (
                  <li
                    key={c.id}
                    className={cn(
                      'rounded-md border border-border bg-background px-2.5 py-1.5',
                      c._pending && 'opacity-60'
                    )}
                  >
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-[11px] font-semibold text-foreground">
                        {c.author_name || '—'}
                      </span>
                      <span
                        className="text-[10px] text-muted-foreground"
                        title={formatDate(c.created_at)}
                      >
                        {formatTimeAgo(c.created_at)}
                      </span>
                    </div>
                    <p className="mt-0.5 whitespace-pre-wrap break-words text-xs text-foreground">
                      {c.body}
                    </p>
                  </li>
                ))}
                <div ref={commentsEndRef} />
              </ol>
            )}
          </div>
          <div className="shrink-0 border-t border-border p-2">
            <textarea
              className="mb-1.5 w-full resize-none rounded-md border border-border bg-background px-2 py-1.5 text-xs text-foreground outline-none placeholder:text-muted-foreground/60 focus:border-ring"
              placeholder={t('review.comments.placeholder', 'Add a comment…')}
              rows={2}
              value={commentDraft}
              onChange={(e) => setCommentDraft(e.target.value)}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                  e.preventDefault();
                  handlePostComment();
                }
              }}
            />
            <div className="flex items-center justify-between gap-1">
              <span className="text-[10px] text-muted-foreground">
                {t('review.comments.shortcut', '⌘↩ to post')}
              </span>
              <Button
                size="sm"
                className="h-6 gap-1 px-2 text-[11px]"
                disabled={!commentDraft.trim() || posting}
                onClick={handlePostComment}
              >
                {posting ? <Loader2 size={11} className="animate-spin" /> : <Send size={11} />}
                {t('review.comments.post', 'Post')}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
