import { useState, useCallback } from 'react';
import { Twitter, Facebook, Instagram, Copy, Check, Sparkles, Loader2 } from 'lucide-react';
import { useI18n } from '../../i18n';
import { llmChat } from '../../services/api';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

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
  onCopy,
  copied,
  onGenerate,
  generating,
  t,
}) {
  const charCount = text.length;
  const isWarn = maxChars && charCount > maxChars * 0.9;
  const isOver = maxChars && charCount > maxChars;

  return (
    <div className="flex flex-col overflow-hidden rounded-lg border border-border bg-card shadow-sm transition-all hover:shadow-md">
      <div className="h-1 w-full" style={accentStyle} />
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Icon size={16} className="shrink-0" style={{ color: iconColor }} />
          <span className="text-sm font-semibold text-foreground">{name}</span>
        </div>
        <span className="inline-flex items-center whitespace-nowrap rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
          {limitLabel}
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-2 px-4 py-3">
        {!text && !generating ? (
          <div className="flex flex-col items-center justify-center gap-3 py-8">
            <Icon size={28} className="text-muted-foreground/50" style={{ color: iconColor + '40' }} />
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5"
              onClick={onGenerate}
            >
              <Sparkles size={14} />
              {t('social.generate')}
            </Button>
          </div>
        ) : generating ? (
          <div className="flex flex-col items-center justify-center gap-2 py-8">
            <Loader2 size={20} className="animate-spin text-primary" />
            <p className="text-xs text-muted-foreground">{t('social.generating')}</p>
          </div>
        ) : (
          <>
            <Textarea
              className="min-h-[120px] resize-y bg-background text-sm leading-relaxed text-foreground"
              value={text}
              onChange={(e) => onTextChange(e.target.value)}
              spellCheck={false}
            />
            {showCharCounter && maxChars && (
              <div
                className={cn(
                  'text-right text-xs text-muted-foreground',
                  isWarn && 'text-amber-500',
                  isOver && 'font-semibold text-destructive'
                )}
              >
                {charCount}/{maxChars}
              </div>
            )}
          </>
        )}
      </div>
      {text && (
        <div className="flex items-center gap-1 border-t border-border px-4 py-2">
          <Button
            variant="outline"
            size="sm"
            className={cn(
              'flex-1 gap-1.5',
              copied && 'border-emerald-500 bg-emerald-50 text-emerald-600'
            )}
            onClick={onCopy}
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
            {copied ? t('actions.copied') : t('actions.copyToClipboard')}
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="gap-1"
            onClick={onGenerate}
            disabled={generating}
          >
            <Sparkles size={12} />
          </Button>
        </div>
      )}
    </div>
  );
}

const PLATFORM_PROMPTS = {
  twitter: 'Write a concise, engaging tweet (max 280 characters) for this news article. Use relevant hashtags. Write in the same language as the article. Return ONLY the tweet text.',
  facebook: 'Write an engaging Facebook post for this news article. Include a hook, key details, and a call to action. Write in the same language as the article. Return ONLY the post text.',
  instagram: 'Write an Instagram caption for this news article. Make it engaging with relevant emojis and hashtags. Write in the same language as the article. Return ONLY the caption text.',
};

