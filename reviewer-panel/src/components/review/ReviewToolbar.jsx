import {
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
  Table as TableIcon,
} from 'lucide-react';
import { useMemo } from 'react';
import { useI18n } from '../../i18n';
import { useAuth } from '../../contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

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

// Font sizes — covers comfortable reading sizes for users who need
// larger text without going overboard (anything past 32px starts
// breaking the column layout in the editor pane).
const FONT_SIZES = [
  { label: 'Size', value: '' },
  { label: '12', value: '12px' },
  { label: '14', value: '14px' },
  { label: '16', value: '16px' },
  { label: '18', value: '18px' },
  { label: '20', value: '20px' },
  { label: '24', value: '24px' },
  { label: '28', value: '28px' },
  { label: '32', value: '32px' },
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

/**
 * ReviewToolbar — TipTap formatting toolbar for the Odia editor.
 *
 * Owns the font-family list (org-conditional Pragativadi fonts) and
 * exposes Heading/Bold/Italic/Underline/Link, alignment, lists,
 * insert-table, Odia keyboard toggle, and a revert button.
 */
export default function ReviewToolbar({
  editor,
  odiaKeyboard,
  setOdiaKeyboard,
  handleInsertLink,
  handleRevert,
}) {
  const { t } = useI18n();
  const { user } = useAuth();

  const FONT_FAMILIES = useMemo(() => {
    const isPragativadi = user?.org?.slug === 'pragativadi';
    return isPragativadi ? [...BASE_FONTS, ...PRAGATIVADI_FONTS] : BASE_FONTS;
  }, [user?.org?.slug]);

  return (
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
        <select
          className="h-7 w-16 rounded-md border border-border bg-card px-1.5 text-xs text-foreground outline-none ml-px"
          value={editor?.getAttributes('textStyle').fontSize || ''}
          onChange={(e) => {
            if (e.target.value) {
              editor?.chain().focus().setFontSize(e.target.value).run();
            } else {
              editor?.chain().focus().unsetFontSize().run();
            }
          }}
          title={t('review.fontSize') || 'Font size'}
        >
          {FONT_SIZES.map((s) => (
            <option key={s.value} value={s.value}>{s.label}</option>
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
  );
}
