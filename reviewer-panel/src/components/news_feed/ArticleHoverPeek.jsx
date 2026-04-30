import { useEffect, useState } from 'react';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';

const HOVER_DELAY_MS = 400;

/**
 * ArticleHoverPeek — same interaction model as the dashboard's
 * RowHoverPeek but for News Feed articles. Wraps an inline trigger
 * (the headline <span>) so mouseenter only fires when the cursor
 * is on the rendered text, not on the empty stretch of the title cell.
 *
 * The popover shows the article's image (if any) + description (if any).
 * If both are empty we render the children unwrapped — there's nothing
 * to peek and we don't want to mount an empty card on every hover.
 */
export default function ArticleHoverPeek({ children, article, enabled = true }) {
  const [open, setOpen] = useState(false);
  const [pendingTimer, setPendingTimer] = useState(null);

  useEffect(() => () => pendingTimer && clearTimeout(pendingTimer), [pendingTimer]);

  if (!enabled || !article) return children;

  const description = (article.description || '').trim().slice(0, 280);
  const image = article.image_url;
  if (!description && !image) return children;

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
          Inline span — mouseenter only fires on the actual text glyphs.
          Same trick as RowHoverPeek; keeps the preview <img> from
          mounting (and fetching) on every grazing cursor pass.
        */}
        <span onMouseEnter={onEnter} onMouseLeave={onLeave}>
          {children}
        </span>
      </PopoverTrigger>
      <PopoverContent
        side="bottom"
        align="start"
        sideOffset={2}
        avoidCollisions={false}
        className="w-80 p-3 shadow-lg"
        onPointerEnter={(e) => e.preventDefault()}
      >
        <div className="space-y-2">
          {image && (
            <img
              src={image}
              alt=""
              className="h-32 w-full rounded-md object-cover"
              loading="lazy"
              onError={(e) => { e.currentTarget.style.display = 'none'; }}
            />
          )}
          {description && (
            <p className="text-xs leading-relaxed text-muted-foreground">
              {description}
            </p>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
