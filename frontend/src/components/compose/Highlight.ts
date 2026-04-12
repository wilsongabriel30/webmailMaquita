import { Extension } from '@tiptap/core';

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    highlight: {
      setHighlight: (color?: string) => ReturnType;
      unsetHighlight: () => ReturnType;
      toggleHighlight: (color?: string) => ReturnType;
    };
  }
}

const DEFAULT_HIGHLIGHT = '#fff100';

export const Highlight = Extension.create({
  name: 'highlight',

  addOptions() {
    return {
      types: ['textStyle'],
      defaultColor: DEFAULT_HIGHLIGHT,
    };
  },

  addGlobalAttributes() {
    return [{
      types: this.options.types,
      attributes: {
        backgroundColor: {
          default: null,
          parseHTML: (el) => el.style.backgroundColor?.replace(/['"]+/g, '') || null,
          renderHTML: (attrs) => {
            if (!attrs.backgroundColor) return {};
            return { style: `background-color: ${attrs.backgroundColor}` };
          },
        },
      },
    }];
  },

  addCommands() {
    return {
      setHighlight: (color?: string) => ({ chain }) =>
        chain().setMark('textStyle', { backgroundColor: color || this.options.defaultColor }).run(),
      unsetHighlight: () => ({ chain }) =>
        chain().setMark('textStyle', { backgroundColor: null }).removeEmptyTextStyle().run(),
      toggleHighlight: (color?: string) => ({ editor, commands }) => {
        const current = editor.getAttributes('textStyle')?.backgroundColor;
        if (current) return commands.unsetHighlight();
        return commands.setHighlight(color || this.options.defaultColor);
      },
    };
  },
});
