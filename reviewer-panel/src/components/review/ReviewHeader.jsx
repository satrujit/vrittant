import {
  ArrowLeft,
  MapPin,
  Calendar,
  FileText,
  Loader2,
  Save,
  AlertTriangle,
  Clock,
  BookOpen,
  Check,
  ExternalLink,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useI18n } from '../../i18n';
import { useAuth } from '../../contexts/AuthContext';
import { updateStory } from '../../services/api';
import { Avatar, StatusBadge, CategoryChip } from '../common';
import { formatDate } from '../../utils/helpers';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const PRIORITY_COLORS = {
  normal: '#3B82F6',
  urgent: '#F59E0B',
  breaking: '#EF4444',
};

/**
 * ReviewHeader — top metadata bar + sticky headline input.
 *
 * Composed of: back button, reporter avatar, category chip (popover),
 * status badge, priority chip (popover), location, date, source link,
 * edition-assignment popover, approve/reject/save action buttons,
 * and the editable headline.
 *
 * State lives in useReviewState; we receive it via props.
 */
export default function ReviewHeader({
  id,
  story,
  category,
  setCategory,
  status,
  priority,
  setPriority,
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
  const { config } = useAuth();
  const navigate = useNavigate();

  const priorityLevels = (config?.priority_levels || []).filter((p) => p.is_active).map((p) => p.key);
  const activePriorities = priorityLevels.length > 0 ? priorityLevels : ['normal', 'urgent', 'breaking'];

  return (
    <>
      {/* ── Top metadata bar ── */}
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-border bg-card px-4 py-1.5">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <Button variant="outline" size="icon" className="size-7 shrink-0" onClick={() => navigate(-1)}>
            <ArrowLeft size={14} />
          </Button>

          <Avatar initials={story.reporter.initials} color={story.reporter.color} size="sm" />
          <span className="whitespace-nowrap text-xs font-medium text-foreground">{story.reporter.name}</span>

          <span className="select-none text-border">&middot;</span>

          {/* Category */}
          <Popover>
            <PopoverTrigger asChild>
              <button className="cursor-pointer border-none bg-transparent p-0">
                <CategoryChip category={category || story.category} />
              </button>
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
                    try { await updateStory(id, { category: c.key }); } catch (err) { console.error('Failed to update category:', err); }
                  }}
                >
                  {t(`categories.${c.key}`, c.label || c.key)}
                </button>
              ))}
            </PopoverContent>
          </Popover>

          <span className="select-none text-border">&middot;</span>

          <StatusBadge status={status} />

          <span className="select-none text-border">&middot;</span>

          {/* Priority */}
          <Popover>
            <PopoverTrigger asChild>
              <button
                className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold text-white transition-colors"
                style={{ backgroundColor: PRIORITY_COLORS[priority] || PRIORITY_COLORS.normal }}
              >
                {priority === 'breaking' && <AlertTriangle size={10} />}
                {priority === 'urgent' && <Clock size={10} />}
                {t(`priority.${priority}`, priority)}
              </button>
            </PopoverTrigger>
            <PopoverContent align="start" className="w-36 p-2">
              {activePriorities.map((level) => (
                <button
                  key={level}
                  className={cn(
                    'flex w-full items-center gap-2 rounded-md border-none bg-transparent px-2 py-1.5 text-left text-xs transition-colors hover:bg-accent',
                    priority === level && 'bg-primary/10 font-semibold'
                  )}
                  onClick={async () => {
                    setPriority(level);
                    try { await updateStory(id, { priority: level }); } catch (err) { console.error('Failed to update priority:', err); }
                  }}
                >
                  <span className="size-2.5 rounded-full" style={{ backgroundColor: PRIORITY_COLORS[level] }} />
                  {t(`priority.${level}`, level)}
                </button>
              ))}
            </PopoverContent>
          </Popover>

          {story.location && (
            <>
              <span className="select-none text-border">&middot;</span>
              <span className="inline-flex items-center gap-1 whitespace-nowrap text-xs text-muted-foreground"><MapPin size={10} /> {story.location}</span>
            </>
          )}

          <span className="select-none text-border">&middot;</span>
          <span className="inline-flex items-center gap-1 whitespace-nowrap text-xs text-muted-foreground"><Calendar size={10} /> {formatDate(story.submittedAt)}</span>

          {story.source && (
            <>
              <span className="select-none text-border">&middot;</span>
              {story.source.startsWith('http') ? (
                <a
                  href={story.source}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 whitespace-nowrap text-xs text-primary hover:underline truncate max-w-[180px]"
                  title={story.source}
                >
                  <ExternalLink size={10} />
                  {t('review.source', 'Source')}
                </a>
              ) : (
                <span className="inline-flex items-center gap-1 whitespace-nowrap text-xs text-muted-foreground">
                  <FileText size={10} />
                  {story.source === 'Reporter Submitted' ? t('review.reporterSubmitted', 'Reporter Submitted') : story.source === 'Editor Created' ? t('review.editorCreated', 'Editor Created') : story.source}
                </span>
              )}
            </>
          )}

          <span className="select-none text-border">&middot;</span>

          {/* Edition assignment */}
          <Popover>
            <PopoverTrigger asChild>
              <Button variant={editionAssignments.length > 0 ? "outline" : "default"} size="sm" className={editionAssignments.length > 0 ? "h-6 gap-1 px-2 text-xs" : "h-6 gap-1 px-2 text-xs bg-amber-500 text-white hover:bg-amber-600 border-amber-500"}>
                <BookOpen size={12} />
                {editionAssignments.length > 0 ? (
                  <><Check size={12} className="text-emerald-500" /> {editionAssignments.length}</>
                ) : t('review.assignEditionShort')}
              </Button>
            </PopoverTrigger>
            <PopoverContent align="start" className="w-80 p-3">
              <div className="flex flex-col gap-2">
                {editionAssignments.length > 0 && (
                  <div className="flex flex-col gap-1">
                    {editionAssignments.map((a, i) => (
                      <div key={`${a.edition_id}-${a.page_id}-${i}`} className="flex items-center justify-between gap-1 rounded-md bg-muted/50 px-2 py-1">
                        <span className="truncate text-xs text-foreground">
                          {a.edition_title} &rarr; {a.page_name}
                        </span>
                        <button
                          className="shrink-0 rounded p-0.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                          onClick={() => handleRemoveFromEdition(a.edition_id, a.page_id)}
                          title="Remove"
                        >
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
                        </button>
                      </div>
                    ))}
                    <hr className="border-border" />
                  </div>
                )}

                <select
                  className="w-full rounded-md border border-border bg-card px-2 py-1.5 text-xs text-foreground outline-none focus:border-ring"
                  value={selectedEdition || ''}
                  onChange={(e) => setSelectedEdition(e.target.value || null)}
                >
                  <option value="">{t('review.chooseEdition')}</option>
                  {editions.map((ed) => (
                    <option key={ed.id} value={ed.id}>{ed.title} ({ed.publication_date})</option>
                  ))}
                </select>
                {selectedEdition && (
                  <select
                    className="w-full rounded-md border border-border bg-card px-2 py-1.5 text-xs text-foreground outline-none focus:border-ring"
                    value={selectedPage || ''}
                    onChange={(e) => setSelectedPage(e.target.value || null)}
                  >
                    <option value="">{t('review.choosePage')}</option>
                    {editionPages.map((p) => (
                      <option key={p.id} value={p.id}>{p.page_name}</option>
                    ))}
                  </select>
                )}
                <Button
                  size="sm"
                  className="w-full"
                  disabled={!selectedEdition || !selectedPage || assigningToEdition}
                  onClick={handleAssignToEdition}
                >
                  {assigningToEdition ? <Loader2 size={12} className="animate-spin" /> : null}
                  {assigningToEdition ? '...' : t('review.assignButton')}
                </Button>
              </div>
            </PopoverContent>
          </Popover>
        </div>

        {/* Right actions */}
        <div className="flex shrink-0 items-center gap-1.5">
          <Popover open={approveOpen} onOpenChange={setApproveOpen}>
            <PopoverTrigger asChild>
              <Button size="sm" className="h-7 gap-1 bg-emerald-500 px-2.5 text-xs text-white hover:bg-emerald-600">
                <Check size={14} />
                {t('actions.approve')}
              </Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-56 p-3">
              <p className="mb-2 text-xs font-medium text-foreground">{t('actions.approve')}?</p>
              <div className="flex gap-1">
                <Button
                  size="sm"
                  className="flex-1 bg-emerald-500 text-white hover:bg-emerald-600"
                  onClick={() => { handleApprove(); setApproveOpen(false); }}
                  disabled={saving}
                >
                  {saving ? '...' : t('actions.confirm')}
                </Button>
                <Button variant="outline" size="sm" className="flex-1" onClick={() => setApproveOpen(false)}>
                  {t('actions.cancel')}
                </Button>
              </div>
            </PopoverContent>
          </Popover>

          <Popover open={rejectOpen} onOpenChange={setRejectOpen}>
            <PopoverTrigger asChild>
              <Button variant="outline" size="sm" className="h-7 gap-1 border-red-200 px-2.5 text-xs text-red-500 hover:border-red-500 hover:bg-red-50">
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
                  onClick={() => { handleReject(); setRejectOpen(false); }}
                  disabled={saving}
                >
                  {saving ? '...' : t('actions.confirm')}
                </Button>
                <Button variant="outline" size="sm" className="flex-1" onClick={() => setRejectOpen(false)}>
                  {t('actions.cancel')}
                </Button>
              </div>
            </PopoverContent>
          </Popover>

          <Button size="sm" className="h-7 gap-1 px-2.5 text-xs" onClick={handleSaveContent} disabled={saving}>
            {saving ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
            {t('actions.saveDraft')}
          </Button>
        </div>
      </div>

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
