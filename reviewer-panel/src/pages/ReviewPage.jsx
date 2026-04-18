import { useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Loader2, Pencil, FileText, Languages, Share2 } from 'lucide-react';
import { useI18n } from '../i18n';
import { useReviewState } from '../components/review/useReviewState';
import ReviewHeader from '../components/review/ReviewHeader';
import ReviewEditor, { getFabIcon } from '../components/review/ReviewEditor';
import ReviewSidebar from '../components/review/ReviewSidebar';
import AssigneeBar from '../components/review/AssigneeBar';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';

/**
 * ReviewPage — composition-only shell for the editorial review screen.
 *
 * All data + editor state lives in `useReviewState`. The shell renders:
 *   ReviewHeader     — top metadata bar + headline
 *   Tabs             — editor / original / english / social
 *     ReviewEditor   — toolbar + TipTap + voice/sparkle + attachments
 *     ReviewSidebar  — original / english / social tab panes
 *
 * Phase 2.5 split: ReviewPage was 1671 LOC; the body now lives in
 * components/review/. No behavior change — every API call still flows
 * through services/api → services/http.js (Phase 0).
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
  const fabIcon = useMemo(() => getFabIcon(s.voiceMode, s.hasSelection), [s.voiceMode, s.hasSelection]);

  if (s.loading) {
    return (
      <div className="flex h-screen flex-col overflow-hidden">
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
      <div className="flex h-screen flex-col overflow-hidden">
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
    <div className="flex h-screen flex-col overflow-hidden">
      <ReviewHeader
        id={id}
        story={s.story}
        category={s.category}
        setCategory={s.setCategory}
        status={s.status}
        priority={s.priority}
        setPriority={s.setPriority}
        headline={s.headline}
        setHeadline={s.setHeadline}
        saving={s.saving}
        approveOpen={s.approveOpen}
        setApproveOpen={s.setApproveOpen}
        rejectOpen={s.rejectOpen}
        setRejectOpen={s.setRejectOpen}
        rejectReason={s.rejectReason}
        setRejectReason={s.setRejectReason}
        handleApprove={s.handleApprove}
        handleReject={s.handleReject}
        handleSaveContent={s.handleSaveContent}
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

      <AssigneeBar storyId={id} story={s.story} setStory={s.setStory} />

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
            imageInputRef={s.imageInputRef}
            uploadingImage={s.uploadingImage}
            handleImageUpload={s.handleImageUpload}
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
  );
}

export default ReviewPage;
