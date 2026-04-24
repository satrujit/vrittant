import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Loader2, X } from 'lucide-react';
import { useI18n } from '../i18n';
import { fetchReporterStories, transformStory, transformReporter, getInitialsFromName, getAvatarColor } from '../services/api';
import { Avatar, StatusBadge, CategoryChip, PageHeader } from '../components/common';
import { formatTimeAgo } from '../utils/helpers';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import ActivityHeatmap from '../components/dashboard/ActivityHeatmap';

function ReporterDetailPage() {
  const { t } = useI18n();
  const { id } = useParams();
  const navigate = useNavigate();

  const [stories, setStories] = useState([]);
  const [reporter, setReporter] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState(null);
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  // Reset to page 1 whenever the date filter changes so we don't land on
  // an out-of-range page (e.g. page 3 of unfiltered → page 3 of filtered
  // when filtered only has 1 page).
  useEffect(() => { setPage(1); }, [selectedDate]);

  // Fetch reporter's stories on mount
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchReporterStories(id)
      .then((data) => {
        if (!cancelled) {
          const transformed = (data.stories || []).map(transformStory);
          setStories(transformed);

          // Extract reporter info from the first story's reporter field
          if (transformed.length > 0 && transformed[0].reporter) {
            setReporter(transformed[0].reporter);
          } else {
            // Build a minimal reporter object from the id
            setReporter({
              id,
              name: 'Reporter',
              initials: '?',
              color: getAvatarColor('Reporter'),
              areaName: '',
            });
          }
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error('Failed to fetch reporter stories:', err);
        if (!cancelled) {
          setStories([]);
          setReporter(null);
          setLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, [id]);

  if (loading) {
    return (
      <div className="p-6 lg:p-8 max-w-[1400px]">
        <Button
          variant="outline"
          size="icon"
          className="border-border bg-transparent text-muted-foreground shrink-0 hover:bg-accent hover:text-foreground hover:border-primary/40"
          onClick={() => navigate('/reporters')}
        >
          <ArrowLeft size={20} />
        </Button>
        <div className="flex items-center justify-center py-16 text-sm text-muted-foreground italic">
          <Loader2 size={24} className="animate-spin" />
        </div>
      </div>
    );
  }

  if (!reporter) {
    return (
      <div className="p-6 lg:p-8 max-w-[1400px]">
        <Button
          variant="outline"
          size="icon"
          className="border-border bg-transparent text-muted-foreground shrink-0 hover:bg-accent hover:text-foreground hover:border-primary/40"
          onClick={() => navigate('/reporters')}
        >
          <ArrowLeft size={20} />
        </Button>
        <div className="flex items-center justify-center py-16 text-sm text-muted-foreground italic">
          {t('reporters.noReporters')}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 max-w-[1400px]">
      <PageHeader
        title={t('reporters.storiesBy', { name: reporter.name })}
        leading={
          <Button
            variant="outline"
            size="icon"
            className="size-10 shrink-0"
            onClick={() => navigate('/reporters')}
            aria-label="Back"
          >
            <ArrowLeft size={18} />
          </Button>
        }
      />

      {/* Reporter info card */}
      <div className="flex items-center gap-4 p-5 bg-card border border-border rounded-xl mb-6">
        <Avatar initials={reporter.initials} color={reporter.color} size="lg" />
        <div className="flex flex-col gap-0.5 flex-1">
          <h2 className="text-[0.9375rem] font-semibold text-foreground m-0">
            {reporter.name}
          </h2>
          <span className="text-sm text-muted-foreground">
            {reporter.areaName || reporter.area_name || ''}
          </span>
        </div>
        <div className="flex flex-col items-center gap-0.5 py-2 px-5 bg-primary/10 rounded-lg">
          <span className="text-xl font-bold text-primary leading-none">
            {stories.length}
          </span>
          <span className="text-xs text-muted-foreground whitespace-nowrap">
            {t('reporters.totalSubmissions')}
          </span>
        </div>
      </div>

      {/* Activity Heatmap */}
      <div className="mb-6">
        <ActivityHeatmap
          reporterId={id}
          onDateSelect={(dateStr) => setSelectedDate((prev) => prev === dateStr ? null : dateStr)}
          selectedDate={selectedDate}
        />
      </div>

      {/* Date filter chip */}
      {selectedDate && (
        <div className="mb-4 flex items-center gap-2">
          <span className="inline-flex items-center gap-2 rounded-lg bg-primary/10 text-primary px-3 py-1.5 text-sm font-medium">
            Showing stories from{' '}
            {new Date(selectedDate + 'T00:00:00').toLocaleDateString('en-IN', {
              day: 'numeric',
              month: 'short',
              year: 'numeric',
            })}
            <button
              className="ml-1 p-0.5 rounded-full hover:bg-primary/20 transition-colors"
              onClick={() => setSelectedDate(null)}
              aria-label="Clear date filter"
            >
              <X size={14} />
            </button>
          </span>
        </div>
      )}

      {/* Story table */}
      {(() => {
        const filteredStories = selectedDate
          ? stories.filter((s) => {
              const submitted = s.submittedAt || s.createdAt;
              if (!submitted) return false;
              return submitted.split('T')[0] === selectedDate;
            })
          : stories;

        // Latest-first by submission time so reviewers see new work at the top.
        const sortedStories = [...filteredStories].sort((a, b) => {
          const ta = new Date(a.submittedAt || a.createdAt || 0).getTime();
          const tb = new Date(b.submittedAt || b.createdAt || 0).getTime();
          return tb - ta;
        });

        const totalPages = Math.max(1, Math.ceil(sortedStories.length / PAGE_SIZE));
        const safePage = Math.min(page, totalPages);
        const pageStart = (safePage - 1) * PAGE_SIZE;
        const visibleStories = sortedStories.slice(pageStart, pageStart + PAGE_SIZE);

        if (filteredStories.length === 0) return (
          <div className="flex items-center justify-center py-16 text-sm text-muted-foreground italic">
            {selectedDate ? `No stories found for ${new Date(selectedDate + 'T00:00:00').toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}` : t('dashboard.noReports')}
          </div>
        );

        return (
          <div className="bg-card border border-border rounded-xl overflow-hidden">
            <Table className="border-collapse">
              <TableHeader>
                <TableRow className="hover:bg-transparent border-b border-border">
                  <TableHead className="py-3 px-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {t('table.reporterSubject')}
                  </TableHead>
                  <TableHead className="py-3 px-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {t('table.submissionTime')}
                  </TableHead>
                  <TableHead className="py-3 px-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {t('table.category')}
                  </TableHead>
                  <TableHead className="py-3 px-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {t('table.status')}
                  </TableHead>
                  <TableHead className="py-3 px-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {t('table.action')}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {visibleStories.map((story) => (
                  <TableRow
                    key={story.id}
                    className="cursor-pointer transition-colors duration-150 ease-in-out hover:bg-accent [&:not(:last-child)]:border-b [&:not(:last-child)]:border-border"
                    onClick={() => navigate(`/review/${story.id}`)}
                  >
                    <TableCell className="py-3 px-4 text-sm text-foreground">
                      <div className="flex items-center gap-3">
                        <Avatar
                          initials={reporter.initials}
                          color={reporter.color}
                          size="sm"
                        />
                        <div className="flex flex-col gap-0.5 min-w-0">
                          <span className="font-medium text-foreground leading-tight line-clamp-1">
                            {story.headline}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {reporter.name}
                          </span>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="py-3 px-4 text-sm text-foreground">
                      <span className="text-xs text-muted-foreground whitespace-nowrap">
                        {formatTimeAgo(story.submittedAt || story.createdAt)}
                      </span>
                    </TableCell>
                    <TableCell className="py-3 px-4 text-sm text-foreground">
                      <CategoryChip category={story.category} />
                    </TableCell>
                    <TableCell className="py-3 px-4 text-sm text-foreground">
                      <StatusBadge status={story.status} />
                    </TableCell>
                    <TableCell className="py-3 px-4 text-sm text-foreground">
                      <Button
                        variant="ghost"
                        size="xs"
                        className="font-semibold text-primary bg-primary/10 border-none hover:bg-primary/40 hover:text-primary-foreground"
                        onClick={(e) => {
                          // Row already navigates — stopPropagation so we don't
                          // fire navigate() twice (which causes a double history
                          // entry the back button has to undo).
                          e.stopPropagation();
                          navigate(`/review/${story.id}`);
                        }}
                      >
                        {t('actions.review')}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {totalPages > 1 && (
              <div className="flex items-center justify-between border-t border-border bg-muted/20 px-4 py-3 text-sm">
                <span className="text-muted-foreground">
                  Showing {pageStart + 1}–{Math.min(pageStart + PAGE_SIZE, sortedStories.length)} of {sortedStories.length}
                </span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={safePage <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                  >
                    Previous
                  </Button>
                  <span className="text-xs text-muted-foreground tabular-nums">
                    Page {safePage} of {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={safePage >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </div>
        );
      })()}
    </div>
  );
}

export default ReporterDetailPage;
