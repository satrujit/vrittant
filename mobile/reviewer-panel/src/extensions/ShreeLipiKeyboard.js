/**
 * ShreeLipiKeyboard — JavaScript-based Odia keyboard for TipTap
 * Replicates the Shree-Lipi Modular (Utkal) layout used by Akriti software.
 *
 * Key principle: ALL characters insert IMMEDIATELY (consonants, halant, matras,
 * ra-phala, ya-phala). Only two things are buffered:
 *   1. e-kar (େ) — typed early but placed at end of conjunct cluster
 *   2. reph (ର୍) — typed early but placed before the next consonant
 *
 * Based on: https://github.com/coldbreeze16/Kunji-Binyasa
 */
import { Extension } from '@tiptap/core';
import { Plugin, PluginKey } from '@tiptap/pm/state';

const pluginKey = new PluginKey('shreeLipiKeyboard');

// ── Key → Unicode maps ───────────────────────────────────────────────

const LOWER = {
  q: '\u0B2C',       // ବ
  w: '\u0B2A',       // ପ
  e: '\u0B28',       // ନ
  r: '\u0B26',       // ଦ
  t: '\u0B38',       // ସ
  y: '\u0B4C',       // ୌ (matra)
  u: '\u0B2F',       // ଯ
  i: '\u0B02',       // ଂ
  o: '\u0B39',       // ହ
  p: '\u0B48',       // ୈ (matra)
  a: '\u0B2E',       // ମ
  s: '\u0B15',       // କ
  d: '\u0B4D',       // ୍ (virama)
  f: '\u0B24',       // ତ
  g: '\u0B3F',       // ି (matra)
  h: '\u0B40',       // ୀ (matra)
  j: '\u0B30',       // ର
  k: '\u0B3E',       // ା (matra)
  l: 'EKAR',         // େ — SPECIAL: buffered
  z: '\u0B2D',       // ଭ
  x: '\u0B17',       // ଗ
  c: '\u0B1C',       // ଜ
  v: '\u0B1A',       // ଚ
  b: '\u0B41',       // ୁ (matra)
  n: '\u0B42',       // ୂ (matra)
  m: '\u0B33',       // ଳ
};

const UPPER = {
  Q: 'Q',
  W: '\u0B2B',       // ଫ
  E: '\u0B5C',       // ଡ଼
  R: '\u0B27',       // ଧ
  T: '\u0B13',       // ଓ
  Y: '\u0B14',       // ଔ
  U: '\u0B1F',       // ଟ
  I: '\u0B20',       // ଠ
  O: '\u0B21',       // ଡ
  P: '\u0B22',       // ଢ
  A: '\u0B22\u0B3C', // ଢ଼
  S: '\u0B16',       // ଖ
  D: '\u0B4D\u200C', // ୍ + ZWNJ
  F: '\u0B25',       // ଥ
  G: '\u0B07',       // ଇ
  H: '\u0B08',       // ଈ
  J: '\u0B23',       // ଣ
  K: '\u0B36',       // ଶ
  L: '\u0B37',       // ଷ
  Z: '\u0B19',       // ଙ
  X: '\u0B18',       // ଘ
  C: '\u0B1D',       // ଝ
  V: '\u0B1B',       // ଛ
  B: '\u0B09',       // ଉ
  N: '\u0B0A',       // ଊ
  M: '\u0B32',       // ଲ
};

const SYMBOL = {
  '`': '\u0964',           // ।
  '1': '\u0B67', '2': '\u0B68', '3': '\u0B69', '4': '\u0B6A',
  '5': '\u0B6B', '6': '\u0B6C', '7': '\u0B6D', '8': '\u0B6E',
  '9': '\u0B6F', '0': '\u0B66',
  '[': '\u0B05',           // ଅ
  ']': '\u0B4D\u0B30',     // ୍ର (ra-phala)
  '\\': '\u0B5F',          // ୟ
  '\'': 'REPH',            // ର୍ — SPECIAL: buffered
  '-': '-', '=': '=', ';': ';', ',': ',', '.': '.', '/': '/',
};

