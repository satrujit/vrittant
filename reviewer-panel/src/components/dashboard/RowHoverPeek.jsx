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
          Wrapper MUST have a real DOM box so Radix can position the popover
          against it. `display: contents` (the previous attempt) strips the
          wrapper from the box tree and Radix falls back to the top-left of
          the viewport. A plain block-level div with `w-full` keeps the row's
          full-width grid layout intact and gives Radix something to anchor.
        */}
        <div onMouseEnter={onEnter} onMouseLeave={onLeave} className="block w-full">
          {children}
        </div>
      </PopoverTrigger>
      {/*
        side="bottom" + align="end" hangs the peek below the row's right
        edge, always inside the visible content area. The row is
        full-viewport-width so side="right" would overflow and Radix would
        flip it to side="left" — which lands behind the fixed sidebar.
        Bottom-end is predictable and never collides with the sidebar.
      */}
      <PopoverContent
        side="bottom"
        align="end"
        sideOffset={4}
        collisionPadding={{ top: 12, right: 16, bottom: 16, left: 80 }}
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
