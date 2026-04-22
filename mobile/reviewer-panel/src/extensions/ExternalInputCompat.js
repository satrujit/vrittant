/**
 * ExternalInputCompat — TipTap extension for legacy keyboard tools (Akriti, Shree-Lipi, etc.)
 *
 * These tools inject characters via Windows API hooks (SendInput / WM_CHAR)
 * which may bypass ProseMirror's standard input handling. ProseMirror sees
 * the DOM change but can't reconcile it with its internal state, so it
 * reverts the change — making it look like "nothing happened".
 *
 * This extension:
 * 1. Listens for `beforeinput` events and manually routes text insertion
 *    through ProseMirror's transaction system.
 * 2. As a fallback, runs a MutationObserver that detects text changes
 *    ProseMirror missed and force-flushes the DOMObserver.
 */
import { Extension } from '@tiptap/core';
import { Plugin, PluginKey } from '@tiptap/pm/state';

const pluginKey = new PluginKey('externalInputCompat');

const ExternalInputCompat = Extension.create({
  name: 'externalInputCompat',

  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: pluginKey,

        props: {
          handleDOMEvents: {
            /**
             * Catch text insertion from external keyboard hooks.
             * We only intercept non-ASCII characters (Odia Unicode U+0B00–0B7F,
             * other Indic scripts, Akriti extended-ASCII mapped chars, etc.)
             * to avoid breaking normal Latin typing and PM input rules.
             */
            beforeinput(view, event) {
              if (
                (event.inputType === 'insertText' ||
                  event.inputType === 'insertCompositionText') &&
                event.data
              ) {
                const code = event.data.codePointAt(0);
                // Non-ASCII → likely from Akriti / Shree-Lipi / OS IME
                if (code > 127) {
                  const { state } = view;
                  const { from, to } = state.selection;
                  const tr = state.tr.insertText(event.data, from, to);
                  view.dispatch(tr);
                  event.preventDefault();
                  return true;
                }
              }
              return false;
            },
          },
        },

        view(editorView) {
          // Fallback: MutationObserver that force-flushes PM's DOMObserver
          // when external tools modify the DOM directly.
          let pending = false;

          const flush = () => {
            pending = false;
            try {
              // domObserver.flush() forces PM to re-read DOM mutations
              if (editorView.domObserver) {
                editorView.domObserver.flush();
              }
            } catch {
              // Swallow — view may have been destroyed
            }
          };

          const observer = new MutationObserver(() => {
            if (!pending) {
              pending = true;
              requestAnimationFrame(flush);
            }
          });

          observer.observe(editorView.dom, {
            characterData: true,
            childList: true,
            subtree: true,
          });

          return {
            destroy() {
              observer.disconnect();
            },
          };
        },
      }),
    ];
  },
});

export default ExternalInputCompat;
