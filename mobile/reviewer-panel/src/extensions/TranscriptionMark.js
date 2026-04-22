import { Mark } from '@tiptap/core';

const TranscriptionMark = Mark.create({
  name: 'transcription',

  addAttributes() {
    return {};
  },

  parseHTML() {
    return [{ tag: 'span[data-transcription]' }];
  },

  renderHTML({ HTMLAttributes }) {
    return [
      'span',
      {
        ...HTMLAttributes,
        'data-transcription': '',
        style: 'color: #FA6C38; font-weight: 500;',
      },
      0,
    ];
  },
});

export default TranscriptionMark;
