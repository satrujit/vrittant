import { useState } from 'react';
import {
  FileText,
  Loader2,
  Mic,
  MicOff,
  Image as ImageIcon,
  Paperclip,
  Play,
  Pause,
  Volume2,
  Sparkles,
  Languages,
  SendHorizonal,
  Download,
  X,
} from 'lucide-react';
import { EditorContent } from '@tiptap/react';
import { useI18n } from '../../i18n';
import RelatedStoriesPanel from './RelatedStoriesPanel';
import ReviewToolbar from './ReviewToolbar';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

/**
 * ReviewEditor — content of the "Editor" tab.
 *
 * Renders the toolbar, the Odia TipTap EditorContent, attachment
 * thumbnails, the selection-tooltip ("Convert to Odia"), the
 * voice/sparkle banners + interim transcription, the typed-instruction
 * bottom bar with mic FAB, and finally the related-stories side panel.
 *
 * Pure view: every callback comes from useReviewState via props.
 */
export default function ReviewEditor({
  // editor
  editor,
  editorContainerRef,
  // toolbar
  odiaKeyboard,
  setOdiaKeyboard,
  handleInsertLink,
  handleRevert,
  // selection tooltip
  selectionTooltip,
  hasSelection,
  convertingSelection,
  voiceMode,
  handleConvertToLocal,
  // word count + media
  wordCount,
  story,
  mediaFiles,
  imageFiles,
  audioFiles,
  docFiles = [],
  imageInputRef,
  uploadingImage,
  handleImageUpload,
  handleAttachmentDelete,
  playingAudio,
  toggleAudioPlay,
  // banner / errors
  sparkleError,
  interimText,
  // bottom bar
  instructionText,
  setInstructionText,
  instructionProcessing,
  handleTypedInstruction,
  voiceSupported,
  handleVoiceFabClick,
  fabIcon,
}) {
  const { t } = useI18n();
  const [dragActive, setDragActive] = useState(false);

  // Forward dropped/pasted files into the same upload pipeline as the
  // file input, by synthesising a minimal `e.target.files` shape.
  const uploadFiles = (fileList) => {
    if (!fileList || fileList.length === 0) return;
    handleImageUpload({ target: { files: fileList } });
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const files = e.dataTransfer?.files;
    if (files && files.length > 0) uploadFiles(files);
  };

  const handleDragOver = (e) => {
    // Required to allow a drop. Browsers cancel the drop if we don't
    // preventDefault here even when the drop handler is wired up.
    e.preventDefault();
    e.stopPropagation();
    if (!dragActive) setDragActive(true);
  };

  const handleDragLeave = (e) => {
    // Only clear when the cursor leaves the wrapper, not when it
    // moves between child elements (relatedTarget is the next element
    // under the cursor).
    if (e.currentTarget.contains(e.relatedTarget)) return;
    setDragActive(false);
  };

  return (
    <>
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-6 py-2">
        {/* Toolbar */}
        <ReviewToolbar
          editor={editor}
          odiaKeyboard={odiaKeyboard}
          setOdiaKeyboard={setOdiaKeyboard}
          handleInsertLink={handleInsertLink}
          handleRevert={handleRevert}
        />

        {/* TipTap Editor */}
        <div className="relative min-h-[200px] flex-1" ref={editorContainerRef}>
          <div
            className={cn(
              'absolute inset-0 overflow-y-auto rounded-b-lg border border-border bg-card focus-within:border-ring focus-within:shadow-[0_0_0_2px_rgba(250,108,56,0.08)]',
              voiceMode === 'dictating' && 'editor-muted',
              voiceMode === 'sparkle-processing' && 'sparkle-processing'
            )}
          >
            <EditorContent editor={editor} />
          </div>

          {/* Selection tooltip — Convert to Odia */}
          {selectionTooltip && hasSelection && !convertingSelection && voiceMode === 'idle' && (
            <div
              className="absolute z-50 flex animate-[vr-slide-down_150ms_ease] items-center gap-1 rounded-lg border border-border bg-card px-1.5 py-1 shadow-lg"
              style={{ top: selectionTooltip.top, left: selectionTooltip.left }}
            >
              <button
                className="flex items-center gap-1.5 whitespace-nowrap rounded-md border-none bg-transparent px-2 py-1 text-xs font-medium text-foreground transition-colors hover:bg-primary/10 hover:text-primary"
                onClick={handleConvertToLocal}
              >
                <Languages size={13} />
                {t('review.convertToOdia', 'ଓଡ଼ିଆକୁ ବଦଳାନ୍ତୁ')}
              </button>
            </div>
          )}
          {convertingSelection && selectionTooltip && (
            <div
              className="absolute z-50 flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 shadow-lg"
              style={{ top: selectionTooltip.top, left: selectionTooltip.left }}
            >
              <Loader2 size={13} className="animate-spin text-primary" />
              <span className="text-xs text-muted-foreground">{t('review.converting', 'Converting...')}</span>
            </div>
          )}
        </div>

        {/* Word count */}
        <div className="flex items-center gap-1 px-1 py-1 text-xs text-muted-foreground">
          <FileText size={12} />
          <span>{wordCount} {t('review.words', 'words')}</span>
        </div>

        {/* Attachments — also a drop target for files dragged from the OS */}
        <div
          className={cn(
            'mt-2 rounded-lg border border-border bg-card p-3 transition-colors',
            dragActive && 'border-primary bg-primary/5'
          )}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragEnter={handleDragOver}
          onDragLeave={handleDragLeave}
        >
          <h4 className="mb-2 flex items-center justify-between text-xs font-semibold text-muted-foreground">
            <span className="flex items-center gap-2">
              <ImageIcon size={14} />
              {mediaFiles.length > 0 ? mediaFiles.length : t('review.attachments', 'Attachments ({count})').replace('{count}', '0')}
            </span>
            <input
              ref={imageInputRef}
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              onChange={handleImageUpload}
            />
            <button
              className="inline-flex items-center gap-1 rounded-md border border-border bg-background px-2 py-0.5 text-xs font-medium text-foreground transition-colors hover:bg-accent disabled:opacity-50"
              onClick={() => imageInputRef.current?.click()}
              disabled={uploadingImage}
            >
              {uploadingImage ? <Loader2 size={10} className="animate-spin" /> : <ImageIcon size={10} />}
              {t('review.uploadImage', 'Upload Image')}
            </button>
          </h4>
          {dragActive && (
            <div className="mb-2 rounded-md border border-dashed border-primary/60 bg-primary/5 px-3 py-2 text-center text-[11px] font-medium text-primary">
              {t('review.dropToUpload', 'Drop images to upload')}
            </div>
          )}
          {imageFiles.length > 0 && (
            <div className="mb-2 grid grid-cols-[repeat(auto-fill,minmax(100px,1fr))] gap-2">
              {imageFiles.map((img, i) => (
                <div key={img.paragraphId || i} className="group relative aspect-[4/3] overflow-hidden rounded-md border border-border bg-background">
                  <img src={img.url} alt={img.name || `Image ${i + 1}`} className="size-full object-cover" onError={(e) => { e.target.style.display = 'none'; }} />
                  {/* Download overlay sits BELOW the remove button. Both are
                      shown on group-hover. Order matters: the link is rendered
                      first so the X button (rendered after, z-20) captures
                      clicks in the corner without the link's `inset-0` hit
                      area swallowing them. */}
                  <a
                    href={img.url}
                    download={img.name || `image-${i + 1}`}
                    target="_blank"
                    rel="noreferrer"
                    className="absolute inset-0 z-10 flex items-center justify-center bg-black/50 opacity-0 transition-opacity group-hover:opacity-100"
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
                  {handleAttachmentDelete && img.paragraphId && (
                    <button
                      type="button"
                      title={t('review.removeAttachment', 'Remove')}
                      aria-label={t('review.removeAttachment', 'Remove')}
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        handleAttachmentDelete(img.paragraphId);
                      }}
                      className="absolute right-1 top-1 z-20 inline-flex size-5 items-center justify-center rounded-full border border-white/40 bg-black/60 text-white opacity-0 transition-opacity hover:bg-red-500 group-hover:opacity-100"
                    >
                      <X size={11} />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
          {docFiles.length > 0 && (
            <div className="mb-2 flex flex-col gap-1">
              {docFiles.map((doc, i) => {
                // Try to derive a friendly filename from the URL when the
                // backend didn't supply one (older WA forwards just store
                // the GCS path with no display name).
                const fallbackName = (() => {
                  try {
                    const u = new URL(doc.url);
                    const last = u.pathname.split('/').pop() || '';
                    return decodeURIComponent(last) || `Document ${i + 1}`;
                  } catch {
                    return `Document ${i + 1}`;
                  }
                })();
                const displayName = doc.name && doc.name !== 'media' ? doc.name : fallbackName;
                return (
                  <div
                    key={doc.paragraphId || i}
                    className="group flex items-center gap-2 rounded-md border border-border bg-background px-2 py-1.5"
                  >
                    <Paperclip size={12} className="shrink-0 text-muted-foreground" />
                    <a
                      href={doc.url}
                      target="_blank"
                      rel="noreferrer"
                      className="min-w-0 flex-1 truncate text-xs text-foreground hover:text-primary hover:underline"
                      title={displayName}
                    >
                      {displayName}
                    </a>
                    <a
                      href={doc.url}
                      download={displayName}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex size-5 shrink-0 items-center justify-center rounded text-muted-foreground hover:bg-accent hover:text-foreground"
                      title={t('review.download', 'Download')}
                    >
                      <Download size={11} />
                    </a>
                    {handleAttachmentDelete && doc.paragraphId && (
                      <button
                        type="button"
                        title={t('review.removeAttachment', 'Remove')}
                        aria-label={t('review.removeAttachment', 'Remove')}
                        onClick={() => handleAttachmentDelete(doc.paragraphId)}
                        className="inline-flex size-5 shrink-0 items-center justify-center rounded-full text-muted-foreground opacity-0 transition-opacity hover:bg-red-500/10 hover:text-red-500 group-hover:opacity-100"
                      >
                        <X size={12} />
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}
          {audioFiles.length > 0 && (
            <div className="flex flex-col gap-1">
              {audioFiles.map((audio, i) => (
                <div key={audio.paragraphId || i} className="group flex items-center gap-2 rounded-md border border-border bg-background px-2 py-1.5">
                  <button className="flex size-6 shrink-0 items-center justify-center rounded-full border-none bg-primary text-primary-foreground transition-colors hover:bg-primary/80" onClick={() => toggleAudioPlay(audio.url)}>
                    {playingAudio === audio.url ? <Pause size={12} /> : <Play size={12} />}
                  </button>
                  <Volume2 size={12} className="shrink-0 text-muted-foreground" />
                  <span className="truncate text-xs text-foreground">{audio.name || `Audio ${i + 1}`}</span>
                  {handleAttachmentDelete && audio.paragraphId && (
                    <button
                      type="button"
                      title={t('review.removeAttachment', 'Remove')}
                      aria-label={t('review.removeAttachment', 'Remove')}
                      onClick={() => handleAttachmentDelete(audio.paragraphId)}
                      className="ml-auto inline-flex size-5 shrink-0 items-center justify-center rounded-full text-muted-foreground opacity-0 transition-opacity hover:bg-red-500/10 hover:text-red-500 group-hover:opacity-100"
                    >
                      <X size={12} />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Sparkle error toast */}
      {sparkleError && (
        <div className="flex shrink-0 animate-[vr-slide-up_150ms_ease] items-center gap-2 border-t border-red-200 px-4 py-2 text-xs font-semibold text-red-500" style={{ background: '#FEE2E2' }}>
          {sparkleError}
        </div>
      )}

      {/* Voice/sparkle indicator banner */}
      {voiceMode === 'dictating' && (
        <div className="flex shrink-0 animate-[vr-slide-up_150ms_ease] items-center gap-2 border-t border-primary/40 bg-primary/10 px-4 py-2 text-xs font-semibold text-primary">
          <span className="size-2 animate-[vr-pulse-fast] rounded-full bg-red-500" />
          {t('review.dictating')}
        </div>
      )}
      {voiceMode === 'sparkle-listening' && (
        <div className="flex shrink-0 animate-[vr-slide-up_150ms_ease] items-center gap-2 border-t border-primary/40 bg-primary/10 px-4 py-2 text-xs font-semibold text-primary">
          <Sparkles size={14} />
          {t('review.sparkleListening')}
        </div>
      )}
      {voiceMode === 'sparkle-processing' && (
        <div className="flex shrink-0 animate-[vr-slide-up_150ms_ease] items-center gap-2 border-t border-primary/40 bg-primary/10 px-4 py-2 text-xs font-semibold text-primary">
          <Loader2 size={14} className="animate-spin" />
          {t('review.sparkleProcessing')}
        </div>
      )}

      {/* Interim transcription */}
      {interimText && (voiceMode === 'dictating' || voiceMode === 'sparkle-listening') && (
        <div className="shrink-0 border-l-[3px] border-l-primary bg-primary/5 px-4 py-1 text-sm font-medium italic text-primary">
          {interimText}
        </div>
      )}

      {/* ── Bottom bar: instruction input + mic ── */}
      <div className="flex shrink-0 items-center gap-2 border-t border-border bg-card px-4 py-2">
        <div className="relative flex flex-1 items-center">
          <input
            type="text"
            className="h-10 w-full rounded-full border border-border bg-background pl-4 pr-10 text-sm text-foreground outline-none placeholder:text-muted-foreground/60 focus:border-primary focus:shadow-[0_0_0_2px_rgba(250,108,56,0.1)]"
            placeholder={hasSelection ? t('review.instructionPlaceholderEdit', 'Type an editing instruction...') : t('review.instructionPlaceholder', 'Type an instruction...')}
            value={instructionText}
            onChange={(e) => setInstructionText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && instructionText.trim()) {
                e.preventDefault();
                handleTypedInstruction();
              }
            }}
            disabled={instructionProcessing || voiceMode !== 'idle'}
          />
          {instructionText.trim() && (
            <button
              className="absolute right-1.5 flex size-7 items-center justify-center rounded-full border-none bg-primary text-primary-foreground transition-all hover:bg-primary/80 disabled:opacity-50"
              onClick={handleTypedInstruction}
              disabled={instructionProcessing}
            >
              {instructionProcessing ? <Loader2 size={14} className="animate-spin" /> : <SendHorizonal size={14} />}
            </button>
          )}
        </div>

        {voiceSupported && (
          <button
            className={cn(
              'flex size-10 shrink-0 items-center justify-center rounded-full border-none bg-primary text-primary-foreground shadow-[0_2px_10px_rgba(250,108,56,0.35)] transition-all hover:scale-110 hover:shadow-[0_4px_16px_rgba(250,108,56,0.5)] disabled:scale-100 disabled:cursor-not-allowed disabled:opacity-50',
              voiceMode === 'dictating' && 'animate-[vr-pulse] bg-red-500 shadow-[0_2px_10px_rgba(239,68,68,0.4)]',
              (hasSelection && voiceMode === 'idle') || voiceMode === 'sparkle-listening'
                ? 'animate-[vr-sparkle-glow] bg-gradient-to-br from-primary to-[#FF8A5C]'
                : ''
            )}
            onClick={handleVoiceFabClick}
            disabled={voiceMode === 'sparkle-processing' || instructionProcessing}
            title={
              voiceMode === 'dictating'
                ? 'Stop'
                : hasSelection
                  ? 'AI Edit'
                  : 'Dictate'
            }
          >
            {fabIcon}
          </button>
        )}
      </div>

      {/* Related stories panel — collapsed by default */}
      <RelatedStoriesPanel storyId={story?.id} headline={story?.headline} />
    </>
  );
}

/** Helper exported so the page can render the FAB icon without depending on lucide here. */
export function getFabIcon(voiceMode, hasSelection) {
  if (voiceMode === 'dictating') return <MicOff size={22} />;
  if (voiceMode === 'sparkle-listening') return <Sparkles size={22} />;
  if (voiceMode === 'sparkle-processing') return <Loader2 size={22} className="animate-spin" />;
  if (hasSelection) return <Sparkles size={22} />;
  return <Mic size={22} />;
}