const SHIFT_SYMBOL = {
  '~': '\u0B03',                    // ଃ
  '!': '!',
  '@': '\u2018',                    // '
  '#': '\u2019',                    // '
  '$': '\u0B15\u0B4D\u0B37',       // କ୍ଷ
  '%': '%',
  '^': '\u0B0B',                    // ଋ
  '&': '\u0B70',
  '*': '*', '(': '(', ')': ')',
  '_': '\u0B3D',                    // ଽ
  '+': '+',
  '{': '\u0B43',                    // ୃ (matra)
  '}': '\u0B4D\u0B5F',             // ୍ୟ (ya-phala)
  '|': '\u0B1E',                    // ଞ
  '"': '"', ':': ':',
  '<': '\u0B0F',                    // ଏ
  '>': '\u0B10',                    // ଐ
  '?': '?',
};

// ── Classification ───────────────────────────────────────────────────

const VIRAMA = '\u0B4D';

const CONSONANTS = new Set([
  '\u0B15', '\u0B16', '\u0B17', '\u0B18', '\u0B19',
  '\u0B1A', '\u0B1B', '\u0B1C', '\u0B1D', '\u0B1E',
  '\u0B1F', '\u0B20', '\u0B21', '\u0B22', '\u0B23',
  '\u0B24', '\u0B25', '\u0B26', '\u0B27', '\u0B28',
  '\u0B2A', '\u0B2B', '\u0B2C', '\u0B2D', '\u0B2E',
  '\u0B2F', '\u0B30', '\u0B32', '\u0B33',
  '\u0B36', '\u0B37', '\u0B38', '\u0B39',
  '\u0B5C', '\u0B5F', '\u0B71',
]);

const MATRAS = new Set([
  '\u0B3E', '\u0B3F', '\u0B40', '\u0B41', '\u0B42',
  '\u0B43', '\u0B47', '\u0B48', '\u0B4C',
]);

// Vowel + matra → combined vowel (e.g. ଅ + ା → ଆ)
const VOWEL_COMBINE = {
  '\u0B05\u0B3E': '\u0B06',  // ଅ + ା → ଆ
  '\u0B07\u0B40': '\u0B08',  // ଇ + ୀ → ଈ
  '\u0B09\u0B42': '\u0B0A',  // ଉ + ୂ → ଊ
  '\u0B0F\u0B48': '\u0B10',  // ଏ + ୈ → ଐ
  '\u0B13\u0B4C': '\u0B14',  // ଓ + ୌ → ଔ
};

function isConsonant(ch) { return CONSONANTS.has(ch); }
function isMatra(ch) { return MATRAS.has(ch); }

// ── Extension ────────────────────────────────────────────────────────

