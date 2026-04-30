import { useEffect, useState } from 'react';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';
import { getMediaUrl } from '../../services/api';

const HOVER_DELAY_MS = 400;

export default function RowHoverPeek({ children, story, enabled = true }) {
  const [open, setOpen] = useState(false);
  const [pendingTimer, setPendingTimer] = useState(null);

  useEffect(() => () => pendingTimer && clearTimeout(pendingTimer), [pendingTimer]);

  if (!enabled || !story) return children;

  const firstParagraph = (story.paragraphs?.[0]?.text || '').slice(0, 240);
  const firstImage = story.paragraphs?.find((p) => p.media_path)?.media_path;

  // Nothing to peek — render children without the popover wrapper at all.
  if (!firstParagraph && !firstImage) return children;

  const onEnter = () => {
    const timer = setTimeout(() => setOpen(true), HOVER_DELAY_MS);
    setPendingTimer(timer);
  };
  const onLeave = () => {
    if (pendingTimer) clearTimeout(pendingTimer);
    setPendingTimer(null);
    setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        {/*
          Inline wrapper sized to its text content. Crucial: by using a
          <span> (inline by default) the mouseenter/mouseleave events only
          fire when the cursor is actually over the text glyphs — not the
          empty stretch of the title cell beside the truncated headline.
          This keeps the popover from opening (and the preview <img> from
          mounting and fetching) every time the cursor grazes a row.
          Radix asChild forwards the events + ref to this span, so the
          popover anchors precisely against the rendered text rect.
        */}
        <span onMouseEnter={onEnter} onMouseLeave={onLeave}>
          {children}
        </span>
      </PopoverTrigger>
      {/*
        Anchor under the LEFT edge of the row (the title cell) so the peek
        reads as belonging to that story. side="bottom" align="start" keeps
        the popover inside the visible area; the row is full-viewport-width
        so side="right" would overflow and Radix would flip it to "left",
        landing behind the sidebar. avoidCollisions=false locks the side so
        the popover always opens toward the title — the brain's natural
        anchor — instead of skipping pages around when near the viewport
        bottom.
      */}
      <PopoverContent
        side="bottom"
        align="start"
        sideOffset={2}
        avoidCollisions={false}
        className="w-80 p-3 shadow-lg"
        onPointerEnter={(e) => e.preventDefault()}
      >
        <div className="space-y-2">
          {firstImage && (
            <img
              src={getMediaUrl(firstImage)}
              alt=""
              className="h-32 w-full rounded-md object-cover"
              loading="lazy"
            />
          )}
          <p className="text-xs leading-relaxed text-muted-foreground">
            {firstParagraph || '(empty)'}
          </p>
        </div>
      </PopoverContent>
    </Popover>
  );
}
