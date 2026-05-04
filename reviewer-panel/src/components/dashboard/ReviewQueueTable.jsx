import { useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { Avatar } from '../common';
import { formatDate } from '../../utils/helpers';
import { categoryDotColor } from '../../utils/categoryColors';
import { useI18n } from '../../i18n';
import { DENSITIES } from '../../hooks/useDensityPreference';
import InlineStatusPill from './InlineStatusPill';
import RowHoverPeek from './RowHoverPeek';

// Map the backend `source` string (heterogeneous, set by various ingest
// paths) into a human-readable submission mode shown below the time. The
// values here are the strings that get written by the routers/services
// that create stories — keep this map in sync if a new ingest path lands.
function formatSource(source) {
  if (!source) return '';
  const s = String(source);
  if (s === 'whatsapp') return 'WhatsApp';
  if (s === 'Reporter Submitted') return 'Mobile App';
  if (s === 'Editor Created') return 'Editor';
  if (s.startsWith('Email · ') || s.startsWith('Email')) return 'Email';
  // The research-from-article flow stores the article URL as `source`.
  if (s.startsWith('http://') || s.startsWith('https://')) return 'AI Generated';
  return s;
}

// Column geometry — kept identical between header and rows so they line up.
// Story gets the most space; reporter sits AFTER submitted/category so the
// title is the first thing the eye lands on. Submitted is wide enough for a
// time stamp on the first line and a submission-mode label below.
const BASE_GRID_COLS =
  'minmax(0,3fr) 140px 130px minmax(0,1.4fr) 130px';

/**
 * Optional appended-column definition for the queue table.
 *
 * Pages that need extra signals on each row (All Stories needs Reviewed by
 * + Assigned to + per-row admin actions) can pass an array of these
 * descriptors. Each one widens the grid by `width` and renders its header
 * + cell content via `render(story)`. Columns appear AFTER the Status pill.
 *
 * extraColumn shape:
 *   {
 *     id:     string,            unique, used for React keys
 *     header: ReactNode,         text shown in the sticky header bar
 *     width:  string,            valid grid-template-columns track size
 *                                (e.g. "140px", "minmax(0,1fr)")
 *     render: (story) => node    cell content for one row
 *     stopRowClick?: boolean     when true, swallows clicks inside the
 *                                cell so they don't trigger row-nav.
 *                                Use for popovers / menus that have
 *                                their own click semantics.
 *   }
 */
export default function ReviewQueueTable({
  stories,
  loading,
  density = 'comfortable',
  extraColumns = [],
}) {
  const navigate = useNavigate();
  const { t } = useI18n();
  const rowHeight = DENSITIES[density].rowHeight;
  // Compose the grid template once per render. The base 5 tracks always
  // come first; any extras append in the order the page supplied them.
  const gridCols = extraColumns.length
    ? `${BASE_GRID_COLS} ${extraColumns.map((c) => c.width).join(' ')}`
    : BASE_GRID_COLS;

  if (loading && stories.length === 0) {
    return (
      <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
        {t('common.loading') || 'Loading…'}
      </div>
    );
  }

  if (!loading && stories.length === 0) {
    return (
      <div className="flex h-40 flex-col items-center justify-center gap-1 text-sm text-muted-foreground">
        <span className="text-base font-medium text-foreground">{t('dashboard.noReports')}</span>
        <span className="text-xs">{t('dashboard.noReportsHint') || 'New submissions will appear here.'}</span>
      </div>
    );
  }

  return (
    <div role="grid" className="divide-y divide-border/80">
      {/* Sticky header */}
      <div
        className="sticky top-0 z-10 grid items-center gap-4 bg-background/95 px-4 text-[11px] font-medium uppercase tracking-wider text-muted-foreground backdrop-blur"
        style={{ gridTemplateColumns: gridCols, height: 36 }}
      >
        <div>{t('table.storyTitle')}</div>
        <div>{t('table.submissionTime')}</div>
        <div>{t('table.category')}</div>
        <div>{t('table.reporterSubject')}</div>
        <div>{t('table.status')}</div>
        {extraColumns.map((col) => (
          <div key={col.id}>{col.header}</div>
        ))}
      </div>

      {stories.map((story) => {
        return (
          <div
            key={story.id}
            role="row"
            data-row-id={story.id}
            className={cn(
              'group grid cursor-pointer items-center gap-4 px-4 transition-colors',
              'hover:bg-accent/40',
            )}
            style={{ gridTemplateColumns: gridCols, height: rowHeight }}
            onClick={() => navigate(`/review/${story.id}`)}
          >
            {/* Story title — the hover-peek triggers ONLY on the headline
                text glyphs, not the surrounding cell. Wrapping the inline
                <span> in a truncating block keeps the ellipsis behaviour
                while letting mouseenter fire only when the cursor is on
                the rendered text. hover:text-primary turns the headline
                coral as a visual confirmation that the peek is armed. */}
            <div className="min-w-0">
              <div className="truncate text-[13.5px] font-medium text-foreground">
                <RowHoverPeek story={story}>
                  <span className="cursor-pointer transition-colors hover:text-primary">
                    {story.headline || t('table.untitled') || 'Untitled'}
                  </span>
                </RowHoverPeek>
              </div>
              {story.display_id && (
                <div className="text-[11px] font-medium text-blue-600">{story.display_id}</div>
              )}
            </div>

              {/* Submitted — time on top, ingest mode below */}
              <div className="min-w-0">
                <div className="truncate text-xs tabular-nums text-foreground">
                  {formatDate(story.submittedAt)}
                </div>
                {formatSource(story.source) && (
                  <div className="truncate text-[11px] text-muted-foreground">
                    {formatSource(story.source)}
                  </div>
                )}
              </div>

              {/* Category — coloured dot + capitalised label */}
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span
                  className="inline-block size-1.5 shrink-0 rounded-full"
                  style={{ backgroundColor: categoryDotColor(story.category) }}
                />
                <span className="truncate capitalize">{story.category || '—'}</span>
              </div>

              {/* Reporter — pushed right of category */}
              <div className="flex min-w-0 items-center gap-2">
                <Avatar
                  initials={story.reporter?.initials}
                  color={story.reporter?.color}
                  size="sm"
                />
                <div className="min-w-0">
                  <div className="truncate text-[13px] text-foreground">
                    {story.reporter?.name || '—'}
                  </div>
                  {story.reporter?.area_name && (
                    <div className="truncate text-[11px] text-muted-foreground">
                      {story.reporter.area_name}
                    </div>
                  )}
                </div>
              </div>

              {/* Status pill — read-only on the queue table.
                  Clicking through to the review page is the only path for
                  changing status; inline edit on a long table makes
                  accidental approvals/rejections too easy. */}
              <div>
                <InlineStatusPill status={story.status} disabled />
              </div>

              {/* Page-supplied extra columns (Reviewed by, Assigned to,
                  per-row admin actions, etc). Cells that contain
                  popovers / dropdown menus pass `stopRowClick: true` so
                  their own click semantics aren't hijacked by the
                  whole-row navigate. */}
              {extraColumns.map((col) => (
                <div
                  key={col.id}
                  onClick={col.stopRowClick ? (e) => e.stopPropagation() : undefined}
                >
                  {col.render(story)}
                </div>
              ))}
          </div>
        );
      })}
    </div>
  );
}
