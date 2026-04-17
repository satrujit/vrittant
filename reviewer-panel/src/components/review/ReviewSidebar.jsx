import {
  FileText,
  Loader2,
  Image as ImageIcon,
  Play,
  Pause,
  Volume2,
  Sparkles,
  RotateCcw,
  Languages,
  Download,
} from 'lucide-react';
import { EditorContent } from '@tiptap/react';
import { useI18n } from '../../i18n';
import { PageLayoutCanvas, LayoutConfigPanel } from '../PageLayoutPreview';
import SocialTab from './SocialTab';
import { TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';

/**
 * ReviewSidebar — the non-editor tab panes (original / english / layout / social).
 *
 * Despite the name, these tabs render in the same content area as the
 * main editor, not in a literal sidebar. Grouped here to keep the page
 * shell thin; each pane is small enough to live as one block.
 */
export default function ReviewSidebar({
  id,
  story,
  imageFiles,
  audioFiles,
  mediaFiles,
  playingAudio,
  toggleAudioPlay,
  // english
  englishEditor,
  translating,
  handleTranslateToEnglish,
  // layout
  layoutHtml,
  setLayoutHtml,
  layoutGenerating,
  setLayoutGenerating,
  editor,
  headline,
  // social
  socialPosts,
  setSocialPosts,
}) {
  const { t } = useI18n();

  return (
    <>
      {/* ── Original Submission tab ── */}
      <TabsContent value="original" className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
        <div className="rounded-lg border border-border bg-card p-5">
          <h2 className="mb-3 border-b-2 border-border pb-2 text-xl font-bold leading-tight text-foreground">
            {story.headline}
          </h2>
          <div className="text-sm leading-relaxed text-foreground [&_p:last-child]:mb-0 [&_p]:mb-3">
            {story.paragraphs?.map((p, i) => (
              <p key={i}>{p.text}</p>
            ))}
          </div>
          {(imageFiles.length > 0 || audioFiles.length > 0) && (
            <div className="mt-4 rounded-lg border border-border p-3">
              <h4 className="mb-2 flex items-center gap-2 text-xs font-semibold text-muted-foreground">
                <ImageIcon size={14} />
                {mediaFiles.length}
              </h4>
              {imageFiles.length > 0 && (
                <div className="mb-2 grid grid-cols-[repeat(auto-fill,minmax(100px,1fr))] gap-2">
                  {imageFiles.map((img, i) => (
                    <div key={i} className="group relative aspect-[4/3] overflow-hidden rounded-md border border-border bg-background">
                      <img src={img.url} alt={img.name || `Image ${i + 1}`} className="size-full object-cover" onError={(e) => { e.target.style.display = 'none'; }} />
                      <a
                        href={img.url}
                        download={img.name || `image-${i + 1}`}
                        target="_blank"
                        rel="noreferrer"
                        className="absolute inset-0 flex items-center justify-center bg-black/50 opacity-0 transition-opacity group-hover:opacity-100"
                        onClick={async (e) => {
                          e.preventDefault();
                          try {
                            const res = await fetch(img.url);
                            const blob = await res.blob();
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = img.name || `image-${i + 1}.jpg`;
                            document.body.appendChild(a);
                            a.click();
                            a.remove();
                            URL.revokeObjectURL(url);
                          } catch {
                            window.open(img.url, '_blank');
                          }
                        }}
                      >
                        <Download size={20} className="text-white" />
                      </a>
                    </div>
                  ))}
                </div>
              )}
              {audioFiles.length > 0 && (
                <div className="flex flex-col gap-1">
                  {audioFiles.map((audio, i) => (
                    <div key={i} className="flex items-center gap-2 rounded-md border border-border bg-background px-2 py-1.5">
                      <button className="flex size-6 shrink-0 items-center justify-center rounded-full border-none bg-primary text-primary-foreground transition-colors hover:bg-primary/80" onClick={() => toggleAudioPlay(audio.url)}>
                        {playingAudio === audio.url ? <Pause size={12} /> : <Play size={12} />}
                      </button>
                      <Volume2 size={12} className="shrink-0 text-muted-foreground" />
                      <span className="truncate text-xs text-foreground">{audio.name || `Audio ${i + 1}`}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </TabsContent>

      {/* ── English Translation tab (TipTap) ── */}
      <TabsContent value="english" className="flex min-h-0 flex-1 flex-col">
        <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-6 py-4">
          {!englishEditor?.getText()?.trim() && !translating && (
            <div className="flex flex-1 flex-col items-center justify-center gap-3">
              <Languages size={32} className="text-muted-foreground" />
              <Button onClick={handleTranslateToEnglish} className="gap-1.5">
                <Sparkles size={14} />
                {t('review.translateToEnglish')}
              </Button>
            </div>
          )}
          {translating && (
            <div className="flex flex-1 flex-col items-center justify-center gap-3">
              <Loader2 size={24} className="animate-spin text-primary" />
              <p className="text-sm font-medium text-muted-foreground">{t('review.translating')}</p>
            </div>
          )}
          {englishEditor?.getText()?.trim() && !translating && (
            <>
              <div className="mb-2 flex shrink-0 items-center justify-end">
                <Button variant="outline" size="sm" className="h-7 gap-1 px-2 text-xs" onClick={handleTranslateToEnglish}>
                  <RotateCcw size={12} />
                  {t('review.retranslate')}
                </Button>
              </div>
              <div className="min-h-[300px] flex-1 overflow-y-auto rounded-lg border border-border bg-card focus-within:border-ring focus-within:shadow-[0_0_0_2px_rgba(250,108,56,0.08)]">
                <EditorContent editor={englishEditor} />
              </div>
            </>
          )}
        </div>
      </TabsContent>

      {/* ── Page Layout tab ── */}
      <TabsContent value="layout" className="flex min-h-0 flex-1 overflow-hidden">
        <PageLayoutCanvas layoutHtml={layoutHtml} isGenerating={layoutGenerating} />
        <LayoutConfigPanel
          storyId={id}
          layoutHtml={layoutHtml}
          onHtmlChange={setLayoutHtml}
          onLoadingChange={setLayoutGenerating}
          getStoryContent={() => {
            const bodyText = editor ? editor.getText() : '';
            const textParagraphs = bodyText.split('\n\n').filter(Boolean).map((text, i) => ({
              id: `p-${i}`,
              text,
              type: 'paragraph',
            }));

            const storyParas = story?.revision?.paragraphs || story?.paragraphs || [];
            const imageParagraphs = storyParas
              .filter(p => p.type === 'media' || p.type === 'image' || p.image_url || p.media_path)
              .map(p => ({
                id: p.id || `img-${Math.random().toString(36).slice(2)}`,
                text: p.text || p.media_name || '',
                type: p.type || 'image',
                image_url: p.image_url || p.media_path || '',
              }));

            return { headline, paragraphs: [...textParagraphs, ...imageParagraphs] };
          }}
        />
      </TabsContent>

      {/* ── Social Media tab ── */}
      <TabsContent value="social" className="flex min-h-0 flex-1 overflow-hidden">
        <SocialTab story={story} initialPosts={socialPosts} onPostsChange={setSocialPosts} />
      </TabsContent>
    </>
  );
}
