import { useState, useEffect, useMemo, useCallback } from 'react';
import { Loader2, ChevronLeft, ChevronRight, ChevronDown, ChevronUp, CheckCircle2, XCircle } from 'lucide-react';
import { fetchActivityHeatmap } from '../../services/api';
import { cn } from '@/lib/utils';
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from '@/components/ui/tooltip';

/* -- Helpers ---------------------------------------------------------------- */

function getIntensityLevel(count, avg) {
  if (count === 0) return 0;
  if (avg <= 0) return count > 0 ? 4 : 0;
  const ratio = count / avg;
  if (ratio <= 0.5) return 1;
  if (ratio <= 1.0) return 2;
  if (ratio <= 2.0) return 3;
  return 4;
}

const LEVEL_COLORS = [
  'bg-muted',                                          // 0 -- no activity
  'bg-emerald-200 dark:bg-emerald-900',                // 1 -- low
  'bg-emerald-400 dark:bg-emerald-700',                // 2 -- medium
  'bg-emerald-500 dark:bg-emerald-500',                // 3 -- high
  'bg-emerald-700 dark:bg-emerald-400',                // 4 -- very high
];

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const WEEKDAY_LABELS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

/**
 * Build the full-year calendar grid.
 * Returns { weeks, monthLabels } where weeks is an array of columns,
 * each column is an array of 7 slots (Sun=0 .. Sat=6), each slot is a dateStr or null.
 */
function buildYearGrid(year) {
  const now = new Date();
  const currentYear = now.getFullYear();
  const isCurrentYear = year === currentYear;

  // Start: Jan 1 of the year
  const startDate = new Date(year, 0, 1);
  // End: Dec 31 or today (if current year)
  const endDate = isCurrentYear ? now : new Date(year, 11, 31);

  // We need to start the grid on a Sunday
  const gridStart = new Date(startDate);
  gridStart.setDate(gridStart.getDate() - gridStart.getDay());

  const weeks = [];
  const monthLabels = [];
  let current = new Date(gridStart);
  let lastLabelMonth = -1;

  while (current <= endDate || current.getDay() !== 0) {
    const week = [];
    for (let dayOfWeek = 0; dayOfWeek < 7; dayOfWeek++) {
      const dateStr = current.toISOString().split('T')[0];
      const inRange = current >= startDate && current <= endDate;
      week.push(inRange ? dateStr : null);

      // Track month labels (on the first occurrence of a new month in a week)
      if (inRange && dayOfWeek === 0) {
        const m = current.getMonth();
        if (m !== lastLabelMonth) {
          monthLabels.push({ month: MONTH_NAMES[m], weekIdx: weeks.length });
          lastLabelMonth = m;
        }
      }

      current.setDate(current.getDate() + 1);
    }
    weeks.push(week);

    // Stop once we've passed the end date and completed the week
    if (current > endDate) break;
  }

  return { weeks, monthLabels };
}

/* -- Today Status Panel (multi-reporter dashboard only) -------------------- */

