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
        <div onMouseEnter={onEnter} onMouseLeave={onLeave} className="contents">
          {children}
        </div>
      </PopoverTrigger>
      <PopoverContent
        side="right"
        align="start"
        className="w-80 p-3"
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
