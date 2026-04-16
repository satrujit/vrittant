import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Bold,
  Italic,
  Underline as UnderlineIcon,
  Link2,
  AlignLeft,
  AlignCenter,
  AlignRight,
  Heading1,
  Heading2,
  List,
  ListOrdered,
  RotateCcw,
  MapPin,
  Calendar,
  FileText,
  ChevronDown,
  Loader2,
  Mic,
  MicOff,
  Image as ImageIcon,
  Play,
  Pause,
  Volume2,
  Sparkles,
  Table as TableIcon,
  Save,
  Pencil,
  Languages,
  LayoutTemplate,
  Share2,
  AlertTriangle,
  Clock,
  BookOpen,
  Check,
  SendHorizonal,
  ExternalLink,
  Download,
} from 'lucide-react';
import { useEditor, EditorContent } from '@tiptap/react';
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
import TranscriptionMark from '../extensions/TranscriptionMark';
import ExternalInputCompat from '../extensions/ExternalInputCompat';
import { createShreeLipiKeyboard } from '../extensions/ShreeLipiKeyboard';
import { useI18n } from '../i18n';
import { useAuth } from '../contexts/AuthContext';
import { fetchStory, updateStoryStatus, updateStory, transformStory, getMediaUrl, llmChat, getSTTWebSocketUrl, fetchEditions, fetchEdition, addStoryToPage, removeStoryFromPage, uploadStoryImage } from '../services/api';
import { Avatar, StatusBadge, CategoryChip } from '../components/common';
import { formatDate, generateICML } from '../utils/helpers';
import { PageLayoutCanvas, LayoutConfigPanel } from '../components/PageLayoutPreview';
import SocialTab from '../components/review/SocialTab';
import RelatedStoriesPanel from '../components/review/RelatedStoriesPanel';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const STATUS_OPTIONS = [
  'submitted',
  'in_progress',
  'approved',
  'rejected',
  'flagged',
  'published',
];

const PRIORITY_COLORS = {
  normal: '#3B82F6',
  urgent: '#F59E0B',
  breaking: '#EF4444',
};

const BASE_FONTS = [
  { label: 'Default', value: '' },
  { label: 'Plus Jakarta Sans', value: 'Plus Jakarta Sans' },
  { label: 'Akruti Regular (AkrutiOri06)', value: 'AkrutiOri06' },
  { label: 'Akruti Bilingual (AkrutiOfficeOri)', value: 'AkrutiOfficeOri' },
  { label: 'AkrutiOri99', value: 'AkrutiOri99' },
  { label: 'AkrutiOriIndesign', value: 'AkrutiOriIndesign' },
  { label: 'Arial', value: 'Arial' },
  { label: 'Georgia', value: 'Georgia' },
  { label: 'Times New Roman', value: 'Times New Roman' },
  { label: 'Courier New', value: 'Courier New' },
];

const PRAGATIVADI_FONTS = [
  { label: 'Pragativadi 1', value: 'Pragativadi 1' },
  { label: 'Pragativadi 2', value: 'Pragativadi 2' },
  { label: 'Pragativadi 3', value: 'Pragativadi 3' },
  { label: 'Pragativadi 4', value: 'Pragativadi 4' },
  { label: 'Pragativadi 5', value: 'Pragativadi 5' },
  { label: 'Pragativadi 6', value: 'Pragativadi 6' },
  { label: 'Pragativadi 7', value: 'Pragativadi 7' },
  { label: 'Pragativadi 8', value: 'Pragativadi 8' },
  { label: 'Pragativadi 9', value: 'Pragativadi 9' },
  { label: 'Pragativadi 10', value: 'Pragativadi 10' },
  { label: 'Pragativadi Bold1', value: 'Pragativadi Bold1' },
  { label: 'Pragativadi Bold2', value: 'Pragativadi Bold2' },
];

