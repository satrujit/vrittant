import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { useEditor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import LinkExt from '@tiptap/extension-link';
import UnderlineExt from '@tiptap/extension-underline';
import { TextStyle } from '@tiptap/extension-text-style';
import FontFamily from '@tiptap/extension-font-family';
import TextAlign from '@tiptap/extension-text-align';
import Placeholder from '@tiptap/extension-placeholder';
import { Table } from '@tiptap/extension-table';
import { TableRow } from '@tiptap/extension-table-row';
import { TableCell } from '@tiptap/extension-table-cell';
import { TableHeader } from '@tiptap/extension-table-header';
import TranscriptionMark from '../../extensions/TranscriptionMark';
import ExternalInputCompat from '../../extensions/ExternalInputCompat';
import { createShreeLipiKeyboard } from '../../extensions/ShreeLipiKeyboard';
import {
  fetchStory,
  updateStoryStatus,
  updateStory,
  transformStory,
  llmChat,
  getSTTWebSocketUrl,
  fetchEditions,
  fetchEdition,
  addStoryToPage,
  removeStoryFromPage,
  uploadStoryImage,
} from '../../services/api';

/**
 * useReviewState — owns all data + editor state for ReviewPage.
 *
 * Returns a flat object the page destructures and prop-drills to its
 * region components. Kept as a single hook (no Context) so the
 * data-flow stays explicit; if prop-drilling becomes painful in
 * the future, switch to a ReviewContext at this boundary.
 */
export function useReviewState({ id, t }) {
  // API data state
  const [story, setStory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Editable state
  const [headline, setHeadline] = useState('');
  const [status, setStatus] = useState('submitted');
  const [showStatusDropdown, setShowStatusDropdown] = useState(false);

  // Tab & layout state
  const [activeTab, setActiveTab] = useState('editor');
  const [layoutHtml, setLayoutHtml] = useState('');
  const [layoutGenerating, setLayoutGenerating] = useState(false);

  // Confirmation popovers
  const [approveOpen, setApproveOpen] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  // Editable metadata
  const [priority, setPriority] = useState('normal');
  const [category, setCategory] = useState(null);

  // English translation tab
  const [englishTranslation, setEnglishTranslation] = useState('');
  const [translating, setTranslating] = useState(false);

  // Social posts
  const [socialPosts, setSocialPosts] = useState(null);

  // Edition assignment
  const [editions, setEditions] = useState([]);
  const [selectedEdition, setSelectedEdition] = useState(null);
  const [selectedPage, setSelectedPage] = useState(null);
  const [editionPages, setEditionPages] = useState([]);
  const [assigningToEdition, setAssigningToEdition] = useState(false);
  const [editionAssignments, setEditionAssignments] = useState([]);

  // Voice / sparkle state machine
  const [voiceMode, setVoiceMode] = useState('idle');
  const [hasSelection, setHasSelection] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(false);
  const [interimText, setInterimText] = useState('');
  const [sparkleError, setSparkleError] = useState(null);
  const wsRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const audioContextRef = useRef(null);
  const processorRef = useRef(null);
  const pcmBufferRef = useRef([]);
  const sendTimerRef = useRef(null);

  // Selection tooltip state
  const [selectionTooltip, setSelectionTooltip] = useState(null);
  const [convertingSelection, setConvertingSelection] = useState(false);
  const editorContainerRef = useRef(null);

  // Instruction text input (typed sparkle)
  const [instructionText, setInstructionText] = useState('');
  const [instructionProcessing, setInstructionProcessing] = useState(false);

  // Audio playback state
  const [playingAudio, setPlayingAudio] = useState(null);
  const audioRef = useRef(null);

  // Image upload state
  const [uploadingImage, setUploadingImage] = useState(false);
  const imageInputRef = useRef(null);

  // Odia keyboard (Shree-Lipi layout) toggle — ON by default
  const [odiaKeyboard, setOdiaKeyboard] = useState(true);
  const odiaKeyboardRef = useRef(true);
  useEffect(() => { odiaKeyboardRef.current = odiaKeyboard; }, [odiaKeyboard]);

  // Keyboard shortcut: Ctrl+Space to toggle Odia/English
  useEffect(() => {
    const handler = (e) => {
      if (e.ctrlKey && e.code === 'Space') {
        e.preventDefault();
        setOdiaKeyboard((v) => !v);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  // Check for microphone support
  useEffect(() => {
    if (navigator.mediaDevices?.getUserMedia) {
      setVoiceSupported(true);
    }
  }, []);

  // TipTap editor (Odia article)
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
      }),
      LinkExt.configure({ openOnClick: false, HTMLAttributes: { class: 'tiptap-link' } }),
      UnderlineExt.configure({ HTMLAttributes: {} }),
      TextStyle,
      FontFamily,
      TextAlign.configure({ types: ['heading', 'paragraph'] }),
      Placeholder.configure({ placeholder: t('review.editorPlaceholder') || 'Start writing...' }),
      Table.configure({ resizable: false }),
      TableRow,
      TableCell,
      TableHeader,
      TranscriptionMark,
      ExternalInputCompat,
      createShreeLipiKeyboard(() => odiaKeyboardRef.current),
    ],
    content: '',
  });

  // TipTap editor (English translation)
  const englishEditor = useEditor({
    extensions: [
      StarterKit.configure({ heading: { levels: [1, 2] } }),
      LinkExt.configure({ openOnClick: false }),
      UnderlineExt,
      TextAlign.configure({ types: ['heading', 'paragraph'] }),
      Placeholder.configure({ placeholder: 'English translation will appear here...' }),
      ExternalInputCompat,
    ],
    content: '',
    onUpdate: ({ editor: ed }) => {
      setEnglishTranslation(ed.getHTML());
    },
  });

  // Track selection state for sparkle mode + show tooltip
  useEffect(() => {
    if (!editor) return;
    const handleSelectionUpdate = () => {
      const { from, to } = editor.state.selection;
      const hasSel = from !== to;
      setHasSelection(hasSel);
      if (hasSel && editorContainerRef.current) {
        const coords = editor.view.coordsAtPos(from);
        const containerRect = editorContainerRef.current.getBoundingClientRect();
        setSelectionTooltip({
          top: coords.top - containerRect.top - 40,
          left: Math.min(
            Math.max(coords.left - containerRect.left, 8),
            containerRect.width - 180
          ),
        });
      } else {
        setSelectionTooltip(null);
      }
    };
    editor.on('selectionUpdate', handleSelectionUpdate);
    return () => {
      editor.off('selectionUpdate', handleSelectionUpdate);
    };
  }, [editor]);

  // Fetch story on mount
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchStory(id)
      .then((data) => {
        if (!cancelled) {
          const transformed = transformStory(data);
          setStory(transformed);
          setStatus(transformed?.status || 'submitted');
          setPriority(transformed?.priority || 'normal');
          setCategory(transformed?.category || null);

          const rev = transformed?.revision;
          const activeHeadline = rev ? rev.headline : (transformed?.headline || '');
          const activeParagraphs = rev ? rev.paragraphs : (transformed?.paragraphs || []);

          setHeadline(activeHeadline);

          if (editor && activeParagraphs.length > 0) {
            const html = activeParagraphs
              .map((p) => `<p>${(p.text || '').replace(/\n/g, '<br>')}</p>`)
              .join('');
            editor.commands.setContent(html);
          }

          if (rev && rev.layout_config && rev.layout_config.html) {
            setLayoutHtml(rev.layout_config.html);
          }

          if (rev && rev.english_translation) {
            setEnglishTranslation(rev.english_translation);
            if (englishEditor) {
              const html = rev.english_translation.startsWith('<')
                ? rev.english_translation
                : rev.english_translation.split('\n\n').map(p => `<p>${p}</p>`).join('');
              englishEditor.commands.setContent(html);
            }
          }

          if (rev && rev.social_posts) {
            setSocialPosts(rev.social_posts);
          }

          if (data.edition_info && data.edition_info.length > 0) {
            setEditionAssignments(data.edition_info);
          }

          setLoading(false);
        }
      })
      .catch((err) => {
        console.error('Failed to fetch story:', err);
        if (!cancelled) {
          setStory(null);
          setLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, [id, editor, englishEditor]);

  // Word count from editor
  const wordCount = useMemo(() => {
    if (!editor) return 0;
    const text = editor.getText();
    return text.trim() ? text.trim().split(/\s+/).length : 0;
  }, [editor?.state?.doc?.content]);

  // Stop any active STT session
  const stopRecognition = useCallback(() => {
    if (sendTimerRef.current) { clearInterval(sendTimerRef.current); sendTimerRef.current = null; }
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      try { wsRef.current.send(JSON.stringify({ type: 'flush' })); } catch (_) {}
    }
    if (processorRef.current) { try { processorRef.current.disconnect(); } catch (_) {} processorRef.current = null; }
    if (audioContextRef.current) { try { audioContextRef.current.close(); } catch (_) {} audioContextRef.current = null; }
    if (mediaStreamRef.current) { mediaStreamRef.current.getTracks().forEach((t) => t.stop()); mediaStreamRef.current = null; }
    pcmBufferRef.current = [];
    const ws = wsRef.current;
    if (ws) { wsRef.current = null; setTimeout(() => { try { ws.close(); } catch (_) {} }, 500); }
  }, []);

  // Start Sarvam STT via WebSocket + microphone
  const startRecognition = useCallback(async (onInterim, onFinal, onError) => {
    stopRecognition();

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
    } catch (err) {
      console.error('[STT] Mic error:', err);
      if (onError) onError(err.message);
      return;
    }

    const audioContext = new AudioContext();
    audioContextRef.current = audioContext;
    if (audioContext.state !== 'running') await audioContext.resume();

    const nativeRate = audioContext.sampleRate;
    const ratio = nativeRate / 16000;
    const source = audioContext.createMediaStreamSource(stream);
    const processor = audioContext.createScriptProcessor(4096, 1, 1);
    processorRef.current = processor;

    let sendCount = 0;
    processor.onaudioprocess = (e) => {
      const float32 = e.inputBuffer.getChannelData(0);
      const outputLen = Math.floor(float32.length / ratio);
      for (let i = 0; i < outputLen; i++) {
        const sample = Math.max(-1, Math.min(1, float32[Math.floor(i * ratio)] || 0));
        const int16 = Math.max(-32768, Math.min(32767, Math.round(sample * 32767)));
        pcmBufferRef.current.push(int16 & 0xFF, (int16 >> 8) & 0xFF);
      }
    };

    source.connect(processor);
    processor.connect(audioContext.destination);

    const ws = new WebSocket(getSTTWebSocketUrl());
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[STT] Connected');
      sendTimerRef.current = setInterval(() => {
        if (pcmBufferRef.current.length === 0 || ws.readyState !== WebSocket.OPEN) return;
        const bytes = new Uint8Array(pcmBufferRef.current);
        pcmBufferRef.current = [];
        let binary = '';
        for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
        ws.send(JSON.stringify({ audio: { data: btoa(binary), sample_rate: 16000, encoding: 'audio/wav' } }));
        sendCount++;
        if (sendCount === 1) console.log('[STT] Sending audio...');
      }, 500);
    };

    let committedText = '';
    let currentWindowText = '';
    let prevRawPartial = '';

    const commonPrefixLen = (a, b) => {
      const limit = Math.min(a.length, b.length);
      let i = 0;
      while (i < limit && a.charCodeAt(i) === b.charCodeAt(i)) i++;
      return i;
    };

    const commitWindow = () => {
      if (currentWindowText) {
        committedText = committedText ? committedText + ' ' + currentWindowText : currentWindowText;
        currentWindowText = '';
      }
      prevRawPartial = '';
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'data') {
          const transcript = msg.data?.transcript?.trim();
          if (transcript) {
            if (prevRawPartial.length > 2) {
              const overlap = commonPrefixLen(transcript, prevRawPartial) / prevRawPartial.length;
              if (overlap < 0.3) {
                commitWindow();
                if (committedText) { onFinal(committedText.trim()); committedText = ''; }
              }
            }
            currentWindowText = transcript;
            prevRawPartial = transcript;
            const full = committedText ? committedText + ' ' + currentWindowText : currentWindowText;
            onInterim(full);
          }
        } else if (msg.type === 'events' && msg.data?.event === 'vad_end' && currentWindowText) {
          commitWindow();
          if (committedText) { onFinal(committedText.trim()); committedText = ''; }
        } else if (msg.type === 'error') {
          console.error('[STT] Error:', msg.data?.message || msg.data?.error);
        }
      } catch (_) {}
    };

    ws.onerror = () => { if (onError) onError('STT connection failed'); };
    ws.onclose = (e) => {
      console.log('[STT] Closed:', e.code);
      if (sendTimerRef.current) { clearInterval(sendTimerRef.current); sendTimerRef.current = null; }
      if (mediaStreamRef.current) { mediaStreamRef.current.getTracks().forEach((t) => t.stop()); mediaStreamRef.current = null; }
    };
  }, [stopRecognition]);

  // Handle voice/sparkle FAB click
  const handleVoiceFabClick = useCallback(() => {
    if (!editor) return;

    if (voiceMode === 'dictating') {
      if (interimText) {
        editor.commands.insertContent(interimText + ' ');
      }
      stopRecognition();
      setVoiceMode('idle');
      setInterimText('');
      return;
    }

    if (voiceMode === 'sparkle-listening') {
      const instruction = interimText;
      stopRecognition();
      setInterimText('');

      if (instruction && instruction.trim()) {
        setVoiceMode('sparkle-processing');

        const { from, to } = editor.state.selection;
        const selectedText = editor.state.doc.textBetween(from, to);

        editor.chain().setMeta('addToHistory', false)
          .setTextSelection({ from, to }).run();

        llmChat([
          { role: 'system', content: 'You are an Odia language editor. Modify the following text based on the user instruction. Return ONLY the modified text, nothing else. Keep the same language as the input. IMPORTANT: Preserve the original paragraph structure — keep the same number of paragraphs and line breaks. Do not merge paragraphs into a single block. Only refine the text within each paragraph.' },
          { role: 'user', content: `Instruction: ${instruction}\n\nText to modify:\n${selectedText}` },
        ])
          .then((response) => {
            const modifiedText = response.choices[0].message.content;
            const htmlContent = modifiedText
              .split(/\n\n+/)
              .filter(Boolean)
              .map((p) => `<p>${p.replace(/\n/g, '<br>')}</p>`)
              .join('');
            editor.chain().focus().setTextSelection({ from, to }).deleteSelection().insertContent(htmlContent).run();
            setVoiceMode('idle');
          })
          .catch((err) => {
            console.error('Sparkle AI error:', err);
            setSparkleError(t('review.sparkleError'));
            setVoiceMode('idle');
            setTimeout(() => setSparkleError(null), 3000);
          });
      } else {
        setVoiceMode('idle');
      }
      return;
    }

    if (voiceMode === 'sparkle-processing') return;

    if (hasSelection) {
      setVoiceMode('sparkle-listening');
      setSparkleError(null);

      let collectedText = '';

      startRecognition(
        (interim) => { setInterimText(interim); },
        (finalText) => {
          collectedText += finalText;
          setInterimText('');
          stopRecognition();

          setVoiceMode('sparkle-processing');

          const { from, to } = editor.state.selection;
          const selectedText = editor.state.doc.textBetween(from, to);

          llmChat([
            { role: 'system', content: 'You are an Odia language editor. Modify the following text based on the user instruction. Return ONLY the modified text, nothing else. Keep the same language as the input. IMPORTANT: Preserve the original paragraph structure — keep the same number of paragraphs and line breaks. Do not merge paragraphs into a single block. Only refine the text within each paragraph.' },
            { role: 'user', content: `Instruction: ${collectedText}\n\nText to modify:\n${selectedText}` },
          ])
            .then((response) => {
              const modifiedText = response.choices[0].message.content;
              const htmlContent = modifiedText
                .split(/\n\n+/)
                .filter(Boolean)
                .map((p) => `<p>${p.replace(/\n/g, '<br>')}</p>`)
                .join('');
              editor.chain().focus().deleteSelection().insertContent(htmlContent).run();
              setVoiceMode('idle');
            })
            .catch((err) => {
              console.error('Sparkle AI error:', err);
              setSparkleError(t('review.sparkleError'));
              setVoiceMode('idle');
              setTimeout(() => setSparkleError(null), 3000);
            });
        },
        (error) => { setVoiceMode('idle'); setInterimText(''); }
      ).catch(() => { setVoiceMode('idle'); setInterimText(''); });
    } else {
      setVoiceMode('dictating');
      setInterimText('');

      startRecognition(
        (interim) => setInterimText(interim),
        (finalText) => { editor.commands.insertContent(finalText + ' '); setInterimText(''); },
        () => { setVoiceMode('idle'); setInterimText(''); }
      ).catch(() => { setVoiceMode('idle'); setInterimText(''); });
    }
  }, [voiceMode, hasSelection, editor, interimText, startRecognition, stopRecognition, t]);

  // Convert selected text to local language (Odia)
  const handleConvertToLocal = useCallback(async () => {
    if (!editor) return;
    const { from, to } = editor.state.selection;
    if (from === to) return;
    const selectedText = editor.state.doc.textBetween(from, to);
    setConvertingSelection(true);
    try {
      const translated = (await llmChat({
        messages: [
          { role: 'system', content: 'Translate the following text to Odia. Return ONLY the translated text, nothing else. Do not add any explanation or prefix.' },
          { role: 'user', content: selectedText },
        ],
        expectOdia: true,
      })).trim();
      editor.chain().focus().setTextSelection({ from, to }).deleteSelection().insertContent(translated).run();
    } catch (err) {
      console.error('Convert to local failed:', err);
      setSparkleError(t('review.convertError', 'Translation failed'));
      setTimeout(() => setSparkleError(null), 3000);
    } finally {
      setConvertingSelection(false);
      setSelectionTooltip(null);
    }
  }, [editor, t]);

  // Handle typed instruction (same as voice sparkle but from text input)
  const handleTypedInstruction = useCallback(async () => {
    if (!editor || !instructionText.trim()) return;
    const { from, to } = editor.state.selection;
    const hasTextSelected = from !== to;

    const instruction = instructionText.trim();
    setInstructionText('');

    if (hasTextSelected) {
      setInstructionProcessing(true);
      const selectedText = editor.state.doc.textBetween(from, to);
      try {
        const res = await llmChat(
          [
            { role: 'system', content: 'You are an Odia language editor. Modify the following text based on the user instruction. Return ONLY the modified text, nothing else. Keep the same language as the input. IMPORTANT: Preserve the original paragraph structure — keep the same number of paragraphs and line breaks. Do not merge paragraphs into a single block. Only refine the text within each paragraph.' },
            { role: 'user', content: `Instruction: ${instruction}\n\nText to modify:\n${selectedText}` },
          ]
        );
        const modifiedText = res.choices[0].message.content;
        const htmlContent = modifiedText
          .split(/\n\n+/)
          .filter(Boolean)
          .map((p) => `<p>${p.replace(/\n/g, '<br>')}</p>`)
          .join('');
        editor.chain().focus().setTextSelection({ from, to }).deleteSelection().insertContent(htmlContent).run();
      } catch (err) {
        console.error('Typed instruction error:', err);
        setSparkleError(t('review.sparkleError'));
        setTimeout(() => setSparkleError(null), 3000);
      } finally {
        setInstructionProcessing(false);
      }
    } else {
      setInstructionProcessing(true);
      try {
        const res = await llmChat(
          [
            { role: 'system', content: 'You are an Odia language writer. Based on the user instruction, generate the requested content. Return ONLY the content text, nothing else. Write in Odia unless the instruction specifies otherwise.' },
            { role: 'user', content: instruction },
          ]
        );
        const generatedText = res.choices[0].message.content.trim();
        const htmlContent = generatedText
          .split(/\n\n+/)
          .filter(Boolean)
          .map((p) => `<p>${p.replace(/\n/g, '<br>')}</p>`)
          .join('');
        editor.chain().focus().insertContent(htmlContent).run();
      } catch (err) {
        console.error('Typed instruction error:', err);
        setSparkleError(t('review.sparkleError'));
        setTimeout(() => setSparkleError(null), 3000);
      } finally {
        setInstructionProcessing(false);
      }
    }
  }, [editor, instructionText, t]);

  // Escape key handler to stop voice
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && (voiceMode === 'dictating' || voiceMode === 'sparkle-listening')) {
        stopRecognition();
        setVoiceMode('idle');
        setInterimText('');
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [voiceMode, stopRecognition]);

  // Toolbar actions
  const handleInsertLink = useCallback(() => {
    if (!editor) return;
    const url = prompt('Enter URL:');
    if (url) {
      editor.chain().focus().setLink({ href: url }).run();
    }
  }, [editor]);

  const handleRevert = useCallback(() => {
    if (story && editor) {
      setHeadline(story.headline);
      const html = story.bodyText
        .split('\n\n')
        .map((p) => `<p>${p.replace(/\n/g, '<br>')}</p>`)
        .join('');
      editor.commands.setContent(html);
    }
  }, [story, editor]);

  // Action handlers
  const handleApprove = useCallback(async () => {
    setSaving(true);
    try {
      await updateStoryStatus(id, 'approved');
      setStatus('approved');
    } catch (err) {
      console.error('Failed to approve story:', err);
    } finally {
      setSaving(false);
    }
  }, [id]);

  const handleReject = useCallback(async () => {
    setSaving(true);
    try {
      await updateStoryStatus(id, 'rejected', rejectReason);
      setStatus('rejected');
      setRejectReason('');
    } catch (err) {
      console.error('Failed to reject story:', err);
    } finally {
      setSaving(false);
    }
  }, [id, rejectReason]);

  const handleStatusChange = useCallback(async (newStatus) => {
    setShowStatusDropdown(false);
    if (newStatus === status) return;
    setSaving(true);
    try {
      await updateStoryStatus(id, newStatus);
      setStatus(newStatus);
    } catch (err) {
      console.error('Failed to update status:', err);
    } finally {
      setSaving(false);
    }
  }, [id, status]);

  // Save all edited content in one call
  const handleSaveContent = useCallback(async () => {
    if (!story || !editor) return;
    setSaving(true);
    try {
      const bodyText = editor.getText();
      const paragraphs = bodyText.split('\n\n').map((text, i) => ({
        id: story.paragraphs?.[i]?.id || `p-new-${i}`,
        text,
      }));
      const payload = { headline, paragraphs };
      if (layoutHtml) {
        payload.layout_config = { html: layoutHtml };
      }
      const enHtml = englishEditor ? englishEditor.getHTML() : englishTranslation;
      if (enHtml) {
        payload.english_translation = enHtml;
      }
      if (socialPosts) {
        payload.social_posts = socialPosts;
      }
      await updateStory(id, payload);
    } catch (err) {
      console.error('Failed to save story:', err);
    } finally {
      setSaving(false);
    }
  }, [id, story, headline, editor, englishEditor, layoutHtml, englishTranslation, socialPosts]);

  // Translate to English via Sarvam AI
  const handleTranslateToEnglish = useCallback(async () => {
    if (!story) return;
    setTranslating(true);
    try {
      const odiaText = story.paragraphs.map((p) => p.text).filter(Boolean).join('\n\n');
      const res = await llmChat(
        [
          { role: 'system', content: 'Translate the following Odia newspaper article to English. Maintain journalistic tone. Return only the translated text.' },
          { role: 'user', content: `Headline: ${story.headline}\n\n${odiaText}` },
        ]
      );
      const translatedText = res.choices[0].message.content;
      setEnglishTranslation(translatedText);
      if (englishEditor) {
        const html = translatedText.split('\n\n').filter(Boolean).map(p => `<p>${p}</p>`).join('');
        englishEditor.commands.setContent(html);
      }
    } catch (err) {
      console.error('Translation failed:', err);
    } finally {
      setTranslating(false);
    }
  }, [story, englishEditor]);

  // Fetch draft editions for assignment
  useEffect(() => {
    fetchEditions({ status: 'draft' })
      .then((data) => setEditions(data?.editions || []))
      .catch(() => {});
  }, []);

  // Fetch pages when edition is selected
  useEffect(() => {
    if (!selectedEdition) {
      setEditionPages([]);
      setSelectedPage(null);
      return;
    }
    fetchEdition(selectedEdition)
      .then((data) => setEditionPages(data?.pages || []))
      .catch(() => setEditionPages([]));
  }, [selectedEdition]);

  // Handle edition assignment
  const handleAssignToEdition = useCallback(async () => {
    if (!selectedEdition || !selectedPage) return;
    setAssigningToEdition(true);
    try {
      await addStoryToPage(selectedEdition, selectedPage, id);
      const edition = editions.find((e) => e.id === selectedEdition);
      const page = editionPages.find((p) => p.id === selectedPage);
      setEditionAssignments((prev) => [
        ...prev,
        {
          edition_id: selectedEdition,
          edition_title: edition?.title || '',
          page_id: selectedPage,
          page_name: page?.page_name || '',
        },
      ]);
      setSelectedEdition(null);
      setSelectedPage(null);
    } catch (err) {
      console.error('Failed to assign to edition:', err);
    } finally {
      setAssigningToEdition(false);
    }
  }, [id, selectedEdition, selectedPage, editions, editionPages]);

  const handleRemoveFromEdition = useCallback(async (editionId, pageId) => {
    try {
      await removeStoryFromPage(editionId, pageId, id);
      setEditionAssignments((prev) =>
        prev.filter((a) => !(a.edition_id === editionId && a.page_id === pageId))
      );
    } catch (err) {
      console.error('Failed to remove from edition:', err);
    }
  }, [id]);

  // Audio playback
  const toggleAudioPlay = useCallback((mediaUrl) => {
    if (playingAudio === mediaUrl) {
      audioRef.current?.pause();
      setPlayingAudio(null);
    } else {
      if (audioRef.current) audioRef.current.pause();
      const audio = new Audio(mediaUrl);
      audio.onended = () => setPlayingAudio(null);
      audio.play();
      audioRef.current = audio;
      setPlayingAudio(mediaUrl);
    }
  }, [playingAudio]);

  const handleImageUpload = useCallback(async (e) => {
    const file = e.target.files?.[0];
    if (!file || !id) return;
    setUploadingImage(true);
    try {
      await uploadStoryImage(id, file);
      const freshStory = await fetchStory(id);
      setStory(transformStory(freshStory));
    } catch (err) {
      console.error('Image upload failed:', err);
    } finally {
      setUploadingImage(false);
      if (imageInputRef.current) imageInputRef.current.value = '';
    }
  }, [id]);

  return {
    // editors
    editor,
    englishEditor,
    editorContainerRef,

    // story
    story,
    setStory,
    loading,
    saving,

    // editable
    headline,
    setHeadline,
    status,
    showStatusDropdown,
    setShowStatusDropdown,

    // tabs / layout
    activeTab,
    setActiveTab,
    layoutHtml,
    setLayoutHtml,
    layoutGenerating,
    setLayoutGenerating,

    // popovers
    approveOpen,
    setApproveOpen,
    rejectOpen,
    setRejectOpen,
    rejectReason,
    setRejectReason,

    // metadata
    priority,
    setPriority,
    category,
    setCategory,

    // english translation
    englishTranslation,
    translating,

    // social
    socialPosts,
    setSocialPosts,

    // editions
    editions,
    selectedEdition,
    setSelectedEdition,
    selectedPage,
    setSelectedPage,
    editionPages,
    assigningToEdition,
    editionAssignments,

    // voice / sparkle
    voiceMode,
    hasSelection,
    voiceSupported,
    interimText,
    sparkleError,
    selectionTooltip,
    convertingSelection,

    // instruction input
    instructionText,
    setInstructionText,
    instructionProcessing,

    // audio playback
    playingAudio,

    // image upload
    uploadingImage,
    imageInputRef,

    // odia keyboard
    odiaKeyboard,
    setOdiaKeyboard,

    // word count
    wordCount,

    // handlers
    handleVoiceFabClick,
    handleConvertToLocal,
    handleTypedInstruction,
    handleInsertLink,
    handleRevert,
    handleApprove,
    handleReject,
    handleStatusChange,
    handleSaveContent,
    handleTranslateToEnglish,
    handleAssignToEdition,
    handleRemoveFromEdition,
    toggleAudioPlay,
    handleImageUpload,
  };
}
