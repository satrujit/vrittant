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

  // Legacy-font Latin-block escapes. Reporters typing in old 8-bit Odia
  // fonts (AkrutiOriya / AkrutiOriBhagyashree etc.) emit byte 0xD2 for
  // the dirgha-i matra glyph; when that byte is decoded as Latin-1 it
  // arrives in our DB as `Ò` U+00D2. Pure-Odia fonts have no glyph for
  // that codepoint, so it renders as tofu in the middle of words like
  // ମାରିଥÒଲା (intended ମାରିଥୀଲା). Map back to the canonical matra.
  // Add more Latin-block mappings ONLY when found in real DB scans —
  // random Latin substitution would corrupt English in translations.
  '\u00D2': '\u0B40',  // Ò → ୀ ORIYA VOWEL SIGN II (dirgha-i)
};

// Pre-built character class for the regex — kept module-level so we
// don't rebuild it on every call. Update when SUBSTITUTIONS changes.
const NEEDLE_RE = new RegExp(
  '[' + Object.keys(SUBSTITUTIONS).join('') + ']',
  'g'
);

// Odia editorial convention: a space MUST precede the danda / double-danda,
// otherwise the standalone vertical-stroke glyph of । sits flush against
// the prior cluster and visually reads as another aa-kar matra (ା).
// Insert a single space when the character immediately before । or ॥ is
// non-whitespace. Leaves existing `\s।` and `^।` alone.
const DANDA_SPACING_RE = /(\S)([\u0964\u0965])/g;

/**
 * Replace known-bad Odia codepoints with their canonical equivalents
 * AND enforce a space before the danda for editorial legibility.
 * Pure: returns input unchanged when there's nothing to do.
 *
 * @param {string} text
 * @returns {string}
 */
export function normalizeOdiaText(text) {
  if (typeof text !== 'string' || text.length === 0) return text;

  // Step 1 — codepoint normalization. Skipped via fast-path when none
  // of the bad codepoints are present.
  let out = text;
  NEEDLE_RE.lastIndex = 0;
  if (NEEDLE_RE.test(out)) {
    NEEDLE_RE.lastIndex = 0;
    out = out.replace(NEEDLE_RE, (ch) => SUBSTITUTIONS[ch] || ch);
  }

  // Step 2 — danda spacing. Runs against the *normalized* string so it
  // catches both originally-canonical danda AND the freshly-substituted
  // ones from step 1.
  if (out.includes('\u0964') || out.includes('\u0965')) {
    out = out.replace(DANDA_SPACING_RE, '$1 $2');
  }

  return out;
}
