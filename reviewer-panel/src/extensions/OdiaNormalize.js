/**
 * OdiaNormalize — TipTap extension that cleans Odia text on paste.
 *
 * Reporters paste from legacy editors / WhatsApp forwards that contain
 * unassigned codepoints from the Oriya Unicode block (U+0B64 etc.) which
 * render as tofu boxes. We hook the ProseMirror plugin's
 * `transformPastedText` and `transformPastedHTML` props so the bad
 * codepoints get rewritten to their canonical Devanagari equivalents
 * (। / ॥) BEFORE they hit the editor state.
 *
 * Always-on. Independent of the Shree-Lipi keyboard toggle, since
 * legacy-source paste needs the same fix in English mode too.
 */

import { Extension } from '@tiptap/core';
import { Plugin, PluginKey } from '@tiptap/pm/state';
import { normalizeOdiaText } from '../utils/odiaText';

export const OdiaNormalize = Extension.create({
  name: 'odiaNormalize',

  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: new PluginKey('odiaNormalize'),
        props: {
          // Plain-text paste path (e.g. paste from a terminal, plain notepad)
          transformPastedText(text) {
            return normalizeOdiaText(text);
          },
          // Rich HTML paste path (e.g. paste from Word, Google Docs, web)
          // We walk the parsed slice's text nodes rather than regex'ing
          // the raw HTML so we don't accidentally munge attribute values.
          transformPasted(slice) {
            slice.content.descendants((node) => {
              if (node.isText && node.text) {
                const cleaned = normalizeOdiaText(node.text);
                if (cleaned !== node.text) {
                  // ProseMirror text nodes are immutable; mutate the
                  // private field — this is the documented escape hatch
                  // for in-place text fixups during paste transformation.
                  node.text = cleaned;
                }
              }
              return true;
            });
            return slice;
          },
        },
      }),
    ];
  },
});

export default OdiaNormalize;
