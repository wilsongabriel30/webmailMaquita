import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import Link from '@tiptap/extension-link';
import Placeholder from '@tiptap/extension-placeholder';
import TextAlign from '@tiptap/extension-text-align';
import { TextStyle } from '@tiptap/extension-text-style';
import { Color } from '@tiptap/extension-color';
import { useEffect } from 'react';

interface Props { content: string; onChange: (html: string) => void; }

export default function RichTextEditor({ content, onChange }: Props) {
  const editor = useEditor({
    extensions: [
      StarterKit, Underline, Link.configure({ openOnClick: false }),
      Placeholder.configure({ placeholder: 'Escribe aqui...' }),
      TextAlign.configure({ types: ['heading', 'paragraph'] }),
      TextStyle, Color,
    ],
    content,
    onUpdate: ({ editor: e }) => onChange(e.getHTML()),
    editorProps: { attributes: { class: 'outline-none min-h-[150px] px-4 py-3 text-[14px] text-[#323130]' } },
  });

  useEffect(() => {
    if (!editor) return;
    if (!content || content === '<p></p>') {
      if (editor.getHTML() !== '<p></p>') editor.commands.clearContent();
      return;
    }
    if (!editor.getHTML().includes(content.slice(0, 20))) editor.commands.setContent(content);
  }, [content, editor]);

  if (!editor) return null;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-px px-2 py-1 border-b border-[#edebe9] bg-[#faf9f8] flex-wrap">
        <button onClick={() => editor.chain().focus().toggleBold().run()} className={`w-7 h-7 rounded flex items-center justify-center text-[12px] ${editor.isActive('bold') ? 'bg-[#e1dfdd] text-[#0078d4]' : 'text-[#605e5c] hover:bg-[#e1dfdd]'}`} title="Negrita"><b>N</b></button>
        <button onClick={() => editor.chain().focus().toggleItalic().run()} className={`w-7 h-7 rounded flex items-center justify-center text-[12px] ${editor.isActive('italic') ? 'bg-[#e1dfdd] text-[#0078d4]' : 'text-[#605e5c] hover:bg-[#e1dfdd]'}`} title="Cursiva"><i>K</i></button>
        <button onClick={() => editor.chain().focus().toggleUnderline().run()} className={`w-7 h-7 rounded flex items-center justify-center text-[12px] ${editor.isActive('underline') ? 'bg-[#e1dfdd] text-[#0078d4]' : 'text-[#605e5c] hover:bg-[#e1dfdd]'}`} title="Subrayado"><u>S</u></button>
      </div>
      <EditorContent editor={editor} className="flex-1 overflow-y-auto" />
    </div>
  );
}
