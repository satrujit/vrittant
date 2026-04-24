/**
 * Odia text normalization.
 *
 * Reporters copy-paste from a long tail of legacy Odia editors and
 * WhatsApp clients that emit *unassigned* codepoints from the Oriya
 * Unicode block (U+0B64, U+0B65, …). Those code points have no glyph
 * in any font we ship, so they render as the dreaded tofu/box.
 *
 * The most common offender is U+0B64 — a reserved slot that some
 * legacy fonts visually encode as the sentence-end "purnaccheda"
 * (full stop). The canonical form is U+0964 DEVANAGARI DANDA (।),
 * which Indic fonts (including Noto Sans Oriya) render correctly.
 *
 * `normalizeOdiaText` substitutes these reserved codepoints with their
 * canonical Devanagari equivalents wherever Odia text crosses our
 * boundaries — load (transformStory), paste (TipTap extension), and
 * save (handleSaveContent) — so bad codepoints can't survive any
 * round-trip.
 *
 * Keep this list tight. Only add a substitution when:
 *   1. The source codepoint is unassigned/reserved in current Unicode
 *      (so no font has a glyph and it's guaranteed to render as tofu),
 *      AND
 *   2. There's a single, unambiguous canonical equivalent. Substituting
 *      Devanagari letters that "look like" Odia letters is OUT OF SCOPE
 *      — that's content, not normalization.
 */

const SUBSTITUTIONS = {
  // Reserved Oriya codepoints → their Devanagari shared-mark equivalents.
  // These two are the realistic culprits for the tofu the editorial
  // team sees on pasted text. Both Devanagari danda chars are the
  // canonical "purnaccheda" used in Odia, Hindi, Bengali, Marathi etc.
  '\u0B64': '\u0964',  // ୤ (reserved) → । DEVANAGARI DANDA
  '\u0B65': '\u0965',  // ୥ (reserved) → ॥ DEVANAGARI DOUBLE DANDA
};

// Pre-built character class for the regex — kept module-level so we
// don't rebuild it on every call. Update when SUBSTITUTIONS changes.
const NEEDLE_RE = new RegExp(
  '[' + Object.keys(SUBSTITUTIONS).join('') + ']',
  'g'
);

/**
 * Replace any known-bad Odia codepoint with its canonical equivalent.
 * Pure: returns input unchanged when there's nothing to do.
 *
 * @param {string} text
 * @returns {string}
 */
export function normalizeOdiaText(text) {
  if (typeof text !== 'string' || text.length === 0) return text;
  // Fast path — most strings won't contain any of the bad codepoints.
  if (!NEEDLE_RE.test(text)) {
    NEEDLE_RE.lastIndex = 0;
    return text;
  }
  NEEDLE_RE.lastIndex = 0;
  return text.replace(NEEDLE_RE, (ch) => SUBSTITUTIONS[ch] || ch);
}
