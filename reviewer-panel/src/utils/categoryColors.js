/**
 * Per-category dot colour. Stable mapping so the same category always reads
 * the same hue across the panel — used by the dashboard review queue, the
 * news feed, and any other list view that wants a small coloured tag.
 *
 * Keys are matched case-insensitively; unknown values fall back to slate.
 * Add a category here only when a feature ships referencing it; an
 * unmapped category just renders slate.
 */
const CATEGORY_DOT = {
  general:        '#94a3b8', // slate
  regional:       '#0ea5e9', // sky — Odisha-local stories
  crime:          '#ef4444', // red
  governance:     '#3b82f6', // blue
  politics:       '#f59e0b', // amber
  science:        '#10b981', // emerald
  technology:     '#10b981', // emerald (mirrors science)
  business:       '#8b5cf6', // violet
  entertainment:  '#ec4899', // pink
  sports:         '#f97316', // orange
  health:         '#14b8a6', // teal
  education:      '#06b6d4', // cyan
  weather:        '#0ea5e9', // sky
};

export function categoryDotColor(category) {
  if (!category) return '#cbd5e1'; // slate-300 for empty
  return CATEGORY_DOT[String(category).toLowerCase()] || '#94a3b8';
}
