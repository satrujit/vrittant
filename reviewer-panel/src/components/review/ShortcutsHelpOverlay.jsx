import { useEffect } from 'react';
import { X } from 'lucide-react';

/**
 * ShortcutsHelpOverlay — centred modal that lists every review-page
 * keyboard shortcut. Triggered by Alt+/ (or ⌥/ on Mac). Dismissed by
 * Escape, the close button, or clicking the backdrop.
 *
 * The shortcut keys are stored as static data here so the source of
 * truth lives next to the visual presentation; the hook in
 * useReviewState wires the same key codes to actions.
 */
const SHORTCUTS = [
  { group: 'Focus', items: [
    { keys: ['⌥', 'H'], label: 'Headline' },
    { keys: ['⌥', 'B'], label: 'Body editor' },
    { keys: ['⌥', 'I'], label: 'Instruction box' },
    { keys: ['⌥', 'C'], label: 'Comments' },
  ]},
  { group: 'Tabs', items: [
    { keys: ['⌥', 'E'], label: 'Editor' },
    { keys: ['⌥', 'O'], label: 'Original' },
    { keys: ['⌥', 'T'], label: 'English (Translate)' },
  ]},
  { group: 'Actions', items: [
    { keys: ['⌥', 'R'], label: 'Refine story' },
    { keys: ['⌘', 'S'], label: 'Save' },
    { keys: ['⌘', '↵'], label: 'Approve' },
  ]},
  { group: 'General', items: [
    { keys: ['⌥', '/'], label: 'Toggle this help' },
    { keys: ['Esc'],    label: 'Close / dismiss' },
  ]},
];

export default function ShortcutsHelpOverlay({ open, onClose }) {
  // Lock background scroll while open and route Escape to onClose.
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKey = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener('keydown', onKey);
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm animate-in fade-in"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Keyboard shortcuts"
    >
      <div
        className="w-full max-w-lg rounded-xl border border-border bg-card shadow-2xl animate-in zoom-in-95"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b border-border px-5 py-3">
          <h2 className="text-sm font-semibold text-foreground">Keyboard shortcuts</h2>
          <button
            type="button"
            onClick={onClose}
            className="flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            aria-label="Close"
          >
            <X size={14} />
          </button>
        </header>
        <div className="grid grid-cols-2 gap-x-6 gap-y-4 p-5">
          {SHORTCUTS.map((g) => (
            <section key={g.group}>
              <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                {g.group}
              </h3>
              <ul className="space-y-1.5">
                {g.items.map((s) => (
                  <li key={s.label} className="flex items-center justify-between gap-3 text-xs">
                    <span className="text-foreground">{s.label}</span>
                    <span className="flex items-center gap-1">
                      {s.keys.map((k, i) => (
                        <kbd
                          key={i}
                          className="rounded border border-border bg-background px-1.5 py-0.5 font-mono text-[10px] font-semibold text-muted-foreground shadow-[0_1px_0_0_var(--border)]"
                        >
                          {k}
                        </kbd>
                      ))}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
        <footer className="border-t border-border bg-muted/30 px-5 py-2 text-[11px] text-muted-foreground">
          Tip — shortcuts pause while you're typing. Hit <kbd className="rounded border border-border bg-background px-1 font-mono">Esc</kbd> first to leave a field.
        </footer>
      </div>
    </div>
  );
}