function TodayStatusPanel({ todaySubmitted }) {
  const submitted = todaySubmitted.filter((r) => r.submitted);
  const notSubmitted = todaySubmitted.filter((r) => !r.submitted);

  return (
    <div className="flex flex-col gap-3">
      {submitted.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 mb-2 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
            <CheckCircle2 size={13} />
            Submitted today ({submitted.length})
          </div>
          <div className="flex flex-wrap gap-1.5">
            {submitted.map((r) => (
              <span
                key={r.reporter_id}
                className="inline-flex items-center gap-1 rounded-full bg-emerald-50 dark:bg-emerald-900/30 px-2.5 py-1 text-[11px] font-medium text-emerald-700 dark:text-emerald-400"
              >
                {r.reporter_name}
                <span className="text-emerald-500 font-bold">{r.count}</span>
              </span>
            ))}
          </div>
        </div>
      )}
      {notSubmitted.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 mb-2 text-xs font-semibold text-red-500 dark:text-red-400">
            <XCircle size={13} />
            Not submitted yet ({notSubmitted.length})
          </div>
          <div className="flex flex-wrap gap-1.5">
            {notSubmitted.map((r) => (
              <span
                key={r.reporter_id}
                className="inline-flex items-center rounded-full bg-red-50 dark:bg-red-900/20 px-2.5 py-1 text-[11px] font-medium text-red-600 dark:text-red-400"
              >
                {r.reporter_name}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* -- Reporter Row (multi-reporter mode) ----------------------------------- */

function ReporterHeatmapRow({ reporter, weeks, avgDaily, onDateSelect, selectedDate }) {
  const countMap = useMemo(() => {
    const m = {};
    reporter.days.forEach((d) => { m[d.date] = d.count; });
    return m;
  }, [reporter.days]);

  return (
    <div className="flex items-center gap-3 py-2 border-b border-border/50 last:border-0">
      <div className="w-[140px] shrink-0 truncate text-xs font-medium text-foreground" title={reporter.reporter_name}>
        {reporter.reporter_name}
      </div>
      <div className="flex gap-[2px] overflow-x-auto">
        {weeks.map((week, wi) => (
          <div key={wi} className="flex flex-col gap-[2px]">
            {week.map((dateStr, di) => {
              if (!dateStr) return <div key={di} className="w-[12px] h-[12px]" />;
              const count = countMap[dateStr] || 0;
              const level = getIntensityLevel(count, avgDaily);
              const d = new Date(dateStr);
              const label = `${d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}: ${count} submission${count !== 1 ? 's' : ''}`;
              const isSelected = selectedDate === dateStr;
              return (
                <Tooltip key={dateStr}>
                  <TooltipTrigger asChild>
                    <div
                      className={cn(
                        'w-[12px] h-[12px] rounded-sm transition-colors cursor-pointer',
                        LEVEL_COLORS[level],
                        isSelected && 'ring-2 ring-primary ring-offset-1 ring-offset-card'
                      )}
                      onClick={() => onDateSelect?.(dateStr)}
                    />
                  </TooltipTrigger>
                  <TooltipContent side="top" sideOffset={4} className="text-xs px-2 py-1">
                    {label}
                  </TooltipContent>
                </Tooltip>
              );
            })}
          </div>
        ))}
      </div>
      <div className="shrink-0 ml-auto text-xs text-muted-foreground tabular-nums w-[40px] text-right">
        {reporter.total}
      </div>
    </div>
  );
}

/* -- Main Component -------------------------------------------------------- */

export default function ActivityHeatmap({ reporterId = null, onDateSelect, selectedDate }) {
  const [year, setYear] = useState(new Date().getFullYear());
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [showToday, setShowToday] = useState(false);

  const isSingleReporter = !!reporterId;

  // Calculate days to fetch based on selected year
  const daysToFetch = useMemo(() => {
    const now = new Date();
    const currentYear = now.getFullYear();
    if (year === currentYear) {
      // Days from Jan 1 to today
      const jan1 = new Date(year, 0, 1);
      return Math.ceil((now - jan1) / (1000 * 60 * 60 * 24)) + 1;
    }
    // Full year
    const jan1 = new Date(year, 0, 1);
    const dec31 = new Date(year, 11, 31);
    return Math.ceil((dec31 - jan1) / (1000 * 60 * 60 * 24)) + 1;
  }, [year]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchActivityHeatmap(daysToFetch, reporterId);
      setData(res);
    } catch (err) {
      console.error('Failed to load activity heatmap:', err);
    } finally {
      setLoading(false);
    }
  }, [daysToFetch, reporterId]);

  useEffect(() => {
    load();
    const interval = setInterval(load, 60 * 60 * 1000);
    return () => clearInterval(interval);
  }, [load]);

  const { weeks, monthLabels } = useMemo(() => buildYearGrid(year), [year]);

  // Build a combined count map for single-reporter mode
  const countMap = useMemo(() => {
    if (!data) return {};
    const m = {};
    const reporters = isSingleReporter
      ? data.reporters.filter((r) => String(r.reporter_id) === String(reporterId))
      : data.reporters;
    reporters.forEach((r) => {
      r.days.forEach((d) => {
        m[d.date] = (m[d.date] || 0) + d.count;
      });
    });
    return m;
  }, [data, isSingleReporter, reporterId]);

  // Total submissions for the year
  const yearTotal = useMemo(() => {
    return Object.values(countMap).reduce((sum, c) => sum + c, 0);
  }, [countMap]);

  const avgDaily = data?.avg_daily || 1;

  const currentYear = new Date().getFullYear();
  // Vrittant launched in 2026 — no submissions exist for earlier years,
  // so don't let users navigate to empty grids.
  const MIN_YEAR = 2026;
  const canGoForward = year < currentYear;
  const canGoBack = year > MIN_YEAR;

  if (loading) {
    return (
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="flex items-center justify-center py-8">
          <Loader2 size={20} className="animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  if (!data) return null;

  // Multi-reporter mode: filter and paginate
  const allReporters = isSingleReporter
    ? []
    : data.reporters;
  const displayReporters = expanded ? allReporters : allReporters.slice(0, 8);

  return (
    <TooltipProvider delayDuration={150}>
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        {/* Header with year selector */}
        <div className="flex items-center justify-between px-5 pt-4 pb-2">
          <div>
            <h3 className="text-sm font-semibold text-foreground">
              {isSingleReporter ? 'Submission Activity' : 'Reporter Activity'}
            </h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              {year}
              {isSingleReporter && ` — ${yearTotal} total submissions`}
              {!isSingleReporter && ` — avg ${avgDaily} submissions/day`}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {!isSingleReporter && (
              <button
                className={cn(
                  'text-xs font-medium px-3 py-1.5 rounded-lg transition-colors mr-2',
                  showToday
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground hover:text-foreground'
                )}
                onClick={() => setShowToday(!showToday)}
              >
                Today's Status
              </button>
            )}
            {/* Year selector */}
            <button
              className={cn(
                'p-1 rounded-md transition-colors',
                canGoBack
                  ? 'text-muted-foreground hover:text-foreground hover:bg-accent'
                  : 'text-muted-foreground/30 cursor-not-allowed'
              )}
              onClick={() => canGoBack && setYear((y) => y - 1)}
              disabled={!canGoBack}
              aria-label="Previous year"
            >
              <ChevronLeft size={16} />
            </button>
            <span className="text-sm font-semibold text-foreground tabular-nums min-w-[48px] text-center">
              {year}
            </span>
            <button
              className={cn(
                'p-1 rounded-md transition-colors',
                canGoForward
                  ? 'text-muted-foreground hover:text-foreground hover:bg-accent'
                  : 'text-muted-foreground/30 cursor-not-allowed'
              )}
              onClick={() => canGoForward && setYear((y) => y + 1)}
              disabled={!canGoForward}
              aria-label="Next year"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>

        {/* Today panel (multi-reporter only) */}
        {!isSingleReporter && showToday && data.today_submitted && (
          <div className="px-5 pb-3 pt-1 border-b border-border">
            <TodayStatusPanel todaySubmitted={data.today_submitted} />
          </div>
        )}

        {/* Single-reporter GitHub-style heatmap grid */}
        {isSingleReporter && (
          <div className="px-5 py-3 overflow-x-auto">
            {/* Month labels row */}
            <div className="flex mb-1" style={{ paddingLeft: '32px' }}>
              {(() => {
                // Position month labels above the correct week columns
                const labels = [];
                let lastIdx = -1;
                monthLabels.forEach((ml, i) => {
                  const leftPx = ml.weekIdx * 14; // 12px cell + 2px gap
                  if (lastIdx >= 0 && leftPx - lastIdx < 28) return; // skip if too close
                  lastIdx = leftPx;
                  labels.push(
                    <span
                      key={i}
                      className="text-[10px] text-muted-foreground absolute"
                      style={{ left: `${leftPx}px` }}
                    >
                      {ml.month}
                    </span>
                  );
                });
                return <div className="relative h-4 w-full">{labels}</div>;
              })()}
            </div>

            {/* Grid: 7 rows (Sun-Sat) x N columns (weeks) */}
            <div className="flex gap-0">
              {/* Weekday labels */}
              <div className="flex flex-col gap-[2px] mr-1.5 shrink-0">
                {WEEKDAY_LABELS.map((label, i) => (
                  <div
                    key={i}
                    className="h-[12px] flex items-center justify-end text-[10px] text-muted-foreground"
                    style={{ width: '26px' }}
                  >
                    {i % 2 === 1 ? label : ''}
                  </div>
                ))}
              </div>

              {/* Cells */}
              <div className="flex gap-[2px]">
                {weeks.map((week, wi) => (
                  <div key={wi} className="flex flex-col gap-[2px]">
                    {week.map((dateStr, di) => {
                      if (!dateStr) {
                        return <div key={di} className="w-[12px] h-[12px]" />;
                      }
                      const count = countMap[dateStr] || 0;
                      const level = getIntensityLevel(count, avgDaily);
                      const d = new Date(dateStr);
                      const label = `${d.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })}: ${count} submission${count !== 1 ? 's' : ''}`;
                      const isSelected = selectedDate === dateStr;
                      return (
                        <Tooltip key={dateStr}>
                          <TooltipTrigger asChild>
                            <div
                              className={cn(
                                'w-[12px] h-[12px] rounded-sm transition-all cursor-pointer',
                                LEVEL_COLORS[level],
                                isSelected && 'ring-2 ring-primary ring-offset-1 ring-offset-card'
                              )}
                              onClick={() => onDateSelect?.(dateStr)}
                            />
                          </TooltipTrigger>
                          <TooltipContent side="top" sideOffset={4} className="text-xs px-2 py-1">
                            {label}
                          </TooltipContent>
                        </Tooltip>
                      );
                    })}
                  </div>
                ))}
              </div>
            </div>

            {/* Legend */}
            <div className="flex items-center justify-end gap-1.5 mt-2">
              <span className="text-[10px] text-muted-foreground">Less</span>
              {LEVEL_COLORS.map((cls, i) => (
                <div key={i} className={cn('w-[12px] h-[12px] rounded-sm', cls)} />
              ))}
              <span className="text-[10px] text-muted-foreground">More</span>
            </div>
          </div>
        )}

        {/* Multi-reporter row-based heatmap */}
        {!isSingleReporter && (
          <>
            {/* Legend + month labels */}
            <div className="flex items-center gap-3 px-5 py-2 border-b border-border/50">
              <span className="text-[10px] text-muted-foreground">Less</span>
              {LEVEL_COLORS.map((cls, i) => (
                <div key={i} className={cn('w-[12px] h-[12px] rounded-sm', cls)} />
              ))}
              <span className="text-[10px] text-muted-foreground">More</span>
              <div className="ml-auto flex gap-4">
                {monthLabels.filter((_, i) => i % 1 === 0).map((ml, i) => (
                  <span key={i} className="text-[10px] text-muted-foreground">{ml.month}</span>
                ))}
              </div>
            </div>

            <div className="px-5 py-2 max-h-[400px] overflow-y-auto">
              {displayReporters.map((reporter) => (
                <ReporterHeatmapRow
                  key={reporter.reporter_id}
                  reporter={reporter}
                  weeks={weeks}
                  avgDaily={avgDaily}
                  onDateSelect={onDateSelect}
                  selectedDate={selectedDate}
                />
              ))}
            </div>

            {allReporters.length > 8 && (
              <div className="flex justify-center py-2 border-t border-border/50">
                <button
                  className="flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors px-3 py-1"
                  onClick={() => setExpanded(!expanded)}
                >
                  {expanded ? (
                    <>Show less <ChevronUp size={13} /></>
                  ) : (
                    <>Show all {allReporters.length} reporters <ChevronDown size={13} /></>
                  )}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </TooltipProvider>
  );
}
