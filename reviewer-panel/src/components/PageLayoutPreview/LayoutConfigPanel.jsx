import { useState, useEffect } from 'react';
import {
  Sparkles, Download, Loader2, RefreshCw, BookmarkPlus,
} from 'lucide-react';
import {
  generateAutoLayout, exportIdml,
  fetchLayoutTemplates, createLayoutTemplate,
} from '../../services/api';
import { useI18n } from '../../i18n';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';

export default function LayoutConfigPanel({ storyId, layoutHtml, onHtmlChange, onLoadingChange, getStoryContent }) {
  const { t } = useI18n();
  const [loading, setLoading] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
  const [instructions, setInstructions] = useState('');

  // Templates
  const [templates, setTemplates] = useState([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState('none');

  // Save as template dialog
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [saveMode, setSaveMode] = useState('flexible');
  const [saving, setSaving] = useState(false);

  // Design preferences
  const [imageSize, setImageSize] = useState('medium');
  const [orientation, setOrientation] = useState('landscape');
  const [columns, setColumns] = useState('auto');
  const [colorMode, setColorMode] = useState('colored');
  const [includeSubtitle, setIncludeSubtitle] = useState(true);
  const [includeBullets, setIncludeBullets] = useState(true);
  const [includeQuote, setIncludeQuote] = useState(true);

  // Fetch layout templates on mount
  useEffect(() => {
    fetchLayoutTemplates()
      .then((data) => setTemplates(Array.isArray(data) ? data : []))
      .catch(console.error);
  }, []);

  const selectedTemplate = templates.find((t) => t.id === selectedTemplateId);

  // Notify parent when loading state changes
  useEffect(() => {
    onLoadingChange?.(loading);
  }, [loading, onLoadingChange]);

  const handleGenerate = async () => {
    if (!storyId) return;
    setLoading(true);
    try {
      const storyContent = getStoryContent ? getStoryContent() : {};
      const result = await generateAutoLayout(storyId, {
        instructions: instructions.trim() || undefined,
        headline: storyContent.headline || undefined,
        paragraphs: storyContent.paragraphs || undefined,
        layoutTemplateId: selectedTemplateId !== 'none' ? selectedTemplateId : undefined,
        preferences: {
          image_size: imageSize,
          orientation,
          columns: columns === 'auto' ? null : parseInt(columns, 10),
          color_mode: colorMode,
          include_subtitle: includeSubtitle,
          include_bullets: includeBullets,
          include_quote: includeQuote,
        },
      });
      if (result.html) {
        onHtmlChange(result.html);
      }
    } catch (err) {
      console.error('Auto layout failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleExportIdml = async () => {
    if (!storyId) return;
    setExportLoading(true);
    try {
      await exportIdml(storyId);
    } catch (err) {
      console.error('IDML export failed:', err);
    } finally {
      setExportLoading(false);
    }
  };

  const handleSaveAsTemplate = async () => {
    if (!saveName.trim() || !layoutHtml) return;
    setSaving(true);
    try {
      const newTpl = await createLayoutTemplate({
        name: saveName.trim(),
        mode: saveMode,
        html_content: layoutHtml,
      });
      setTemplates((prev) => [newTpl, ...prev]);
      setSaveDialogOpen(false);
      setSaveName('');
    } catch (err) {
      console.error('Save template failed:', err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex h-full min-w-[260px] max-w-[300px] flex-col gap-3 overflow-y-auto border-l border-border p-4">
      {/* ── AI Generate Button ── */}
      <Button
        className="flex w-full items-center gap-2.5 rounded-md bg-gradient-to-br from-indigo-500 via-violet-500 to-purple-500 px-3.5 py-2.5 text-white transition-all h-auto hover:opacity-[0.92] hover:-translate-y-px"
        onClick={handleGenerate}
        disabled={loading || !storyId}
      >
        <Sparkles size={18} />
        <span className="text-sm font-bold">
          {loading ? t('layout.generating') : t('layout.autoLayout')}
        </span>
      </Button>

      {/* ── Template Selector ── */}
      <div className="flex flex-col gap-1.5">
        <Label className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          {t('layout.template', 'Layout Template')}
        </Label>
        <Select value={selectedTemplateId} onValueChange={setSelectedTemplateId}>
          <SelectTrigger className="text-xs h-8">
            <SelectValue placeholder={t('layout.noTemplate', 'No template')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="none">{t('layout.noTemplate', 'No template (free design)')}</SelectItem>
            {templates.map((tpl) => (
              <SelectItem key={tpl.id} value={tpl.id}>
                <span className="flex items-center gap-2">
                  {tpl.name}
                  <Badge variant="outline" className="text-[9px] px-1 py-0 h-4">
                    {tpl.mode === 'fixed' ? t('layout.fixed', 'Fixed') : t('layout.flexible', 'Flexible')}
                  </Badge>
                </span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {selectedTemplate && (
          <p className="text-[10px] leading-tight text-muted-foreground">
            {selectedTemplate.mode === 'fixed'
              ? t('layout.fixedDesc', 'Exact design preserved. AI only replaces content.')
              : t('layout.flexibleDesc', 'Structure preserved. AI can adjust colors and sizing.')}
          </p>
        )}
      </div>

      {/* ── Design Preferences ── */}
      <div className="flex flex-col gap-2.5 rounded-lg border border-border p-2.5">
        <Label className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          {t('layout.designPrefs', 'Design Preferences')}
        </Label>

        {/* Image Size */}
        <div className="flex flex-col gap-1">
          <span className="text-[10px] text-muted-foreground">{t('layout.imageSize', 'Image Size')}</span>
          <div className="flex gap-1">
            {['small', 'medium', 'large'].map((s) => (
              <Button
                key={s}
                size="sm"
                variant={imageSize === s ? 'default' : 'outline'}
                className="h-6 px-2 text-[10px] flex-1"
                onClick={() => setImageSize(s)}
              >
                {s === 'small' ? 'S' : s === 'medium' ? 'M' : 'L'}
              </Button>
            ))}
          </div>
        </div>

        {/* Orientation */}
        <div className="flex flex-col gap-1">
          <span className="text-[10px] text-muted-foreground">{t('layout.orientation', 'Orientation')}</span>
          <div className="flex gap-1">
            {['landscape', 'portrait'].map((o) => (
              <Button
                key={o}
                size="sm"
                variant={orientation === o ? 'default' : 'outline'}
                className="h-6 px-2 text-[10px] flex-1"
                onClick={() => setOrientation(o)}
              >
                {o === 'landscape' ? t('layout.landscape', 'Landscape') : t('layout.portrait', 'Portrait')}
              </Button>
            ))}
          </div>
        </div>

        {/* Columns */}
        <div className="flex flex-col gap-1">
          <span className="text-[10px] text-muted-foreground">{t('layout.columns', 'Columns')}</span>
          <div className="flex gap-1">
            {['auto', '1', '2', '3'].map((c) => (
              <Button
                key={c}
                size="sm"
                variant={columns === c ? 'default' : 'outline'}
                className="h-6 px-2 text-[10px] flex-1"
                onClick={() => setColumns(c)}
              >
                {c === 'auto' ? t('layout.columnsAuto', 'Auto') : c}
              </Button>
            ))}
          </div>
        </div>

        {/* Color Mode */}
        <div className="flex flex-col gap-1">
          <span className="text-[10px] text-muted-foreground">{t('layout.colorMode', 'Color Mode')}</span>
          <div className="flex gap-1">
            <Button
              size="sm"
              variant={colorMode === 'colored' ? 'default' : 'outline'}
              className="h-6 px-2 text-[10px] flex-1"
              onClick={() => setColorMode('colored')}
            >
              {t('layout.colored', 'Colored')}
            </Button>
            <Button
              size="sm"
              variant={colorMode === 'bw' ? 'default' : 'outline'}
              className="h-6 px-2 text-[10px] flex-1"
              onClick={() => setColorMode('bw')}
            >
              {t('layout.blackWhite', 'B&W')}
            </Button>
          </div>
        </div>

        {/* Content toggles */}
        <div className="flex flex-col gap-1.5 pt-1 border-t border-border">
          <div className="flex items-center gap-2">
            <Checkbox
              id="subtitle"
              checked={includeSubtitle}
              onCheckedChange={setIncludeSubtitle}
              className="h-3.5 w-3.5"
            />
            <label htmlFor="subtitle" className="text-[10px] text-muted-foreground cursor-pointer">
              {t('layout.subtitle', 'Subtitle')}
            </label>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox
              id="bullets"
              checked={includeBullets}
              onCheckedChange={setIncludeBullets}
              className="h-3.5 w-3.5"
            />
            <label htmlFor="bullets" className="text-[10px] text-muted-foreground cursor-pointer">
              {t('layout.bullets', 'Bullet Points')}
            </label>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox
              id="quote"
              checked={includeQuote}
              onCheckedChange={setIncludeQuote}
              className="h-3.5 w-3.5"
            />
            <label htmlFor="quote" className="text-[10px] text-muted-foreground cursor-pointer">
              {t('layout.quote', 'Pull Quote')}
            </label>
          </div>
        </div>
      </div>

      {/* ── Instructions ── */}
      <div className="flex flex-col gap-1.5">
        <Label className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          {t('layout.instructions')}
        </Label>
        <Textarea
          className="min-h-16 resize-none text-xs"
          placeholder={t('layout.instructionsPlaceholder')}
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
        />
      </div>

      {/* ── Regenerate ── */}
      {layoutHtml && (
        <Button
          variant="outline"
          className="flex w-full items-center justify-center gap-1.5 text-sm"
          onClick={handleGenerate}
          disabled={loading}
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          {t('layout.regenerate')}
        </Button>
      )}

      {/* ── Save as Template ── */}
      {layoutHtml && (
        <Button
          variant="outline"
          className="flex w-full items-center justify-center gap-1.5 text-sm"
          onClick={() => setSaveDialogOpen(true)}
        >
          <BookmarkPlus size={14} />
          {t('layout.saveAsTemplate', 'Save as Template')}
        </Button>
      )}

      <div className="my-1 border-t border-border" />

      {/* ── Export IDML ── */}
      <Button
        className="flex w-full items-center justify-center gap-1.5 bg-foreground text-background font-medium hover:bg-foreground/80"
        onClick={handleExportIdml}
        disabled={exportLoading || !storyId}
      >
        <Download size={14} />
        {t('layout.exportIdml')}
      </Button>

      {/* ── Save Template Dialog ── */}
      <Dialog open={saveDialogOpen} onOpenChange={setSaveDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{t('layout.saveAsTemplate', 'Save as Template')}</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3 py-2">
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs">{t('layout.templateName', 'Template Name')}</Label>
              <Input
                value={saveName}
                onChange={(e) => setSaveName(e.target.value)}
                placeholder={t('layout.templateNamePlaceholder', "e.g. 'Breaking News - Bold', 'Sports Feature'...")}
                className="text-sm"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs">{t('layout.templateMode', 'Template Mode')}</Label>
              <Select value={saveMode} onValueChange={setSaveMode}>
                <SelectTrigger className="text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="fixed">{t('layout.fixed', 'Fixed')}</SelectItem>
                  <SelectItem value="flexible">{t('layout.flexible', 'Flexible')}</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-[10px] text-muted-foreground">
                {saveMode === 'fixed'
                  ? t('layout.fixedDesc', 'Exact design preserved. AI only replaces content.')
                  : t('layout.flexibleDesc', 'Structure preserved. AI can adjust colors and sizing.')}
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSaveDialogOpen(false)}>
              {t('actions.cancel', 'Cancel')}
            </Button>
            <Button onClick={handleSaveAsTemplate} disabled={saving || !saveName.trim()}>
              {saving ? (
                <>
                  <Loader2 size={14} className="animate-spin mr-1" />
                  {t('common.saving', 'Saving...')}
                </>
              ) : (
                t('actions.save', 'Save')
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