export function createShreeLipiKeyboard(isEnabled) {
  return Extension.create({
    name: 'shreeLipiKeyboard',

    addProseMirrorPlugins() {
      let pendingEkar = false;  // େ waiting to be placed
      let pendingReph = false;  // ର୍ waiting to be placed

      function insert(view, text) {
        const { state } = view;
        const { from, to } = state.selection;
        view.dispatch(state.tr.insertText(text, from, to));
      }

      /**
       * Flush pending e-kar before a non-cluster character.
       * E-kar goes at the current cursor position (end of cluster).
       */
      function flushEkar(view) {
        if (pendingEkar) {
          insert(view, '\u0B47');
          pendingEkar = false;
        }
      }

      /**
       * Flush pending reph. Reph goes before the next consonant in Unicode,
       * so it's inserted right before the consonant.
       */
      function flushReph(view, beforeText) {
        if (pendingReph) {
          pendingReph = false;
          return '\u0B30\u0B4D' + beforeText;
        }
        return beforeText;
      }

      return [
        new Plugin({
          key: pluginKey,
          props: {
            handleKeyDown(view, event) {
              if (!isEnabled()) return false;
              if (event.ctrlKey || event.metaKey || event.altKey) return false;

              // ── Navigation / editing keys ──
              const NAV = [
                'Backspace', 'Delete', 'Enter', 'Tab', 'Escape',
                'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown',
                'Home', 'End', 'PageUp', 'PageDown',
              ];
              if (NAV.includes(event.key)) {
                if (event.key === 'Backspace' && (pendingEkar || pendingReph)) {
                  pendingEkar = false;
                  pendingReph = false;
                  event.preventDefault();
                  return true;
                }
                // Flush pending before nav
                flushEkar(view);
                if (pendingReph) { insert(view, '\u0B30\u0B4D'); pendingReph = false; }
                return false;
              }

              // ── Space ──
              if (event.key === ' ') {
                flushEkar(view);
                if (pendingReph) { insert(view, '\u0B30\u0B4D'); pendingReph = false; }
                // Let PM handle the space naturally
                return false;
              }

              // ── Resolve the character for this key ──
              const key = event.key;
              let char = null;

              if (event.shiftKey && SHIFT_SYMBOL[key]) {
                char = SHIFT_SYMBOL[key];
              } else if (event.shiftKey && UPPER[key]) {
                char = UPPER[key];
              } else if (event.shiftKey && UPPER[key.toUpperCase()]) {
                char = UPPER[key.toUpperCase()];
              } else if (!event.shiftKey && LOWER[key]) {
                char = LOWER[key];
              } else if (SYMBOL[key]) {
                char = SYMBOL[key];
              }

              if (char === null) {
                // Unknown key — flush pending and let browser handle
                flushEkar(view);
                if (pendingReph) { insert(view, '\u0B30\u0B4D'); pendingReph = false; }
                return false;
              }

              // ── SPECIAL: e-kar — buffer, don't insert ──
              if (char === 'EKAR') {
                pendingEkar = true;
                event.preventDefault();
                return true;
              }

              // ── SPECIAL: reph — buffer, don't insert ──
              if (char === 'REPH') {
                pendingReph = true;
                event.preventDefault();
                return true;
              }

              // ── VIRAMA (halant) — insert immediately, part of cluster ──
              if (char === VIRAMA || char === '\u0B4D\u200C') {
                // Halant keeps e-kar pending (cluster continues)
                insert(view, char);
                event.preventDefault();
                return true;
              }

              // ── Ra-phala (୍ର) or Ya-phala (୍ୟ) — insert immediately ──
              if (char.charAt(0) === VIRAMA && char.length > 1) {
                // These extend the cluster, keep e-kar pending
                insert(view, char);
                event.preventDefault();
                return true;
              }

              // ── CONSONANT — insert immediately ──
              const firstCh = char.charAt(0);
              if (isConsonant(firstCh)) {
                // If reph is pending, place it before this consonant
                const text = flushReph(view, char);
                insert(view, text);
                // e-kar stays pending (cluster may continue with halant)
                event.preventDefault();
                return true;
              }

              // ── MATRA — ends the cluster ──
              if (isMatra(firstCh)) {
                // If e-kar is pending and this is ୈ, treat as just ୈ (no double)
                if (pendingEkar && char === '\u0B48') {
                  pendingEkar = false;
                }
                // Flush e-kar BEFORE the matra
                flushEkar(view);
                // Flush reph too (shouldn't normally happen but safety)
                if (pendingReph) { insert(view, '\u0B30\u0B4D'); pendingReph = false; }

                // Vowel + matra combining (e.g. ଅ + ା → ଆ)
                const st = view.state;
                const pos = st.selection.from;
                if (pos > 0) {
                  const before = st.doc.textBetween(pos - 1, pos);
                  const combined = VOWEL_COMBINE[before + char];
                  if (combined) {
                    view.dispatch(st.tr.insertText(combined, pos - 1, pos));
                    event.preventDefault();
                    return true;
                  }
                }

                insert(view, char);
                event.preventDefault();
                return true;
              }

              // ── EVERYTHING ELSE (vowels, numbers, punctuation, etc.) ──
              flushEkar(view);
              if (pendingReph) { insert(view, '\u0B30\u0B4D'); pendingReph = false; }
              insert(view, char);
              event.preventDefault();
              return true;
            },
          },
        }),
      ];
    },
  });
}

export default createShreeLipiKeyboard;
