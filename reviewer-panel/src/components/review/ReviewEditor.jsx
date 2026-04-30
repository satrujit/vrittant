import { useState, useEffect } from 'react';
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
  ChevronLeft,
  ChevronRight,
  X,
} from 'lucide-react';
import { EditorContent } from '@tiptap/react';
import { useI18n } from '../../i18n';
import RelatedStoriesPanel from './RelatedStoriesPanel';
import ReviewToolbar from './ReviewToolbar';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { getFontSizePref } from '../../utils/fontSizePreference';

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
  handleRefineStory,
  refining,
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
  // #55 — read the user's saved "comfortable size" pref once on mount and
  // apply it as a CSS font-size on the editor wrapper. Cascades through the
  // ProseMirror tree so paragraphs without an inline style="font-size: ..."
  // pick it up; spans that DO carry an inline style still win via specificity.
  // Read once (state) so toggling the dropdown updates immediately for the
  // current story without forcing a remount of the EditorContent.
  const [fontSizePref, setFontSizePrefState] = useState(() => getFontSizePref());
  useEffect(() => {
    // Re-sync from localStorage on focus so a change made in another tab
    // (rare but cheap to support) doesn't leave the editor stuck on the
    // old size until reload.
    const onFocus = () => setFontSizePrefState(getFontSizePref());
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, []);
  // Also re-read after every render of the toolbar's onChange — that
  // handler writes via setFontSizePref() but doesn't bubble up. Polling
  // on the editor's transaction is overkill; instead listen to the storage
  // event AND fall back to a cheap re-read whenever the editor selection
  // updates (which fires on every dropdown change because the toolbar
  // calls editor.chain().focus()...).
  useEffect(() => {
    if (!editor) return;
    const onUpdate = () => {
      const next = getFontSizePref();
      if (next !== fontSizePref) setFontSizePrefState(next);
    };
    editor.on('selectionUpdate', onUpdate);
    return () => editor.off('selectionUpdate', onUpdate);
  }, [editor, fontSizePref]);
  // #53 — lightbox preview state. Holds the index into imageFiles of the
  // currently open photo (null when closed). Indexed (not URL) so the
  // ←/→ arrows can walk through the attachment grid without re-deriving
  // position from the URL on each press.
  const [previewIdx, setPreviewIdx] = useState(null);
  const closePreview = () => setPreviewIdx(null);
  const previewImage = previewIdx != null ? imageFiles[previewIdx] : null;
  const showPrev = () => {
    if (previewIdx == null || imageFiles.length === 0) return;
    setPreviewIdx((i) => (i - 1 + imageFiles.length) % imageFiles.length);
  };
  const showNext = () => {
    if (previewIdx == null || imageFiles.length === 0) return;
    setPreviewIdx((i) => (i + 1) % imageFiles.length);
  };
  // Keyboard nav: Esc to close, ←/→ to step. Only wired while a preview
  // is open so it doesn't fight the editor's own arrow handling.
  useEffect(() => {
    if (previewIdx == null) return;
    const onKey = (e) => {
      if (e.key === 'Escape') closePreview();
      else if (e.key === 'ArrowLeft') showPrev();
      else if (e.key === 'ArrowRight') showNext();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [previewIdx, imageFiles.length]);

  // Force-download a photo via blob fetch so the browser doesn't just
  // navigate to it (GCS serves photos with inline content-disposition).
  const downloadImage = async (img, fallbackIndex) => {
    try {
      const res = await fetch(img.url);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = img.name || `image-${fallbackIndex + 1}.jpg`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      window.open(img.url, '_blank');
    }
  };

  // Forward dropped/pasted files into the same upload pipeline as the
  // file input, by synthesising a minimal `e.target.files` shape.
  const uploadFiles = (fileList) => {
    if (!fileList || fileList.length === 0) return;
    handleImageUpload({ target: { files: fileList } });
  };

  // True only for OS file drags. Internal text-selection drags within
  // the editor have type "text/plain" / "text/html" and we ignore them
  // (otherwise the upload overlay would flicker on every text drag).
  const isFileDrag = (e) => {
    const types = e.dataTransfer?.types;
    if (!types) return false;
    // DataTransferItemList exposes .contains in some browsers and array
    // semantics in others; check both.
    for (let i = 0; i < types.length; i++) {
      if (types[i] === 'Files') return true;
    }
    return false;
  };

  const handleDrop = (e) => {
    if (!isFileDrag(e)) return;
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const files = e.dataTransfer?.files;
    if (files && files.length > 0) uploadFiles(files);
  };

  const handleDragOver = (e) => {
    if (!isFileDrag(e)) return;
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
      <div
        className="relative flex min-h-0 flex-1 flex-col overflow-y-auto px-6 py-2"
        // Capture-phase handlers so we intercept file drops before
        // ProseMirror's own drop handler (which would otherwise try to
        // insert the file as an image node and bypass our upload pipeline).
        onDropCapture={handleDrop}
        onDragOverCapture={handleDragOver}
        onDragEnterCapture={handleDragOver}
        onDragLeave={handleDragLeave}
      >
        {/* Full-area drop overlay — sits above the editor + attachments
            so reporters can drop image files anywhere in the editor pane,
            not just the tiny attachments box at the bottom. */}
        {dragActive && (
          <div className="pointer-events-none absolute inset-2 z-40 flex items-center justify-center rounded-lg border-2 border-dashed border-primary bg-primary/10 backdrop-blur-[1px]">
            <div className="flex items-center gap-2 rounded-md bg-card px-4 py-2 text-sm font-semibold text-primary shadow-lg">
              <Paperclip size={16} />
              {t('review.dropToUpload', 'Drop files to attach')}
            </div>
          </div>
        )}

        {/* Toolbar */}
        <ReviewToolbar
          editor={editor}
          odiaKeyboard={odiaKeyboard}
          setOdiaKeyboard={setOdiaKeyboard}
          handleInsertLink={handleInsertLink}
          handleRevert={handleRevert}
          handleRefineStory={handleRefineStory}
          refining={refining}
        />

        {/* TipTap Editor */}
        <div className="relative min-h-[200px] flex-1" ref={editorContainerRef}>
          <div
            className={cn(
              'absolute inset-0 overflow-y-auto rounded-b-lg border border-border bg-card focus-within:border-ring focus-within:shadow-[0_0_0_2px_rgba(250,108,56,0.08)]',
              voiceMode === 'dictating' && 'editor-muted',
              voiceMode === 'sparkle-processing' && 'sparkle-processing'
            )}
            // #55 — apply the saved per-user base size here so it cascades
            // into every paragraph that doesn't carry an inline override.
            style={fontSizePref ? { fontSize: fontSizePref } : undefined}
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

        {/* Attachments — drop target is now the entire editor pane (see
            outer wrapper above), so we don't double-up the visual hint
            here. The box still shows the upload button + thumbnails. */}
        <div className="mt-2 rounded-lg border border-border bg-card p-3">
          <h4 className="mb-2 flex items-center justify-between text-xs font-semibold text-muted-foreground">
            <span className="flex items-center gap-2">
              <ImageIcon size={14} />
              {mediaFiles.length > 0 ? mediaFiles.length : t('review.attachments', 'Attachments ({count})').replace('{count}', '0')}
            </span>
            {/* #44 — accept document types alongside images. The backend
                /upload-image endpoint discriminates by extension and stores
                photo/document accordingly, so the same handler covers both. */}
            <input
              ref={imageInputRef}
              type="file"
              accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.rtf"
              multiple
              className="hidden"
              onChange={handleImageUpload}
            />
            <button
              className="inline-flex items-center gap-1 rounded-md border border-border bg-background px-2 py-0.5 text-xs font-medium text-foreground transition-colors hover:bg-accent disabled:opacity-50"
              onClick={() => imageInputRef.current?.click()}
              disabled={uploadingImage}
            >
              {uploadingImage ? <Loader2 size={10} className="animate-spin" /> : <Paperclip size={10} />}
              {t('review.attach', 'Attach')}
            </button>
          </h4>
          {/* Cap the combined attachment region so a long photo grid or a
              dozen audio clips can't push the editor body off-screen. The
              header (upload button + count) stays pinned above; only the
              lists below scroll. 192px ≈ two rows of 80px thumbs — enough
              to see what's there at a glance without dominating the pane. */}
          <div className="max-h-48 overflow-y-auto pr-1">
          {imageFiles.length > 0 && (
            <div className="mb-2 grid grid-cols-[repeat(auto-fill,minmax(80px,1fr))] gap-1.5">
              {imageFiles.map((img, i) => (
                <div key={img.paragraphId || i} className="group relative aspect-[4/3] overflow-hidden rounded-md border border-border bg-background">
                  <img src={img.url} alt={img.name || `Image ${i + 1}`} className="size-full object-cover" onError={(e) => { e.target.style.display = 'none'; }} />
                  {/* #53 — Click the image to open a fullscreen lightbox
                      (was: click downloads). Download moved to its own
                      icon button next to X so reporters can still grab a
                      copy without waiting on the preview. The button
                      overlay sits BELOW the corner controls (z-10 vs z-30)
                      and is clipped away from the corners so the controls
                      stay clickable. */}
                  <button
                    type="button"
                    aria-label={t('review.previewImage', 'Preview image')}
                    title={t('review.previewImage', 'Preview image')}
                    className="absolute inset-0 z-10 flex cursor-zoom-in items-center justify-center border-none bg-black/50 opacity-0 transition-opacity group-hover:opacity-100"
                    style={{ clipPath: 'polygon(0 0, calc(100% - 60px) 0, calc(100% - 60px) 28px, 100% 28px, 100% 100%, 0 100%)' }}
                    onClick={() => setPreviewIdx(i)}
                  >
                    <ImageIcon size={20} className="text-white" />
                  </button>
                  <button
                    type="button"
                    title={t('review.download', 'Download')}
                    aria-label={t('review.download', 'Download')}
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      downloadImage(img, i);
                    }}
                    className="absolute right-8 top-1 z-30 inline-flex size-6 cursor-pointer items-center justify-center rounded-full border border-white/40 bg-black/70 text-white shadow-md transition-colors hover:bg-primary"
                  >
                    <Download size={12} />
                  </button>
                  {handleAttachmentDelete && img.paragraphId && (
                    <button
                      type="button"
                      title={t('review.removeAttachment', 'Remove')}
                      aria-label={t('review.removeAttachment', 'Remove')}
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        if (window.confirm(t('review.removeAttachmentConfirm', 'Remove this image?'))) {
                          handleAttachmentDelete(img.paragraphId);
                        }
                      }}
                      className="absolute right-1 top-1 z-30 inline-flex size-6 cursor-pointer items-center justify-center rounded-full border border-white/40 bg-black/70 text-white shadow-md transition-colors hover:bg-red-500"
                    >
                      <X size={12} />
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
            data-shortcut-target="instruction"
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

      {/* #53 — Image preview lightbox. Renders inline (no portal) since
          the editor pane already establishes a high-stacking context;
          z-[100] keeps it above the bottom-bar FAB. Backdrop click
          closes; ←/→/Esc handled by the keydown effect above. */}
      {previewImage && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/85 p-4"
          onClick={closePreview}
          role="dialog"
          aria-modal="true"
          aria-label={t('review.previewImage', 'Preview image')}
        >
          <button
            type="button"
            title={t('common.close', 'Close')}
            aria-label={t('common.close', 'Close')}
            className="absolute right-4 top-4 inline-flex size-10 items-center justify-center rounded-full border border-white/30 bg-black/60 text-white transition-colors hover:bg-red-500"
            onClick={(e) => { e.stopPropagation(); closePreview(); }}
          >
            <X size={20} />
          </button>
          <a
            href={previewImage.url}
            target="_blank"
            rel="noreferrer"
            title={t('review.download', 'Download')}
            aria-label={t('review.download', 'Download')}
            className="absolute right-16 top-4 inline-flex size-10 items-center justify-center rounded-full border border-white/30 bg-black/60 text-white transition-colors hover:bg-primary"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              downloadImage(previewImage, previewIdx);
            }}
          >
            <Download size={18} />
          </a>
          {imageFiles.length > 1 && (
            <>
              <button
                type="button"
                title={t('common.previous', 'Previous')}
                aria-label={t('common.previous', 'Previous')}
                className="absolute left-4 top-1/2 inline-flex size-12 -translate-y-1/2 items-center justify-center rounded-full border border-white/30 bg-black/60 text-white transition-colors hover:bg-primary"
                onClick={(e) => { e.stopPropagation(); showPrev(); }}
              >
                <ChevronLeft size={24} />
              </button>
              <button
                type="button"
                title={t('common.next', 'Next')}
                aria-label={t('common.next', 'Next')}
                className="absolute right-4 top-1/2 inline-flex size-12 -translate-y-1/2 items-center justify-center rounded-full border border-white/30 bg-black/60 text-white transition-colors hover:bg-primary"
                onClick={(e) => { e.stopPropagation(); showNext(); }}
              >
                <ChevronRight size={24} />
              </button>
            </>
          )}
          <img
            src={previewImage.url}
            alt={previewImage.name || `Image ${previewIdx + 1}`}
            className="max-h-full max-w-full select-none object-contain shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          />
          {(previewImage.name || imageFiles.length > 1) && (
            <div
              className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-md bg-black/60 px-3 py-1 text-xs font-medium text-white"
              onClick={(e) => e.stopPropagation()}
            >
              {previewImage.name ? `${previewImage.name}` : ''}
              {previewImage.name && imageFiles.length > 1 ? ' · ' : ''}
              {imageFiles.length > 1 ? `${previewIdx + 1} / ${imageFiles.length}` : ''}
            </div>
          )}
        </div>
      )}
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
