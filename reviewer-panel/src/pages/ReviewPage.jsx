import { useMemo, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Loader2, Pencil, FileText, Languages, Share2 } from 'lucide-react';
import { useI18n } from '../i18n';
import { useReviewState } from '../components/review/useReviewState';
import ReviewHeader from '../components/review/ReviewHeader';
import ReviewEditor, { getFabIcon } from '../components/review/ReviewEditor';
import ReviewSidebar from '../components/review/ReviewSidebar';
import ReviewSidePanel from '../components/review/ReviewSidePanel';
import ShortcutsHelpOverlay from '../components/review/ShortcutsHelpOverlay';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';

/**
 * ReviewPage — composition-only shell for the editorial review screen.
 *
 * Layout: minimalist top bar (back + reporter + headline + actions), left
 * main column with tabbed editor/translation/social, fixed right panel
 * with all settings (status, category, priority, location, source, edition,
 * assignee) plus a per-story comment thread.
 *
 * All data + editor state lives in `useReviewState`.
 */
function ReviewPage() {
  const { t } = useI18n();
  const { id } = useParams();
  const navigate = useNavigate();
  const s = useReviewState({ id, t });

  // Derived view-model (cheap; computed from story on every render)
  const mediaFiles = s.story?.mediaFiles || [];
  const audioFiles = mediaFiles.filter((m) => m.type === 'audio' || m.url?.match(/\.(mp3|wav|m4a|ogg|aac)$/i));
  const imageFiles = mediaFiles.filter((m) => m.type === 'photo' || m.type === 'image' || m.url?.match(/\.(jpg|jpeg|png|gif|webp)$/i));
  // Anything that isn't an image or audio is rendered as a generic
  // "document" attachment — DOCX/PDF/PPT forwarded from WhatsApp end up
  // here. Keeping the bucket separate from images means the photo grid
  // doesn't try to render a thumbnail for a PDF.
  const docFiles = mediaFiles.filter((m) => !imageFiles.includes(m) && !audioFiles.includes(m));
  const fabIcon = useMemo(() => getFabIcon(s.voiceMode, s.hasSelection), [s.voiceMode, s.hasSelection]);

  // Cmd/Ctrl+S → save the article. Suppress the browser's "save page"
  // dialog so the shortcut belongs to us. Undo/redo (Cmd/Ctrl+Z, Shift+Z)
  // are handled inside the TipTap editor by StarterKit's history
  // extension — no global hook needed for those.
  useEffect(() => {
    const onKeyDown = (e) => {
      const meta = e.metaKey || e.ctrlKey;
      if (!meta) return;
      const k = e.key.toLowerCase();
      if (k === 's') {
        e.preventDefault();
        if (!s.saving) {
          s.handleSaveContent();
        }
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [s.handleSaveContent, s.saving]);

  // ── Section-jump shortcuts (Alt/Option + letter) ─────────────────────
  // Combo modifier chosen because:
  //   • Alt avoids the most common single-key conflicts inside TipTap.
  //   • Plain letters (h/b/i/c/r) would fire while typing in the body
  //     editor; Alt-combos pass through cleanly.
  //   • Cmd/Ctrl letters collide with browser/system shortcuts (Cmd+S
  //     save, Cmd+T new tab, Cmd+R reload, etc.); Alt is mostly free.
  // Alt+/ toggles the help overlay; the overlay lists every binding.
  const [helpOpen, setHelpOpen] = useState(false);

  useEffect(() => {
    const focusBy = (selector) => {
      const el = document.querySelector(selector);
      if (!el) return;
      el.focus();
      // For text inputs/textareas, also place caret at end so the user can
      // start typing immediately without re-clicking.
      if (typeof el.setSelectionRange === 'function') {
        const len = el.value?.length ?? 0;
        try { el.setSelectionRange(len, len); } catch { /* not all inputs support selection */ }
      }
    };

    const onKeyDown = (e) => {
      // Alt is the gate — never fire on bare letters.
      if (!e.altKey) return;
      // Don't ride along with Cmd/Ctrl/Shift combos. Browsers and editors
      // bind a lot of those (e.g. ⌥⌘I = devtools); we want clean Alt-only.
      if (e.metaKey || e.ctrlKey || e.shiftKey) return;

      // CRITICAL: use `e.code`, NOT `e.key`. On macOS, holding Option
      // produces special characters — Option+H = "˙", Option+B = "∫",
      // Option+/ = "÷" — so `e.key` no longer matches plain letters.
      // `e.code` is the physical key identifier ("KeyH", "Slash", etc.)
      // and is stable across all modifier states.
      const code = e.code;

      // Alt+/ → toggle the help overlay.
      if (code === 'Slash') {
        e.preventDefault();
        setHelpOpen((v) => !v);
        return;
      }

      switch (code) {
        case 'KeyH':
          e.preventDefault();
          focusBy('[data-shortcut-target="headline"]');
          break;
        case 'KeyB':
          e.preventDefault();
          // Body = TipTap. Use the editor's own focus command so the caret
          // lands at the last known position instead of bouncing to start.
          s.editor?.commands.focus();
          break;
        case 'KeyI':
          e.preventDefault();
          focusBy('[data-shortcut-target="instruction"]');
          break;
        case 'KeyC':
          e.preventDefault();
          focusBy('[data-shortcut-target="comment"]');
          break;
        case 'KeyR':
          e.preventDefault();
          if (!s.refining) s.handleRefineStory?.();
          break;
        case 'KeyE':
          e.preventDefault();
          s.setActiveTab('editor');
          break;
        case 'KeyO':
          e.preventDefault();
          s.setActiveTab('original');
          break;
        case 'KeyT':
          e.preventDefault();
          s.setActiveTab('english');
          break;
        default:
          break;
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [s.editor, s.handleRefineStory, s.refining, s.setActiveTab]);

  // Esc behaviour — keyboard-only reviewers need a reliable path off the
  // page even after using a TipTap shortcut (Option+B / Cmd+B etc.) that
  // parks focus inside the editor's contenteditable.
  //
  //   - INPUT / TEXTAREA / SELECT (search bar, date filter, etc.): ignored.
  //     Esc in those is the browser's native "clear / cancel" affordance
  //     and we don't want to navigate away mid-search.
  //   - contenteditable (the TipTap editor surface): blur it. The editor
  //     deselects so a second Esc — now targeting <body> — will navigate.
  //     This matches the IDE / Vim "first Esc leaves the mode, next one
  //     leaves the file" pattern reviewers already expect.
  //   - everything else: navigate back.
  //
  // Open Radix dialogs / popovers handle Esc themselves; we bail when one
  // is open so we don't double-handle.
  useEffect(() => {
    const onKeyDown = (e) => {
      if (e.key !== 'Escape') return;
      if (document.querySelector('[data-state="open"][role="dialog"]')) return;

      const el = e.target;
      const tag = el?.tagName;

      // Plain text-input fields keep their native Esc behaviour.
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

      // TipTap (and any other contenteditable) — first Esc blurs so the
      // user gets a visible "I've left the editor" cue. Second Esc lands
      // on <body> and falls through to the navigate branch below.
      if (el?.isContentEditable) {
        e.preventDefault();
        try { el.blur(); } catch { /* defensive — element may have been
          unmounted between the keydown firing and blur landing. */ }
        return;
      }

      e.preventDefault();
      navigate(-1);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [navigate]);

  // /review/new — pre-save shell. The story isn't in the DB yet, so the
  // side panel's settings (assignee, edition, comments) and the header's
  // status actions (approve/reject) don't apply. Hide them; just show
  // the editor + Save.
  const isNew = id === 'new';

  if (s.loading) {
    return (
      <div className="flex h-full flex-col overflow-hidden">
        <div className="flex items-center gap-2 border-b border-border bg-card px-6 py-2">
          <Button variant="outline" size="icon" className="size-8" onClick={() => navigate(-1)}>
            <ArrowLeft size={16} />
          </Button>
        </div>
        <div className="flex flex-1 items-center justify-center">
          <Loader2 size={24} className="animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  if (!s.story) {
    return (
      <div className="flex h-full flex-col overflow-hidden">
        <div className="flex items-center gap-2 border-b border-border bg-card px-6 py-2">
          <Button variant="outline" size="icon" className="size-8" onClick={() => navigate(-1)}>
            <ArrowLeft size={16} />
          </Button>
        </div>
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
          {t('dashboard.noReports')}
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full overflow-hidden">
      {/* ── Main column ── */}
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <ReviewHeader
          story={s.story}
          status={s.status}
          headline={s.headline}
          setHeadline={s.setHeadline}
          saving={s.saving}
          lastSavedAt={s.lastSavedAt}
          saveError={s.saveError}
          approveOpen={s.approveOpen}
          setApproveOpen={s.setApproveOpen}
          rejectOpen={s.rejectOpen}
          setRejectOpen={s.setRejectOpen}
          rejectReason={s.rejectReason}
          setRejectReason={s.setRejectReason}
          handleApprove={s.handleApprove}
          handleReject={s.handleReject}
          handleStatusChange={s.handleStatusChange}
          handleSaveContent={s.handleSaveContent}
          isNew={isNew}
        />

        <Tabs value={s.activeTab} onValueChange={s.setActiveTab} className="flex min-h-0 flex-1 flex-col">
          <div className="shrink-0 border-b border-border bg-background px-6">
            <TabsList variant="line" className="w-full justify-start">
              <TabsTrigger value="editor"><Pencil size={14} /> {t('review.tabs.editor')}</TabsTrigger>
              <TabsTrigger value="original"><FileText size={14} /> {t('review.tabs.original')}</TabsTrigger>
              <TabsTrigger value="english"><Languages size={14} /> {t('review.tabs.english')}</TabsTrigger>
              <TabsTrigger value="social"><Share2 size={14} /> {t('review.tabs.social')}</TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value="editor" className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
            <ReviewEditor
              editor={s.editor}
              editorContainerRef={s.editorContainerRef}
              odiaKeyboard={s.odiaKeyboard}
              setOdiaKeyboard={s.setOdiaKeyboard}
              handleInsertLink={s.handleInsertLink}
              handleRevert={s.handleRevert}
              handleRefineStory={s.handleRefineStory}
              refining={s.refining}
              selectionTooltip={s.selectionTooltip}
              hasSelection={s.hasSelection}
              convertingSelection={s.convertingSelection}
              voiceMode={s.voiceMode}
              handleConvertToLocal={s.handleConvertToLocal}
              wordCount={s.wordCount}
              story={s.story}
              mediaFiles={mediaFiles}
              imageFiles={imageFiles}
              audioFiles={audioFiles}
              docFiles={docFiles}
              imageInputRef={s.imageInputRef}
              uploadingImage={s.uploadingImage}
              handleImageUpload={s.handleImageUpload}
              handleAttachmentDelete={s.handleAttachmentDelete}
              playingAudio={s.playingAudio}
              toggleAudioPlay={s.toggleAudioPlay}
              sparkleError={s.sparkleError}
              interimText={s.interimText}
              instructionText={s.instructionText}
              setInstructionText={s.setInstructionText}
              instructionProcessing={s.instructionProcessing}
              handleTypedInstruction={s.handleTypedInstruction}
              voiceSupported={s.voiceSupported}
              handleVoiceFabClick={s.handleVoiceFabClick}
              fabIcon={fabIcon}
            />
          </TabsContent>

          <ReviewSidebar
            id={id}
            story={s.story}
            imageFiles={imageFiles}
            audioFiles={audioFiles}
            mediaFiles={mediaFiles}
            playingAudio={s.playingAudio}
            toggleAudioPlay={s.toggleAudioPlay}
            englishEditor={s.englishEditor}
            translating={s.translating}
            handleTranslateToEnglish={s.handleTranslateToEnglish}
            editor={s.editor}
            headline={s.headline}
            socialPosts={s.socialPosts}
            setSocialPosts={s.setSocialPosts}
          />
        </Tabs>
      </div>

      {/* ── Right side panel: settings + assignee + comments ── */}
      {/* Hidden in /review/new — settings/assignee/comments don't apply
          before the story exists. They mount on the next render after
          handleSaveContent navigates to /review/<actual-id>. */}
      {!isNew && (
      <ReviewSidePanel
        id={id}
        story={s.story}
        setStory={s.setStory}
        category={s.category}
        setCategory={s.setCategory}
        status={s.status}
        priority={s.priority}
        setPriority={s.setPriority}
        editions={s.editions}
        selectedEdition={s.selectedEdition}
        setSelectedEdition={s.setSelectedEdition}
        selectedPage={s.selectedPage}
        setSelectedPage={s.setSelectedPage}
        editionPages={s.editionPages}
        assigningToEdition={s.assigningToEdition}
        editionAssignments={s.editionAssignments}
        handleAssignToEdition={s.handleAssignToEdition}
        handleRemoveFromEdition={s.handleRemoveFromEdition}
      />
      )}

      <ShortcutsHelpOverlay open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  );
}

export default ReviewPage;
