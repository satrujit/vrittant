import { useState, useRef, useEffect, useCallback } from 'react';
import { Loader2, Sparkles, LayoutTemplate } from 'lucide-react';

export default function PageLayoutCanvas({ layoutHtml, isGenerating }) {
  const iframeRef = useRef(null);
  const [iframeHeight, setIframeHeight] = useState(1200);

  // Auto-resize iframe to fit content after load
  const handleLoad = useCallback(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;
    try {
      const doc = iframe.contentDocument || iframe.contentWindow?.document;
      if (doc?.body) {
        // Wait a tick for fonts/images to settle
        setTimeout(() => {
          const h = doc.documentElement.scrollHeight || doc.body.scrollHeight;
          if (h > 100) setIframeHeight(h + 20);
        }, 300);
      }
    } catch {
      // cross-origin fallback — keep default height
    }
  }, []);

  // Reset height when new HTML arrives
  useEffect(() => {
    if (layoutHtml) setIframeHeight(1200);
  }, [layoutHtml]);

  if (isGenerating) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-5 bg-muted/30">
        <div className="relative">
          <Loader2 size={36} className="animate-spin text-primary" />
          <Sparkles size={16} className="absolute -right-1 -top-1 animate-pulse text-primary" />
        </div>
        <div className="flex flex-col items-center gap-1.5">
          <p className="text-sm font-semibold text-foreground">Generating layout...</p>
          <p className="text-xs text-muted-foreground">AI is designing your article page</p>
        </div>
        <div className="w-48 overflow-hidden rounded-full bg-border">
          <div className="h-1.5 animate-[shimmer_2s_ease-in-out_infinite] rounded-full bg-gradient-to-r from-primary/20 via-primary to-primary/20" />
        </div>
      </div>
    );
  }

  if (!layoutHtml) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 bg-muted/30 text-muted-foreground">
        <LayoutTemplate size={40} strokeWidth={1.5} />
        <p className="text-sm">
          Click <strong className="mx-0.5 text-foreground">AI Auto-Layout</strong> to generate the article layout
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-1 items-start justify-center overflow-auto bg-muted/20 p-4">
      <iframe
        ref={iframeRef}
        key={layoutHtml.length}
        srcDoc={layoutHtml}
        title="Article Layout Preview"
        onLoad={handleLoad}
        style={{ height: `${iframeHeight}px` }}
        className="w-full max-w-[1060px] rounded border border-border bg-white shadow-lg"
        sandbox="allow-same-origin"
      />
    </div>
  );
}
