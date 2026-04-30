import { useEffect, useState, useRef } from 'react';
import {
  ExternalLink,
  Flag,
  History,
  Loader2,
  MapPin,
  Pencil,
  Send,
  Sparkles,
  Tag as TagIcon,
  UserCircle2,
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
import { Avatar, StatusProgress } from '../common';
import { getCategoryColor, getInitials } from '../../utils/helpers';
import { formatDate, formatTimeAgo } from '../../utils/helpers';
import { getAvatarColor } from '../../services/api';
import { assignableReviewers } from '../../utils/users';
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
import { EditionPlacementMatrix } from './EditionPlacementMatrix';

// Priority chip tint (icon-color + tinted background) — matches the
// shape of getCategoryColor so the priority chip composes with the
// other tag chips in the same row. The dropdown row uses `dot` as a
// solid swatch.
const PRIORITY_PRESETS = {
  normal:   { color: '#6B7280', bg: '#F3F4F6', dot: '#9CA3AF' },
  urgent:   { color: '#DC2626', bg: '#FEE2E2', dot: '#DC2626' },
  breaking: { color: '#7F1D1D', bg: '#FEE2E2', dot: '#7F1D1D' },
};

// Map current story status to the "<verb> by" label for the second
// people-line. The reviewer field always points to whoever last took
// a status action, so labelling it by current status gives the right
// English without needing per-stage attribution columns.
const REVIEWER_VERB_BY_STATUS = {
  approved:         'review.peopleApprovedBy',
  layout_completed: 'review.peopleLayoutBy',
  published:        'review.peoplePublishedBy',
  rejected:         'review.peopleRejectedBy',
  flagged:          'review.peopleFlaggedBy',
};

/**
 * Card — generic rounded container used for the three stacked sections
 * in the redesigned right panel. The new layout treats Status/Page
 * Assignment/Comments as peer cards rather than nested sections under
 * a "Settings" toggle.
 */
function Card({ children, className }) {
  return (
    <div
      className={cn(
        'rounded-lg border border-border bg-card shadow-[0_1px_2px_rgba(0,0,0,0.04)]',
        className
      )}
    >
      {children}
    </div>
  );
}

/**
 * SectionHeader — small uppercase label used inside each card. Same
 * typographic rhythm everywhere so the three cards read as a system.
 */
function SectionHeader({ children, action }) {
  return (
    <div className="flex items-center justify-between px-4 pt-3 pb-1.5">
      <span className="text-[10px] font-bold uppercase tracking-[0.08em] text-foreground">
        {children}
      </span>
      {action}
    </div>
  );
}

/**
 * Chip — icon-in-coloured-square + text label. Used for Category and
 * Location. Click hands off to a popover (provided by parent) for
 * editing; static chips just render without onClick.
 */
function Chip({ icon: Icon, color, bg, label, title, onClick }) {
  const inner = (
    <span className="inline-flex min-w-0 items-center gap-1.5 truncate">
      <span
        className="inline-flex shrink-0 items-center justify-center rounded p-1"
        style={{ backgroundColor: bg }}
      >
        <Icon size={12} style={{ color }} />
      </span>
      <span className="truncate text-[13px] font-medium text-foreground">{label}</span>
    </span>
  );
  const cls =
    'inline-flex max-w-full items-center rounded-md border border-border bg-background px-1.5 py-1 transition-colors hover:bg-accent';
  if (onClick) {
    return (
      <button type="button" onClick={onClick} title={title} className={cls}>
        {inner}
      </button>
    );
  }
  return (
    <span className={cn(cls, 'cursor-default')} title={title}>
      {inner}
    </span>
  );
}

/**
 * PersonRow — tiny attribution line: small initials avatar + label +
 * name. Used for "Reported by · X" / "Approved by · Y" so the workflow
 * chain (reporter → approver → layout) is visible at a glance without
 * opening the assignment history dialog.
 */
function PersonRow({ label, name }) {
  if (!name) return null;
  return (
    <div className="flex items-center gap-2 text-xs">
      <Avatar
        initials={getInitials(name) || '?'}
        size="xs"
        color={getAvatarColor(name)}
      />
      <span className="truncate text-muted-foreground">
        {label}
        <span className="mx-1 text-muted-foreground/50">·</span>
        <span className="font-medium text-foreground">{name}</span>
      </span>
    </div>
  );
}

/**
 * ReviewSidePanel — fixed right panel on the ReviewPage.
 *
 * Three stacked cards: Status & Assignment, Page Assignment, Comments.
 * Comments expands to fill remaining height; the first two cards size
 * to their content. No collapse toggle in the new design — at 1366×768
 * the natural overflow scrolls inside Comments.
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
  // editions (legacy props — the matrix now reads from /admin/editions
  // directly; we keep the names for prop compatibility with ReviewPage)
  editions: _editions,
  selectedEdition: _selectedEdition,
  setSelectedEdition: _setSelectedEdition,
  selectedPage: _selectedPage,
  setSelectedPage: _setSelectedPage,
  editionPages: _editionPages,
  assigningToEdition: _assigningToEdition,
  editionAssignments: _editionAssignments,
  handleAssignToEdition: _handleAssignToEdition,
  handleRemoveFromEdition: _handleRemoveFromEdition,
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
      .then((data) => setReviewers(assignableReviewers(data.reporters || [])))
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

  // ── Derived display values ─────────────────────────────────────────────
  const catKey = category || story.category;
  const { color: catColor, bg: catBg } = getCategoryColor(catKey);
  const catLabel = (() => {
    const k = (catKey || '').toLowerCase().replace(/[\s]+/g, '_');
    const localized = t(`categories.${k}`);
    return localized !== `categories.${k}` ? localized : (catKey || '—');
  })();

  const priorityPreset = PRIORITY_PRESETS[priority] || PRIORITY_PRESETS.normal;
  const priorityLabel = t(`priority.${priority}`, priority);

  // People attribution. We always know the reporter; we may also know
  // the most-recent reviewer (whoever changed status last). Label that
  // second person by what they did — the verb depends on current
  // status because the API stores only one reviewed_by field.
  const reporterName = story?.reporter?.name || '';
  const reviewerName = story?.reviewer_name || '';
  const reviewerVerbKey = REVIEWER_VERB_BY_STATUS[status] || 'review.peopleReviewedBy';
  const showReviewer = !!reviewerName && status !== 'submitted' && status !== 'draft';

  const sourceLabel = (() => {
    if (!story.source) return '';
    if (story.source.startsWith('http')) return t('review.source', 'Source');
    if (story.source === 'Reporter Submitted') return t('review.reporterSubmitted', 'Reporter Submitted');
    if (story.source === 'Editor Created') return t('review.editorCreated', 'Editor Created');
    return story.source;
  })();
  const sourceIsUrl = !!story.source && story.source.startsWith('http');

  const assigneeName = story?.assignee_name || t('assignment.unassigned', 'Unassigned');
  const assigneeInitials = getInitials(story?.assignee_name || '');

  return (
    <aside className="flex h-full w-[340px] shrink-0 flex-col overflow-hidden border-l border-border bg-muted/20">
      <div className="flex flex-1 flex-col gap-3 overflow-hidden p-3">
        {/* ─────────── Card 1: Status + Assignment ─────────── */}
        <Card className="shrink-0 p-3">
          {/* Status: pill on top + thin progress bar. Priority moved
              into the chip row below — keeping it up here as a dangling
              pill made the card top look unbalanced. */}
          <StatusProgress status={status} />

          {/* Tag chips: Category, Location, Priority. All three share
              the same icon-in-tinted-square + label visual so they
              read as one row of metadata. Each opens its own picker. */}
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Popover>
              <PopoverTrigger asChild>
                <span className="inline-block">
                  <Chip
                    icon={TagIcon}
                    color={catColor}
                    bg={catBg}
                    label={catLabel}
                    title={catLabel}
                    onClick={() => {}}
                  />
                </span>
              </PopoverTrigger>
              <PopoverContent align="start" className="max-h-60 w-48 overflow-y-auto p-2">
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

            {story.location && (
              <Chip
                icon={MapPin}
                color="#DC2626"
                bg="#FEE2E2"
                label={story.location}
                title={story.location}
              />
            )}

            <Popover>
              <PopoverTrigger asChild>
                <span className="inline-block">
                  <Chip
                    icon={Flag}
                    color={priorityPreset.color}
                    bg={priorityPreset.bg}
                    label={priorityLabel}
                    title={t('review.priority', 'Priority')}
                    onClick={() => {}}
                  />
                </span>
              </PopoverTrigger>
              <PopoverContent align="start" className="w-36 p-2">
                {activePriorities.map((level) => {
                  const preset = PRIORITY_PRESETS[level] || PRIORITY_PRESETS.normal;
                  return (
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
                        className="size-2 rounded-full"
                        style={{ backgroundColor: preset.dot }}
                      />
                      {t(`priority.${level}`, level)}
                    </button>
                  );
                })}
              </PopoverContent>
            </Popover>
          </div>

          {/* Submitted | Source — single muted line so it sits behind
              the Category/Location chips visually. */}
          {(story.submittedAt || sourceLabel) && (
            <p className="mt-3 text-xs text-muted-foreground">
              {story.submittedAt && <span>{formatDate(story.submittedAt)}</span>}
              {story.submittedAt && sourceLabel && <span className="mx-1.5">|</span>}
              {sourceLabel && (
                sourceIsUrl ? (
                  <a
                    href={story.source}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-primary hover:underline"
                    title={story.source}
                  >
                    <ExternalLink size={10} />
                    {sourceLabel}
                  </a>
                ) : (
                  <span>{sourceLabel}</span>
                )
              )}
            </p>
          )}

          {/* People — Reported by + most-recent reviewer action.
              Shows two compact rows so the workflow chain is visible
              without scrolling into the assignment-history dialog. */}
          {(reporterName || showReviewer) && (
            <div className="mt-3 flex flex-col gap-1.5">
              {reporterName && (
                <PersonRow
                  label={t('review.peopleReportedBy', 'Reported by')}
                  name={reporterName}
                />
              )}
              {showReviewer && (
                <PersonRow
                  label={t(reviewerVerbKey, 'Reviewed by')}
                  name={reviewerName}
                />
              )}
            </div>
          )}

          {/* Assigned To — small label + avatar + name + history clock.
              The avatar makes this row scannable in a long Q&A; the
              clock opens the assignment-history dialog. */}
          <div className="mt-4">
            <p className="mb-1.5 text-[10px] font-bold uppercase tracking-[0.08em] text-foreground">
              {t('assignment.assignedTo', 'Assigned To')}
            </p>
            <div className="flex items-center gap-2">
              {story?.assignee_name ? (
                <Avatar
                  initials={assigneeInitials || '?'}
                  size="sm"
                  color={getAvatarColor(story.assignee_name)}
                />
              ) : (
                // Unassigned — render an empty grey circle so the
                // row's left edge is visually consistent.
                <span
                  className="inline-flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-white"
                  style={{ backgroundColor: '#9CA3AF' }}
                  aria-hidden
                >
                  <UserCircle2 size={14} />
                </span>
              )}
              <div className="min-w-0 flex-1">
                <ReassignPopover
                  assigneeId={currentAssigneeId}
                  assigneeName={assigneeName}
                  matchReason={null}
                  reviewers={reviewers}
                  onReassign={handleReassign}
                  triggerClassName="!min-w-0 !w-full !text-primary !font-semibold"
                />
              </div>
              {story?.assigned_match_reason === 'manual' ? (
                <Pencil
                  size={11}
                  className="shrink-0 text-muted-foreground/70"
                  aria-label={t('assignment.matchReason.manual', 'Manually assigned')}
                  role="img"
                />
              ) : story?.assigned_match_reason ? (
                <Sparkles
                  size={11}
                  className="shrink-0 text-muted-foreground/70"
                  aria-label={t(
                    `assignment.matchReason.${story.assigned_match_reason}`,
                    'Auto assigned'
                  )}
                  role="img"
                />
              ) : null}
              <Dialog open={historyOpen} onOpenChange={setHistoryOpen}>
                <DialogTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 shrink-0 p-0 text-muted-foreground hover:text-foreground"
                    title={t('assignment.history')}
                    aria-label={t('assignment.history')}
                  >
                    <History size={14} />
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
          </div>
        </Card>

        {/* ─────────── Card 2: Page Assignment ─────────── */}
        <Card className="shrink-0">
          <SectionHeader>{t('review.pageAssignment', 'Page Assignment')}</SectionHeader>
          <EditionPlacementMatrix storyId={id} />
        </Card>

        {/* ─────────── Card 2.5: WordPress publishing state ───────────
            Only shown once a story has a known wp_push_status (set
            on approve, retract, or any save after first push). Hidden
            for fresh / draft stories so the panel doesn't carry a
            "WordPress: nothing yet" row at all times. */}
        {story?.wpPushStatus && (
          <Card className="shrink-0">
            <SectionHeader>{t('review.wordpress', 'WordPress')}</SectionHeader>
            <_WpStatusChip story={story} t={t} />
          </Card>
        )}

        {/* ─────────── Card 3: Comments (fills remaining height) ─────────── */}
        <Card className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <SectionHeader>
            {t('review.comments.title', 'Comments')}
            {comments.length > 0 && (
              <span className="ml-1 normal-case tracking-normal text-muted-foreground/60">
                ({comments.length})
              </span>
            )}
          </SectionHeader>
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
              <ol className="flex flex-col gap-3">
                {comments.map((c) => (
                  <li key={c.id} className={cn('flex gap-2', c._pending && 'opacity-60')}>
                    <Avatar
                      initials={getInitials(c.author_name || '') || '?'}
                      size="sm"
                      color={getAvatarColor(c.author_name || '')}
                      className="mt-0.5"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="break-words text-xs text-foreground">{c.body}</p>
                      <p
                        className="mt-0.5 text-[10px] text-muted-foreground"
                        title={formatDate(c.created_at)}
                      >
                        {formatDate(c.created_at)}
                      </p>
                    </div>
                  </li>
                ))}
                <div ref={commentsEndRef} />
              </ol>
            )}
          </div>
          {/* Single-row composer with an inline send button. Keeps the
              comment thread visible — the old two-row variant
              (textarea above a separate Post button) ate ~60px that
              the user spent reading rather than typing. */}
          <div className="shrink-0 border-t border-border p-2">
            <div className="relative">
              <textarea
                data-shortcut-target="comment"
                className="w-full resize-none rounded-md border border-border bg-background py-2 pl-3 pr-9 text-xs text-foreground outline-none placeholder:text-muted-foreground/60 focus:border-ring"
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
              <button
                type="button"
                onClick={handlePostComment}
                disabled={!commentDraft.trim() || posting}
                className="absolute bottom-1.5 right-1.5 inline-flex h-7 w-7 items-center justify-center rounded-md bg-transparent text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
                aria-label={t('review.comments.post', 'Post')}
                title={t('review.comments.post', 'Post')}
              >
                {posting ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
              </button>
            </div>
          </div>
        </Card>
      </div>
    </aside>
  );
}


