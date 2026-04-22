import { useState, useEffect } from 'react';
import { ChevronRight, ChevronLeft, Loader2, ExternalLink, Newspaper, BookOpen } from 'lucide-react';
import { cn } from '@/lib/utils';
import { fetchRelatedStories, searchNewsByTitle } from '../../services/api';

/**
 * Collapsible right panel showing related content for the current story.
 * Two sections: past Vrittant stories + external news articles.
 * Collapsed by default — toggle via a tab on the right edge.
 */
export default function RelatedStoriesPanel({ storyId, headline }) {
  const [open, setOpen] = useState(false);
  const [activeSection, setActiveSection] = useState('stories'); // 'stories' | 'news'
  const [relatedStories, setRelatedStories] = useState([]);
  const [newsArticles, setNewsArticles] = useState([]);
  const [loadingStories, setLoadingStories] = useState(false);
  const [loadingNews, setLoadingNews] = useState(false);
  const [fetched, setFetched] = useState(false);

  // Fetch related content when panel opens for the first time
  useEffect(() => {
    if (!open || fetched || !storyId) return;
    setFetched(true);

    // Fetch related stories
    setLoadingStories(true);
    fetchRelatedStories(storyId)
      .then((data) => setRelatedStories(Array.isArray(data) ? data : []))
      .catch(() => setRelatedStories([]))
      .finally(() => setLoadingStories(false));

    // Fetch related news articles by headline
    if (headline) {
      setLoadingNews(true);
      searchNewsByTitle(headline, 10)
        .then((data) => setNewsArticles(Array.isArray(data) ? data : []))
        .catch(() => setNewsArticles([]))
        .finally(() => setLoadingNews(false));
    }
  }, [open, fetched, storyId, headline]);

  return (
    <>
      {/* Toggle tab — always visible on the right edge */}
      <button
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'absolute right-0 top-1/2 -translate-y-1/2 z-20 flex items-center gap-1 rounded-l-lg border border-r-0 border-border bg-card px-1.5 py-3 text-muted-foreground shadow-md transition-all hover:bg-accent hover:text-foreground cursor-pointer',
          open && 'right-[360px]'
        )}
        title={open ? 'Hide related' : 'Related stories'}
      >
        {open ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        {!open && (
          <span className="text-[11px] font-medium [writing-mode:vertical-lr] rotate-180">
            Related
          </span>
        )}
      </button>

      {/* Panel */}
      <div
        className={cn(
          'absolute right-0 top-0 bottom-0 z-10 w-[360px] border-l border-border bg-background shadow-[-4px_0_16px_rgba(0,0,0,0.05)] transition-transform duration-200 flex flex-col',
          open ? 'translate-x-0' : 'translate-x-full'
        )}
      >
        {/* Section tabs */}
        <div className="flex border-b border-border shrink-0">
          <button
            onClick={() => setActiveSection('stories')}
            className={cn(
              'flex-1 flex items-center justify-center gap-1.5 px-3 py-2.5 text-xs font-medium transition-colors cursor-pointer border-none bg-transparent',
              activeSection === 'stories'
                ? 'text-primary border-b-2 border-primary'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            <BookOpen size={13} />
            Past Stories
            {!loadingStories && relatedStories.length > 0 && (
              <span className="rounded-full bg-primary/10 px-1.5 text-[10px] font-semibold text-primary">
                {relatedStories.length}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveSection('news')}
            className={cn(
              'flex-1 flex items-center justify-center gap-1.5 px-3 py-2.5 text-xs font-medium transition-colors cursor-pointer border-none bg-transparent',
              activeSection === 'news'
                ? 'text-primary border-b-2 border-primary'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            <Newspaper size={13} />
            News Sources
            {!loadingNews && newsArticles.length > 0 && (
              <span className="rounded-full bg-primary/10 px-1.5 text-[10px] font-semibold text-primary">
                {newsArticles.length}
              </span>
            )}
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {activeSection === 'stories' ? (
            loadingStories ? (
              <div className="flex items-center justify-center gap-2 py-12 text-muted-foreground">
                <Loader2 size={16} className="animate-spin" />
                <span className="text-xs">Finding related stories...</span>
              </div>
            ) : relatedStories.length === 0 ? (
              <div className="py-12 text-center text-xs text-muted-foreground/60 italic">
                No related stories found
              </div>
            ) : (
              <div className="divide-y divide-border">
                {relatedStories.map((s) => (
                  <a
                    key={s.id}
                    href={`/review/${s.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex gap-3 px-4 py-3 transition-colors hover:bg-accent/50 no-underline"
                  >
                    {s.image_url && (
                      <img
                        src={s.image_url}
                        alt=""
                        className="size-14 shrink-0 rounded-md object-cover bg-muted"
                        onError={(e) => { e.target.style.display = 'none'; }}
                      />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="text-[13px] font-medium leading-snug text-foreground line-clamp-2">
                        {s.headline}
                      </p>
                      <div className="mt-1 flex items-center gap-2 text-[10px] text-muted-foreground">
                        {s.reporter_name && <span>{s.reporter_name}</span>}
                        {s.status && (
                          <span className={cn(
                            'rounded-full px-1.5 py-0.5 font-medium capitalize',
                            s.status === 'approved' && 'bg-green-100 text-green-700',
                            s.status === 'published' && 'bg-blue-100 text-blue-700',
                            s.status === 'submitted' && 'bg-yellow-100 text-yellow-700',
                          )}>
                            {s.status}
                          </span>
                        )}
                        {s.location && <span>• {s.location}</span>}
                      </div>
                    </div>
                  </a>
                ))}
              </div>
            )
          ) : (
            loadingNews ? (
              <div className="flex items-center justify-center gap-2 py-12 text-muted-foreground">
                <Loader2 size={16} className="animate-spin" />
                <span className="text-xs">Searching news sources...</span>
              </div>
            ) : newsArticles.length === 0 ? (
              <div className="py-12 text-center text-xs text-muted-foreground/60 italic">
                No related news articles found
              </div>
            ) : (
              <div className="divide-y divide-border">
                {newsArticles.map((a) => (
                  <a
                    key={a.id}
                    href={a.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex gap-3 px-4 py-3 transition-colors hover:bg-accent/50 no-underline"
                  >
                    {a.image_url && (
                      <img
                        src={a.image_url}
                        alt=""
                        className="size-14 shrink-0 rounded-md object-cover bg-muted"
                        onError={(e) => { e.target.style.display = 'none'; }}
                      />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="text-[13px] font-medium leading-snug text-foreground line-clamp-2">
                        {a.title}
                      </p>
                      <div className="mt-1 flex items-center gap-2 text-[10px] text-muted-foreground">
                        {a.source && (
                          <span className="rounded-full bg-primary/10 px-1.5 py-0.5 font-medium text-primary">
                            {a.source}
                          </span>
                        )}
                        <ExternalLink size={9} />
                      </div>
                      {a.description && (
                        <p className="mt-1 text-[11px] leading-snug text-muted-foreground line-clamp-2">
                          {a.description}
                        </p>
                      )}
                    </div>
                  </a>
                ))}
              </div>
            )
          )}
        </div>
      </div>
    </>
  );
}
