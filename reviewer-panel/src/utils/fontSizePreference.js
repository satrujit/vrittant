/**
 * fontSizePreference — per-user "comfortable reading size" for the Odia editor.
 *
 * Why a localStorage preference and NOT a TipTap mark applied to the document?
 *  * Marks travel with the saved HTML and would silently rewrite every story
 *    the user opens, polluting the database with their personal pixel pref.
 *  * Other reviewers opening the same story would inherit the bumped size
 *    even though they never asked for it.
 *
 * Instead: ReviewToolbar writes the chosen size here when the user picks one
 * from the size dropdown, and ReviewEditor reads it back to set a CSS
 * `font-size` on the editor wrapper. The cascade then applies it to every
 * paragraph that doesn't carry an explicit inline `style="font-size:..."`,
 * so per-story per-character overrides (also driven by the same dropdown,
 * via TipTap's textStyle mark) still win via specificity.
 *
 * Net effect: "set 20px once and every story opens at 20px until I change it."
 */

const STORAGE_KEY = 'vrittant_fontSize';

// Whitelist that mirrors the FONT_SIZES dropdown in ReviewToolbar. Anything
// outside this set is rejected so a stray browser-extension write or a stale
// value from an older build can't poison the editor.
const ALLOWED = new Set(['12px', '14px', '16px', '18px', '20px', '24px', '28px', '32px']);

/**
 * Read the saved preference. Returns the size string (e.g. ``"20px"``) or
 * ``null`` if nothing valid is stored. Tolerates a missing/disabled
 * localStorage (private browsing, SSR) and unknown values.
 */
export function getFontSizePref() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw && ALLOWED.has(raw)) return raw;
  } catch {
    // localStorage unavailable — silently fall through to no-pref.
  }
  return null;
}

/**
 * Save (or clear) the preference. Pass ``null`` / empty string to revert to
 * the editor's natural default size. Invalid values are dropped silently
 * rather than throwing — the dropdown still reflects the user's pick locally
 * even if persistence is blocked.
 */
export function setFontSizePref(size) {
  try {
    if (!size) {
      window.localStorage.removeItem(STORAGE_KEY);
      return;
    }
    if (!ALLOWED.has(size)) return;
    window.localStorage.setItem(STORAGE_KEY, size);
  } catch {
    // localStorage unavailable — preference simply won't persist this session.
  }
}