// ── WordPress status chip ────────────────────────────────────────────────
// Maps the server's wp_push_status onto a label + color + optional link.
// Editors see this in the review side panel once a story enters the WP
// pipeline (i.e. has been approved at least once). The state space is
// intentionally small — colour signals "is there anything I need to do?"
// rather than the granular WP-side status.
function _WpStatusChip({ story, t }) {
  const status = story.wpPushStatus;
  const url = story.wpUrl;
  const error = story.wpPushError;

  let label;
  let color;
  let hint;
  if (status === 'pending' || status === 'retract') {
    label = status === 'retract'
      ? t('review.wpRetracting', 'Retracting from website…')
      : t('review.wpPushing', 'Sending to website…');
    color = 'bg-amber-100 text-amber-800 border-amber-200';
  } else if (status === 'ok') {
    label = t('review.wpPushedDraft', 'Sent to website (pending review)');
    color = 'bg-emerald-50 text-emerald-700 border-emerald-200';
  } else if (status === 'failed') {
    label = t('review.wpFailed', 'Push failed');
    color = 'bg-red-50 text-red-700 border-red-200';
    hint = error;
  } else if (status === 'skipped_no_config') {
    label = t('review.wpNoConfig', 'WordPress not configured for this org');
    color = 'bg-stone-50 text-stone-600 border-stone-200';
  } else if (status?.startsWith('skipped_wp_status_publish')) {
    label = t('review.wpLive', 'Live on website');
    color = 'bg-blue-50 text-blue-700 border-blue-200';
  } else if (status?.startsWith('skipped_wp_status_trash')) {
    label = t('review.wpTrashed', 'Rejected by website');
    color = 'bg-stone-50 text-stone-600 border-stone-200';
  } else if (status?.startsWith('skipped_')) {
    label = t('review.wpSkipped', 'Skipped — owned by website team');
    color = 'bg-stone-50 text-stone-600 border-stone-200';
  } else {
    label = status;
    color = 'bg-stone-50 text-stone-600 border-stone-200';
  }

  return (
    <div className="px-4 pb-3">
      <span
        className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium ${color}`}
        title={hint || ''}
      >
        {label}
      </span>
      {url && (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="ml-2 inline-flex items-center text-xs font-medium text-blue-600 hover:underline"
        >
          {t('review.wpOpenLink', 'Open on website ↗')}
        </a>
      )}
      {error && (
        <div className="mt-1.5 text-[11px] text-red-700 break-words">
          {error}
        </div>
      )}
    </div>
  );
}
