import { Extension } from '@tiptap/core';

/**
 * FontSize — adds a `fontSize` attribute carried by TextStyle marks so
 * users with vision needs can bump body text up (or down) in the Odia
 * editor. Lives alongside TipTap's first-party FontFamily, which uses
 * the same TextStyle host.
 *
 * Persistence: TextStyle is part of the saved HTML, so font sizes
 * round-trip through updateStory like every other inline style.
 *
 * Commands:
 *   editor.commands.setFontSize('20px')
 *   editor.commands.unsetFontSize()
 */
export const FontSize = Extension.create({
  name: 'fontSize',

  addOptions() {
    return {
      types: ['textStyle'],
    };
  },

  addGlobalAttributes() {
    return [
      {
        types: this.options.types,
        attributes: {
          fontSize: {
            default: null,
            parseHTML: (element) => element.style.fontSize?.replace(/['"]+/g, '') || null,
            renderHTML: (attributes) => {
              if (!attributes.fontSize) return {};
              return { style: `font-size: ${attributes.fontSize}` };
            },
          },
        },
      },
    ];
  },

  addCommands() {
    return {
      setFontSize:
        (size) =>
        ({ chain }) =>
          chain().setMark('textStyle', { fontSize: size }).run(),
      unsetFontSize:
        () =>
        ({ chain }) =>
          chain().setMark('textStyle', { fontSize: null }).removeEmptyTextStyle().run(),
    };
  },
});

export default FontSize;
