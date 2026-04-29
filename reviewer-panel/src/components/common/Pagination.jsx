import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

/**
 * Shared pagination control with ellipsis truncation.
 *
 * Layout (window of ±1 around the current page, plus first/last anchors):
 *
 *   [‹]  1  2  3  4  5  6  7  [›]            (≤ 7 pages → render all)
 *   [‹]  1  2  3  4  5  …  32 [›]            (current near start)
 *   [‹]  1  …  16 17 18  …  32 [›]           (current in middle)
 *   [‹]  1  …  28 29 30 31 32 [›]            (current near end)
 *
 * Compact, predictable width — never balloons past ~9 buttons regardless
 * of how many pages there are.
 */
export default function Pagination({ currentPage, totalPages, onPageChange }) {
  if (!totalPages || totalPages <= 1) return null;

  const items = _buildPageItems(currentPage, totalPages);

  return (
    <div className="flex items-center gap-1">
      <Button
        variant="outline"
        size="icon-sm"
        onClick={() => onPageChange(Math.max(1, currentPage - 1))}
        disabled={currentPage <= 1}
        aria-label="Previous page"
      >
        <ChevronLeft size={16} />
      </Button>
      {items.map((it, i) =>
        it === '…' ? (
          <span
            key={`ellipsis-${i}`}
            className="inline-flex h-8 min-w-8 items-center justify-center px-1 text-xs text-muted-foreground"
            aria-hidden="true"
          >
            …
          </span>
        ) : (
          <button
            key={it}
            type="button"
            aria-current={it === currentPage ? 'page' : undefined}
            className={cn(
              'inline-flex items-center justify-center min-w-8 h-8 px-2 border rounded-md text-xs font-medium transition-all cursor-pointer',
              it === currentPage
                ? 'bg-primary text-primary-foreground border-primary hover:bg-primary/90'
                : 'bg-card text-foreground border-border hover:bg-accent hover:border-primary/40 hover:text-primary'
            )}
            onClick={() => onPageChange(it)}
          >
            {it}
          </button>
        )
      )}
      <Button
        variant="outline"
        size="icon-sm"
        onClick={() => onPageChange(Math.min(totalPages, currentPage + 1))}
        disabled={currentPage >= totalPages}
        aria-label="Next page"
      >
        <ChevronRight size={16} />
      </Button>
    </div>
  );
}

/**
 * Returns the sequence of page numbers (and '…' placeholders) to render.
 * Pure function for unit testing.
 */
export function _buildPageItems(currentPage, totalPages) {
  // Small lists: render every page so the user can hop directly. The
  // 7-page threshold keeps the worst-case output (1 … N-1 N) at the
  // same width as the all-pages render, so the layout never grows.
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }

  const out = [1];
  // Window of pages adjacent to the current one.
  const windowStart = Math.max(2, currentPage - 1);
  const windowEnd = Math.min(totalPages - 1, currentPage + 1);

  if (windowStart > 2) out.push('…');
  for (let p = windowStart; p <= windowEnd; p++) out.push(p);
  if (windowEnd < totalPages - 1) out.push('…');

  out.push(totalPages);
  return out;
}
