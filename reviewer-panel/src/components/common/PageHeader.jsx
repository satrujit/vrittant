import { cn } from '@/lib/utils';

/**
 * PageHeader — canonical top-of-page title block.
 *
 * Use on every top-level page so spacing, type scale, icon treatment,
 * and the title/subtitle hierarchy stay consistent across the panel.
 *
 * Usage:
 *   <PageHeader
 *     icon={Trophy}
 *     title="Reporters"
 *     subtitle="Reporters ranked by score"
 *     actions={<Button>+ Add</Button>}
 *   />
 *
 * - `icon` is a lucide component (not an element). It's rendered inside a
 *   bg-primary/10 rounded square at a fixed size so every page that uses
 *   one looks the same.
 * - `actions` slot sits on the right (top-aligned) for primary CTAs or
 *   small toolbars that belong with the title rather than the filter row.
 * - Pass `leading` for fully bespoke leading content (e.g. a back button
 *   stack with breadcrumb) when an icon isn't enough.
 */
export default function PageHeader({
  icon: Icon,
  title,
  subtitle,
  actions,
  leading,
  className,
}) {
  // The `icon` prop is intentionally ignored. Header glyphs add visual
  // noise without information value (the title already names the page,
  // the sidebar already shows what's selected). Kept in the API only so
  // existing call sites don't need to be touched.
  void Icon;
  return (
    <div className={cn('flex items-start justify-between gap-4 mb-5 pb-3 border-b border-border', className)}>
      <div className="flex items-center gap-2.5 min-w-0">
        {leading}
        <div className="min-w-0">
          <h1 className="text-[17px] font-semibold leading-tight text-foreground truncate">
            {title}
          </h1>
          {subtitle && (
            <p className="mt-0.5 text-[12.5px] text-muted-foreground">{subtitle}</p>
          )}
        </div>
      </div>
      {actions && <div className="shrink-0 flex items-center gap-2">{actions}</div>}
    </div>
  );
}