export default function SocialTab({ story, initialPosts, onPostsChange }) {
  const { t } = useI18n();

  const [twitterText, setTwitterText] = useState(initialPosts?.twitter || '');
  const [facebookText, setFacebookText] = useState(initialPosts?.facebook || '');
  const [instagramText, setInstagramText] = useState(initialPosts?.instagram || '');

  const [generatingPlatform, setGeneratingPlatform] = useState(null);
  const [copiedPlatform, setCopiedPlatform] = useState(null);

  // Notify parent whenever any text changes
  const notifyChange = useCallback((twitter, facebook, instagram) => {
    if (onPostsChange) {
      const posts = {};
      if (twitter) posts.twitter = twitter;
      if (facebook) posts.facebook = facebook;
      if (instagram) posts.instagram = instagram;
      onPostsChange(Object.keys(posts).length > 0 ? posts : null);
    }
  }, [onPostsChange]);

  const handleTwitterChange = useCallback((val) => {
    setTwitterText(val);
    notifyChange(val, facebookText, instagramText);
  }, [facebookText, instagramText, notifyChange]);

  const handleFacebookChange = useCallback((val) => {
    setFacebookText(val);
    notifyChange(twitterText, val, instagramText);
  }, [twitterText, instagramText, notifyChange]);

  const handleInstagramChange = useCallback((val) => {
    setInstagramText(val);
    notifyChange(twitterText, facebookText, val);
  }, [twitterText, facebookText, notifyChange]);

  const articleContent = `Headline: ${story?.headline || ''}\n\n${(story?.paragraphs || []).map(p => p.text).filter(Boolean).join('\n\n')}`;

  const generateForPlatform = useCallback(async (platform) => {
    setGeneratingPlatform(platform);
    try {
      const res = await llmChat(
        [
          { role: 'system', content: PLATFORM_PROMPTS[platform] },
          { role: 'user', content: articleContent },
        ]
      );
      const generated = res.choices[0].message.content.trim();
      if (platform === 'twitter') {
        setTwitterText(generated);
        notifyChange(generated, facebookText, instagramText);
      } else if (platform === 'facebook') {
        setFacebookText(generated);
        notifyChange(twitterText, generated, instagramText);
      } else if (platform === 'instagram') {
        setInstagramText(generated);
        notifyChange(twitterText, facebookText, generated);
      }
    } catch (err) {
      console.error(`Failed to generate ${platform} post:`, err);
    } finally {
      setGeneratingPlatform(null);
    }
  }, [articleContent, twitterText, facebookText, instagramText, notifyChange]);

  const handleCopy = useCallback(async (platform, text) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
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
  }, []);

  return (
    <div className="flex-1 overflow-y-auto p-5">
      {/* Generate all button */}
      <div className="mb-4 flex items-center justify-end">
        <Button
          size="sm"
          className="gap-1.5"
          onClick={async () => {
            for (const p of ['twitter', 'facebook', 'instagram']) {
              await generateForPlatform(p);
            }
          }}
          disabled={!!generatingPlatform}
        >
          <Sparkles size={14} />
          {t('social.generateAll')}
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <PlatformCard
          platform="twitter"
          icon={Twitter}
          iconColor="#1DA1F2"
          accentStyle={{ background: '#1DA1F2' }}
          name="X / Twitter"
          limitLabel="280 chars"
          text={twitterText}
          onTextChange={handleTwitterChange}
          maxChars={280}
          showCharCounter={true}
          onCopy={() => handleCopy('twitter', twitterText)}
          copied={copiedPlatform === 'twitter'}
          onGenerate={() => generateForPlatform('twitter')}
          generating={generatingPlatform === 'twitter'}
          t={t}
        />
        <PlatformCard
          platform="facebook"
          icon={Facebook}
          iconColor="#1877F2"
          accentStyle={{ background: '#1877F2' }}
          name="Facebook"
          limitLabel="No limit"
          text={facebookText}
          onTextChange={handleFacebookChange}
          maxChars={null}
          showCharCounter={false}
          onCopy={() => handleCopy('facebook', facebookText)}
          copied={copiedPlatform === 'facebook'}
          onGenerate={() => generateForPlatform('facebook')}
          generating={generatingPlatform === 'facebook'}
          t={t}
        />
        <PlatformCard
          platform="instagram"
          icon={Instagram}
          iconColor="#DD2A7B"
          accentStyle={{ background: 'linear-gradient(90deg, #F58529, #DD2A7B, #8134AF, #515BD4)' }}
          name="Instagram"
          limitLabel="2200 chars"
          text={instagramText}
          onTextChange={handleInstagramChange}
          maxChars={2200}
          showCharCounter={false}
          onCopy={() => handleCopy('instagram', instagramText)}
          copied={copiedPlatform === 'instagram'}
          onGenerate={() => generateForPlatform('instagram')}
          generating={generatingPlatform === 'instagram'}
          t={t}
        />
      </div>

      {/* Copied toast */}
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