function ReviewPage() {
  const { t } = useI18n();
  const { user, config } = useAuth();
  const FONT_FAMILIES = useMemo(() => {
    const isPragativadi = user?.org?.slug === 'pragativadi';
    return isPragativadi ? [...BASE_FONTS, ...PRAGATIVADI_FONTS] : BASE_FONTS;
  }, [user?.org?.slug]);
  const { id } = useParams();
  const navigate = useNavigate();

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
  const [editionAssignments, setEditionAssignments] = useState([]); // [{edition_id, edition_title, page_id, page_name}]

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
  const [selectionTooltip, setSelectionTooltip] = useState(null); // { top, left }
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
  // Keep ref in sync so the ProseMirror plugin can read it without re-creating
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
        // Get bounding rect of the selection relative to viewport
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

          // Pre-populate edition assignments from API response
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
        ], { max_tokens: 2048 })
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
          ], { max_tokens: 2048 })
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
      const res = await llmChat(
        [
          { role: 'system', content: 'Translate the following text to Odia. Return ONLY the translated text, nothing else. Do not add any explanation or prefix.' },
          { role: 'user', content: selectedText },
        ],
        { max_tokens: 2048 }
      );
      const translated = res.choices[0].message.content.trim();
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
      // AI edit the selected text
      setInstructionProcessing(true);
      const selectedText = editor.state.doc.textBetween(from, to);
      try {
        const res = await llmChat(
          [
            { role: 'system', content: 'You are an Odia language editor. Modify the following text based on the user instruction. Return ONLY the modified text, nothing else. Keep the same language as the input. IMPORTANT: Preserve the original paragraph structure — keep the same number of paragraphs and line breaks. Do not merge paragraphs into a single block. Only refine the text within each paragraph.' },
            { role: 'user', content: `Instruction: ${instruction}\n\nText to modify:\n${selectedText}` },
          ],
          { max_tokens: 2048 }
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
      // No selection — insert AI-generated content at cursor
      setInstructionProcessing(true);
      try {
        const res = await llmChat(
          [
            { role: 'system', content: 'You are an Odia language writer. Based on the user instruction, generate the requested content. Return ONLY the content text, nothing else. Write in Odia unless the instruction specifies otherwise.' },
            { role: 'user', content: instruction },
          ],
          { max_tokens: 2048 }
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

  // Export ICML
  const handleExportICML = useCallback(() => {
    if (!story || !editor) return;
    const bodyText = editor.getText();
    const editedStory = {
      ...story,
      headline,
      bodyText,
      paragraphs: bodyText.split('\n\n').map((text, i) => ({
        id: `p-edit-${i}`,
        text,
      })),
    };
    const icmlStr = generateICML(editedStory);
    const blob = new Blob([icmlStr], { type: 'application/xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${headline.replace(/[^a-zA-Z0-9]/g, '_').substring(0, 40)}.icml`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [story, headline, editor]);

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
      // Save English translation from TipTap editor
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
        ],
        { max_tokens: 2048 }
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

  // Handle edition assignment (append story to page)
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

  // Handle removing a story from an edition
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
      // Reload story to get updated paragraphs
      const freshStory = await fetchStory(id);
      setStory(transformStory(freshStory));
    } catch (err) {
      console.error('Image upload failed:', err);
    } finally {
      setUploadingImage(false);
      if (imageInputRef.current) imageInputRef.current.value = '';
    }
  }, [id]);

  if (loading) {
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

  if (!story) {
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

  const mediaFiles = story.mediaFiles || [];
  const audioFiles = mediaFiles.filter((m) => m.type === 'audio' || m.url?.match(/\.(mp3|wav|m4a|ogg|aac)$/i));
  const imageFiles = mediaFiles.filter((m) => m.type === 'photo' || m.type === 'image' || m.url?.match(/\.(jpg|jpeg|png|gif|webp)$/i));

  const fabIcon = (() => {
    if (voiceMode === 'dictating') return <MicOff size={22} />;
    if (voiceMode === 'sparkle-listening') return <Sparkles size={22} />;
    if (voiceMode === 'sparkle-processing') return <Loader2 size={22} className="animate-spin" />;
    if (hasSelection) return <Sparkles size={22} />;
    return <Mic size={22} />;
  })();

  const priorityLevels = (config?.priority_levels || []).filter(p => p.is_active).map(p => p.key);
  const activePriorities = priorityLevels.length > 0 ? priorityLevels : ['normal', 'urgent', 'breaking'];

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      {/* ── Top metadata bar ── */}
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-border bg-card px-4 py-1.5">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <Button variant="outline" size="icon" className="size-7 shrink-0" onClick={() => navigate(-1)}>
            <ArrowLeft size={14} />
          </Button>

          <Avatar initials={story.reporter.initials} color={story.reporter.color} size="sm" />
          <span className="whitespace-nowrap text-xs font-medium text-foreground">{story.reporter.name}</span>

          <span className="select-none text-border">&middot;</span>

          {/* Category */}
          <Popover>
            <PopoverTrigger asChild>
              <button className="cursor-pointer border-none bg-transparent p-0">
                <CategoryChip category={category || story.category} />
              </button>
            </PopoverTrigger>
            <PopoverContent align="start" className="max-h-60 w-48 overflow-y-auto p-2">
              {(config?.categories?.filter((c) => c.is_active) || []).map((c) => (
                <button
                  key={c.key}
                  className={cn(
                    'flex w-full rounded-md border-none bg-transparent px-2 py-1 text-left text-xs transition-colors hover:bg-accent',
                    category === c.key && 'bg-primary/10 font-semibold'
                  )}
                  onClick={async () => {
                    setCategory(c.key);
                    try { await updateStory(id, { category: c.key }); } catch (err) { console.error('Failed to update category:', err); }
                  }}
                >
                  {t(`categories.${c.key}`, c.label || c.key)}
                </button>
              ))}
            </PopoverContent>
          </Popover>

          <span className="select-none text-border">&middot;</span>

          {/* Status (read-only badge) */}
          <StatusBadge status={status} />

          <span className="select-none text-border">&middot;</span>

          {/* Priority */}
          <Popover>
            <PopoverTrigger asChild>
              <button
                className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold text-white transition-colors"
                style={{ backgroundColor: PRIORITY_COLORS[priority] || PRIORITY_COLORS.normal }}
              >
                {priority === 'breaking' && <AlertTriangle size={10} />}
                {priority === 'urgent' && <Clock size={10} />}
                {t(`priority.${priority}`, priority)}
              </button>
            </PopoverTrigger>
            <PopoverContent align="start" className="w-36 p-2">
              {activePriorities.map((level) => (
                <button
                  key={level}
                  className={cn(
                    'flex w-full items-center gap-2 rounded-md border-none bg-transparent px-2 py-1.5 text-left text-xs transition-colors hover:bg-accent',
                    priority === level && 'bg-primary/10 font-semibold'
                  )}
                  onClick={async () => {
                    setPriority(level);
                    try { await updateStory(id, { priority: level }); } catch (err) { console.error('Failed to update priority:', err); }
                  }}
                >
                  <span className="size-2.5 rounded-full" style={{ backgroundColor: PRIORITY_COLORS[level] }} />
                  {t(`priority.${level}`, level)}
                </button>
              ))}
            </PopoverContent>
          </Popover>

          {story.location && (
            <>
              <span className="select-none text-border">&middot;</span>
              <span className="inline-flex items-center gap-1 whitespace-nowrap text-xs text-muted-foreground"><MapPin size={10} /> {story.location}</span>
            </>
          )}

          <span className="select-none text-border">&middot;</span>
          <span className="inline-flex items-center gap-1 whitespace-nowrap text-xs text-muted-foreground"><Calendar size={10} /> {formatDate(story.submittedAt)}</span>

          {story.source && (
            <>
              <span className="select-none text-border">&middot;</span>
              {story.source.startsWith('http') ? (
                <a
                  href={story.source}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 whitespace-nowrap text-xs text-primary hover:underline truncate max-w-[180px]"
                  title={story.source}
                >
                  <ExternalLink size={10} />
                  {t('review.source', 'Source')}
                </a>
              ) : (
                <span className="inline-flex items-center gap-1 whitespace-nowrap text-xs text-muted-foreground">
                  <FileText size={10} />
                  {story.source === 'Reporter Submitted' ? t('review.reporterSubmitted', 'Reporter Submitted') : story.source === 'Editor Created' ? t('review.editorCreated', 'Editor Created') : story.source}
                </span>
              )}
            </>
          )}

          <span className="select-none text-border">&middot;</span>

          {/* Edition assignment — moved to top bar */}
          <Popover>
            <PopoverTrigger asChild>
              <Button variant={editionAssignments.length > 0 ? "outline" : "default"} size="sm" className={editionAssignments.length > 0 ? "h-6 gap-1 px-2 text-xs" : "h-6 gap-1 px-2 text-xs bg-amber-500 text-white hover:bg-amber-600 border-amber-500"}>
                <BookOpen size={12} />
                {editionAssignments.length > 0 ? (
                  <><Check size={12} className="text-emerald-500" /> {editionAssignments.length}</>
                ) : t('review.assignEditionShort')}
              </Button>
            </PopoverTrigger>
            <PopoverContent align="start" className="w-80 p-3">
              <div className="flex flex-col gap-2">
                {/* Existing assignments */}
                {editionAssignments.length > 0 && (
                  <div className="flex flex-col gap-1">
                    {editionAssignments.map((a, i) => (
                      <div key={`${a.edition_id}-${a.page_id}-${i}`} className="flex items-center justify-between gap-1 rounded-md bg-muted/50 px-2 py-1">
                        <span className="truncate text-xs text-foreground">
                          {a.edition_title} &rarr; {a.page_name}
                        </span>
                        <button
                          className="shrink-0 rounded p-0.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                          onClick={() => handleRemoveFromEdition(a.edition_id, a.page_id)}
                          title="Remove"
                        >
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
                        </button>
                      </div>
                    ))}
                    <hr className="border-border" />
                  </div>
                )}

                {/* Add new assignment */}
                <select
                  className="w-full rounded-md border border-border bg-card px-2 py-1.5 text-xs text-foreground outline-none focus:border-ring"
                  value={selectedEdition || ''}
                  onChange={(e) => setSelectedEdition(e.target.value || null)}
                >
                  <option value="">{t('review.chooseEdition')}</option>
                  {editions.map((ed) => (
                    <option key={ed.id} value={ed.id}>{ed.title} ({ed.publication_date})</option>
                  ))}
                </select>
                {selectedEdition && (
                  <select
                    className="w-full rounded-md border border-border bg-card px-2 py-1.5 text-xs text-foreground outline-none focus:border-ring"
                    value={selectedPage || ''}
                    onChange={(e) => setSelectedPage(e.target.value || null)}
                  >
                    <option value="">{t('review.choosePage')}</option>
                    {editionPages.map((p) => (
                      <option key={p.id} value={p.id}>{p.page_name}</option>
                    ))}
                  </select>
                )}
                <Button
                  size="sm"
                  className="w-full"
                  disabled={!selectedEdition || !selectedPage || assigningToEdition}
                  onClick={handleAssignToEdition}
                >
                  {assigningToEdition ? <Loader2 size={12} className="animate-spin" /> : null}
                  {assigningToEdition ? '...' : t('review.assignButton')}
                </Button>
              </div>
            </PopoverContent>
          </Popover>
        </div>

        {/* Right actions */}
        <div className="flex shrink-0 items-center gap-1.5">
          <Popover open={approveOpen} onOpenChange={setApproveOpen}>
            <PopoverTrigger asChild>
              <Button size="sm" className="h-7 gap-1 bg-emerald-500 px-2.5 text-xs text-white hover:bg-emerald-600">
                <Check size={14} />
                {t('actions.approve')}
              </Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-56 p-3">
              <p className="mb-2 text-xs font-medium text-foreground">{t('actions.approve')}?</p>
              <div className="flex gap-1">
                <Button
                  size="sm"
                  className="flex-1 bg-emerald-500 text-white hover:bg-emerald-600"
                  onClick={() => { handleApprove(); setApproveOpen(false); }}
                  disabled={saving}
                >
                  {saving ? '...' : t('actions.confirm')}
                </Button>
                <Button variant="outline" size="sm" className="flex-1" onClick={() => setApproveOpen(false)}>
                  {t('actions.cancel')}
                </Button>
              </div>
            </PopoverContent>
          </Popover>

          <Popover open={rejectOpen} onOpenChange={setRejectOpen}>
            <PopoverTrigger asChild>
              <Button variant="outline" size="sm" className="h-7 gap-1 border-red-200 px-2.5 text-xs text-red-500 hover:border-red-500 hover:bg-red-50">
                {t('actions.reject')}
              </Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-64 p-3">
              <textarea
                className="mb-2 min-h-12 w-full rounded-md border border-border bg-card px-2 py-1.5 text-xs text-foreground outline-none focus:border-ring"
                placeholder={t('review.rejectPlaceholder')}
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                rows={2}
              />
              <div className="flex gap-1">
                <Button
                  size="sm"
                  className="flex-1 bg-red-500 text-white hover:bg-red-600"
                  onClick={() => { handleReject(); setRejectOpen(false); }}
                  disabled={saving}
                >
                  {saving ? '...' : t('actions.confirm')}
                </Button>
                <Button variant="outline" size="sm" className="flex-1" onClick={() => setRejectOpen(false)}>
                  {t('actions.cancel')}
                </Button>
              </div>
            </PopoverContent>
          </Popover>

          <Button size="sm" className="h-7 gap-1 px-2.5 text-xs" onClick={handleSaveContent} disabled={saving}>
            {saving ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
            {t('actions.saveDraft')}
          </Button>
        </div>
      </div>

      {/* ── Sticky headline ── */}
      <div className="shrink-0 border-b border-border bg-background px-6 py-2">
        <input
          type="text"
          className="w-full border-none bg-transparent px-0 text-xl font-bold leading-tight text-foreground outline-none placeholder:text-muted-foreground/50"
          value={headline}
          onChange={(e) => setHeadline(e.target.value)}
          placeholder={t('review.headlinePlaceholder') || 'Headline...'}
        />
      </div>

      {/* ── Sticky tabs + scrollable content ── */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex min-h-0 flex-1 flex-col">
        <div className="shrink-0 border-b border-border bg-background px-6">
          <TabsList variant="line" className="w-full justify-start">
            <TabsTrigger value="editor"><Pencil size={14} /> {t('review.tabs.editor')}</TabsTrigger>
            <TabsTrigger value="original"><FileText size={14} /> {t('review.tabs.original')}</TabsTrigger>
            <TabsTrigger value="english"><Languages size={14} /> {t('review.tabs.english')}</TabsTrigger>
            <TabsTrigger value="layout"><LayoutTemplate size={14} /> {t('review.tabs.pageLayout')}</TabsTrigger>
            <TabsTrigger value="social"><Share2 size={14} /> {t('review.tabs.social')}</TabsTrigger>
          </TabsList>
        </div>

        {/* ── Editor tab ── */}
        <TabsContent value="editor" className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
          <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-6 py-2">
            {/* Toolbar */}
            <div className="flex shrink-0 flex-wrap items-center justify-between gap-0.5 rounded-t-lg border border-b-0 border-border bg-background px-1.5 py-1">
              <div className="flex flex-wrap items-center gap-px">
                <select
                  className="h-7 max-w-32 rounded-md border border-border bg-card px-1.5 text-xs text-foreground outline-none"
                  value={editor?.getAttributes('textStyle').fontFamily || ''}
                  onChange={(e) => {
                    if (e.target.value) {
                      editor?.chain().focus().setFontFamily(e.target.value).run();
                    } else {
                      editor?.chain().focus().unsetFontFamily().run();
                    }
                  }}
                >
                  {FONT_FAMILIES.map((f) => (
                    <option key={f.value} value={f.value}>{f.label}</option>
                  ))}
                </select>
                <div className="mx-1 h-5 w-px bg-border" />
                {[
                  { icon: Heading1, action: () => editor?.chain().focus().toggleHeading({ level: 1 }).run(), active: editor?.isActive('heading', { level: 1 }), title: 'H1' },
                  { icon: Heading2, action: () => editor?.chain().focus().toggleHeading({ level: 2 }).run(), active: editor?.isActive('heading', { level: 2 }), title: 'H2' },
                ].map(({ icon: Icon, action, active, title }) => (
                  <button key={title} className={cn('flex size-7 items-center justify-center rounded-md border-none bg-transparent text-muted-foreground transition-all hover:bg-accent hover:text-primary', active && 'bg-primary/10 text-primary')} onClick={action} title={title}><Icon size={16} /></button>
                ))}
                <div className="mx-1 h-5 w-px bg-border" />
                {[
                  { icon: Bold, action: () => editor?.chain().focus().toggleBold().run(), active: editor?.isActive('bold'), title: 'Bold' },
                  { icon: Italic, action: () => editor?.chain().focus().toggleItalic().run(), active: editor?.isActive('italic'), title: 'Italic' },
                  { icon: UnderlineIcon, action: () => editor?.chain().focus().toggleUnderline().run(), active: editor?.isActive('underline'), title: 'Underline' },
                  { icon: Link2, action: handleInsertLink, active: false, title: 'Link' },
                ].map(({ icon: Icon, action, active, title }) => (
                  <button key={title} className={cn('flex size-7 items-center justify-center rounded-md border-none bg-transparent text-muted-foreground transition-all hover:bg-accent hover:text-primary', active && 'bg-primary/10 text-primary')} onClick={action} title={title}><Icon size={16} /></button>
                ))}
                <div className="mx-1 h-5 w-px bg-border" />
                {[
                  { icon: AlignLeft, action: () => editor?.chain().focus().setTextAlign('left').run(), active: editor?.isActive({ textAlign: 'left' }), title: 'Left' },
                  { icon: AlignCenter, action: () => editor?.chain().focus().setTextAlign('center').run(), active: editor?.isActive({ textAlign: 'center' }), title: 'Center' },
                  { icon: AlignRight, action: () => editor?.chain().focus().setTextAlign('right').run(), active: editor?.isActive({ textAlign: 'right' }), title: 'Right' },
                ].map(({ icon: Icon, action, active, title }) => (
                  <button key={title} className={cn('flex size-7 items-center justify-center rounded-md border-none bg-transparent text-muted-foreground transition-all hover:bg-accent hover:text-primary', active && 'bg-primary/10 text-primary')} onClick={action} title={title}><Icon size={16} /></button>
                ))}
                <div className="mx-1 h-5 w-px bg-border" />
                {[
                  { icon: List, action: () => editor?.chain().focus().toggleBulletList().run(), active: editor?.isActive('bulletList'), title: 'Bullets' },
                  { icon: ListOrdered, action: () => editor?.chain().focus().toggleOrderedList().run(), active: editor?.isActive('orderedList'), title: 'Numbered' },
                ].map(({ icon: Icon, action, active, title }) => (
                  <button key={title} className={cn('flex size-7 items-center justify-center rounded-md border-none bg-transparent text-muted-foreground transition-all hover:bg-accent hover:text-primary', active && 'bg-primary/10 text-primary')} onClick={action} title={title}><Icon size={16} /></button>
                ))}
                <div className="mx-1 h-5 w-px bg-border" />
                <button
                  className="flex size-7 items-center justify-center rounded-md border-none bg-transparent text-muted-foreground transition-all hover:bg-accent hover:text-primary"
                  onClick={() => editor?.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()}
                  title="Table"
                >
                  <TableIcon size={16} />
                </button>
                <div className="mx-1 h-5 w-px bg-border" />
                <button
                  className={cn(
                    'flex items-center gap-1 rounded-md border-none px-2 py-1 text-xs font-bold transition-all',
                    odiaKeyboard
                      ? 'bg-primary/15 text-primary ring-1 ring-primary/30'
                      : 'bg-transparent text-muted-foreground hover:bg-accent hover:text-primary'
                  )}
                  onClick={() => setOdiaKeyboard((v) => !v)}
                  title={odiaKeyboard ? 'ଓଡ଼ିଆ ON (Ctrl+Space to switch)' : 'English (Ctrl+Space to switch)'}
                >
                  {odiaKeyboard ? 'ଅ' : 'En'}
                </button>
              </div>
              <Button variant="outline" size="sm" className="h-7 gap-1 px-2 text-xs" onClick={handleRevert} title={t('review.revert')}>
                <RotateCcw size={12} />
              </Button>
            </div>

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

            {/* Attachments */}
            <div className="mt-2 rounded-lg border border-border bg-card p-3">
              <h4 className="mb-2 flex items-center justify-between text-xs font-semibold text-muted-foreground">
                <span className="flex items-center gap-2">
                  <ImageIcon size={14} />
                  {mediaFiles.length > 0 ? mediaFiles.length : t('review.attachments', 'Attachments ({count})').replace('{count}', '0')}
                </span>
                <input
                  ref={imageInputRef}
                  type="file"
                  accept="image/*"
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
            {/* Instruction text input */}
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

            {/* Mic button */}
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
        </TabsContent>

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
              // Extract text paragraphs from editor
              const bodyText = editor ? editor.getText() : '';
              const textParagraphs = bodyText.split('\n\n').filter(Boolean).map((text, i) => ({
                id: `p-${i}`,
                text,
                type: 'paragraph',
              }));

              // Collect image paragraphs from story data (media_path or image_url)
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
      </Tabs>
    </div>
  );
}

export default ReviewPage;
