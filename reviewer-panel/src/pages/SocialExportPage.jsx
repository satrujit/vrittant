import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Twitter, Facebook, Instagram, Copy, Check, Loader2 } from 'lucide-react';
import { useI18n } from '../i18n';
import { fetchStory, transformStory } from '../services/api';
import { generateSocialPost } from '../utils/helpers';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { PageHeader } from '../components/common';
import { cn } from '@/lib/utils';

/* Shared back button for the page header */
function BackButton({ onClick }) {
  return (
    <Button
      variant="outline"
      size="icon"
      className="size-10 shrink-0"
      onClick={onClick}
      aria-label="Back"
    >
      <ArrowLeft size={18} />
    </Button>
  );
}

/* ----------------------------------------
   Platform card sub-component
   ---------------------------------------- */
function PlatformCard({
  platform,
  icon: Icon,
  iconColor,
  accentStyle,
  name,
  limitLabel,
  text,
  onTextChange,
  maxChars,
  showCharCounter,
  children,
  onCopy,
  copied,
  t,
}) {
  const charCount = text.length;
  const isWarn = maxChars && charCount > maxChars * 0.9;
  const isOver = maxChars && charCount > maxChars;

  return (
    <div className="flex flex-col overflow-hidden rounded-lg border border-border bg-card shadow-sm transition-all hover:border-border hover:shadow-md">
      {/* Accent strip */}
      <div className="h-1 w-full" style={accentStyle} />

      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <div className="flex items-center gap-2">
          <Icon size={20} className="shrink-0" style={{ color: iconColor }} />
          <span className="text-base font-semibold text-foreground">{name}</span>
        </div>
        <span className="inline-flex items-center whitespace-nowrap rounded-full bg-border px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
          {limitLabel}
        </span>
      </div>

      {/* Body */}
      <div className="flex flex-1 flex-col gap-3 px-5 py-4">
        <Textarea
          className={cn(
            'min-h-[140px] resize-y bg-background text-sm leading-relaxed text-foreground',
            !showCharCounter && 'min-h-[180px]'
          )}
          value={text}
          onChange={(e) => onTextChange(e.target.value)}
          spellCheck={false}
        />
        {showCharCounter && maxChars && (
          <div
            className={cn(
              'text-right text-xs text-muted-foreground',
              isWarn && 'text-[#F59E0B]',
              isOver && 'font-semibold text-destructive'
            )}
          >
            {t('social.characterCount', {
              count: String(charCount),
              max: String(maxChars),
            })}
          </div>
        )}
        {children}
      </div>

      {/* Footer */}
      <div className="border-t border-border px-5 py-3">
        <Button
          variant="outline"
          className={cn(
            'w-full gap-2',
            copied && 'border-[#10B981] bg-[#D1FAE5] text-[#10B981]'
          )}
          onClick={onCopy}
        >
          {copied ? <Check size={16} /> : <Copy size={16} />}
          {copied ? t('actions.copied') : t('actions.copyToClipboard')}
        </Button>
      </div>
    </div>
  );
}

/* ----------------------------------------
   Main page component
   ---------------------------------------- */
export default function SocialExportPage() {
  const { t } = useI18n();
  const { id: storyId } = useParams();
  const navigate = useNavigate();

  // API data state
  const [story, setStory] = useState(null);
  const [loading, setLoading] = useState(true);

  // Generate initial text for each platform
  const [twitterText, setTwitterText] = useState('');
  const [facebookText, setFacebookText] = useState('');
  const [instagramText, setInstagramText] = useState('');

  // Fetch story on mount
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchStory(storyId)
      .then((data) => {
        if (!cancelled) {
          const transformed = transformStory(data);
          setStory(transformed);
          if (transformed) {
            setTwitterText(generateSocialPost(transformed, 'twitter'));
            setFacebookText(generateSocialPost(transformed, 'facebook'));
            setInstagramText(generateSocialPost(transformed, 'instagram'));
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
  }, [storyId]);

  // Image selection state
  const mediaFiles = story?.mediaFiles || [];
  const [selectedImage, setSelectedImage] = useState(0);

  // Copy-to-clipboard logic
  const [copiedPlatform, setCopiedPlatform] = useState(null);

  const handleCopy = useCallback(
    async (platform, text) => {
      try {
        await navigator.clipboard.writeText(text);
      } catch {
        /* Fallback for insecure contexts */
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      }
      setCopiedPlatform(platform);
      setTimeout(() => setCopiedPlatform(null), 2000);
    },
    []
  );

  // Loading state
  if (loading) {
    return (
      <div className="mx-auto max-w-[1400px] p-6 lg:p-8">
        <PageHeader
          title={t('social.title')}
          leading={<BackButton onClick={() => navigate(-1)} />}
        />
        <div className="flex items-center justify-center p-16">
          <Loader2 size={24} className="animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  // Not found guard
  if (!story) {
    return (
      <div className="mx-auto max-w-[1400px] p-6 lg:p-8">
        <PageHeader
          title={t('social.title')}
          leading={<BackButton onClick={() => navigate(-1)} />}
        />
        <p className="text-muted-foreground">{t('common.storyNotFound')}</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1400px] p-6 lg:p-8">
      <PageHeader
        title={t('social.title')}
        subtitle={t('social.subtitle')}
        leading={<BackButton onClick={() => navigate(-1)} />}
      />

      {/* Story reference */}
      <div className="mb-8 rounded-lg border border-border bg-accent px-5 py-4">
        <div className="mb-1 text-xs font-medium uppercase tracking-[0.04em] text-muted-foreground">{t('table.storyTitle')}</div>
        <div className="text-lg font-semibold leading-tight text-foreground">{story.headline}</div>
      </div>

      {/* Platform cards */}
      <div className="mb-8 grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Twitter / X */}
        <PlatformCard
          platform="twitter"
          icon={Twitter}
          iconColor="#1DA1F2"
          accentStyle={{ background: '#1DA1F2' }}
          name={t('social.twitter')}
          limitLabel={t('social.twitterLimit')}
          text={twitterText}
          onTextChange={setTwitterText}
          maxChars={280}
          showCharCounter={true}
          onCopy={() => handleCopy('twitter', twitterText)}
          copied={copiedPlatform === 'twitter'}
          t={t}
        />

        {/* Facebook */}
        <PlatformCard
          platform="facebook"
          icon={Facebook}
          iconColor="#1877F2"
          accentStyle={{ background: '#1877F2' }}
          name={t('social.facebook')}
          limitLabel={t('social.facebookLimit')}
          text={facebookText}
          onTextChange={setFacebookText}
          maxChars={null}
          showCharCounter={false}
          onCopy={() => handleCopy('facebook', facebookText)}
          copied={copiedPlatform === 'facebook'}
          t={t}
        />

        {/* Instagram */}
        <PlatformCard
          platform="instagram"
          icon={Instagram}
          iconColor="#DD2A7B"
          accentStyle={{ background: 'linear-gradient(90deg, #F58529, #DD2A7B, #8134AF, #515BD4)' }}
          name={t('social.instagram')}
          limitLabel={t('social.instagramLimit')}
          text={instagramText}
          onTextChange={setInstagramText}
          maxChars={null}
          showCharCounter={false}
          onCopy={() => handleCopy('instagram', instagramText)}
          copied={copiedPlatform === 'instagram'}
          t={t}
        >
          {/* Inline image selector for Instagram */}
          {mediaFiles.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {mediaFiles.map((file, idx) => (
                <div
                  key={idx}
                  className={cn(
                    'h-[60px] w-[60px] cursor-pointer overflow-hidden rounded-sm border-2 border-transparent transition-colors hover:border-primary/40',
                    selectedImage === idx && 'border-primary'
                  )}
                  onClick={() => setSelectedImage(idx)}
                >
                  <img src={file.url} alt={file.name} className="block size-full object-cover" />
                </div>
              ))}
            </div>
          )}
        </PlatformCard>
      </div>

      {/* Cover image section */}
      <div className="mb-8">
        <h2 className="mb-3 text-base font-semibold text-foreground">{t('social.selectImage')}</h2>
        {mediaFiles.length === 0 ? (
          <p className="py-5 text-sm italic text-muted-foreground">{t('social.noMedia')}</p>
        ) : (
          <div className="flex flex-wrap gap-3">
            {mediaFiles.map((file, idx) => (
              <div
                key={idx}
                className={cn(
                  'relative h-[90px] w-[120px] cursor-pointer overflow-hidden rounded-md border-2 border-transparent transition-all hover:-translate-y-0.5 hover:shadow-md',
                  selectedImage === idx && 'border-primary shadow-[0_0_0_3px_rgba(250,108,56,0.2)]'
                )}
                onClick={() => setSelectedImage(idx)}
              >
                <img src={file.url} alt={file.name} className="block size-full object-cover" />
                {selectedImage === idx && (
                  <div className="absolute right-1 top-1 flex size-[22px] items-center justify-center rounded-full bg-primary text-primary-foreground">
                    <Check size={14} />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Toast */}
      <div
        className={cn(
          'pointer-events-none fixed bottom-8 left-1/2 z-[1000] -translate-x-1/2 translate-y-5 rounded-full bg-foreground px-6 py-2 text-sm font-medium text-primary-foreground opacity-0 shadow-lg transition-all',
          copiedPlatform && 'translate-y-0 opacity-100'
        )}
      >
        {t('actions.copied')}
      </div>
    </div>
  );
}
