/**
 * Barra flotante al seleccionar una imagen del cuerpo: alinearla a la izquierda, al centro o a
 * la derecha, como en Word. La alineación se guarda en el párrafo (`text-align`), que respetan
 * Outlook, Gmail y el resto de clientes de correo.
 */
import type { Editor } from '@tiptap/react';
import { BubbleMenu } from '@tiptap/react/menus';

type Alineacion = 'left' | 'center' | 'right';

const OPCIONES: { valor: Alineacion; titulo: string; lineas: string }[] = [
  { valor: 'left', titulo: 'Alinear a la izquierda', lineas: 'M4 6h16M4 10h10M4 14h16M4 18h10' },
  { valor: 'center', titulo: 'Centrar', lineas: 'M4 6h16M7 10h10M4 14h16M7 18h10' },
  { valor: 'right', titulo: 'Alinear a la derecha', lineas: 'M4 6h16M10 10h10M4 14h16M10 18h10' },
];

export function BarraImagen({ editor }: { editor: Editor | null }) {
  if (!editor) return null;
  const actual = (valor: Alineacion) =>
    editor.isActive({ textAlign: valor }) || (valor === 'left' && !['center', 'right'].some(v => editor.isActive({ textAlign: v })));
  return (
    <BubbleMenu
      editor={editor}
      pluginKey="barraImagen"
      shouldShow={({ editor: e }) => e.isEditable && e.isActive('image')}
      options={{ placement: 'top' }}
    >
      <div
        role="toolbar"
        aria-label="Alineación de la imagen"
        style={{ display: 'flex', gap: 2, padding: 3, background: '#fff', border: '1px solid #d2d0ce', borderRadius: 6, boxShadow: '0 2px 8px rgba(0,0,0,0.15)' }}
      >
        {OPCIONES.map(o => (
          <button
            key={o.valor}
            type="button"
            title={o.titulo}
            aria-label={o.titulo}
            aria-pressed={actual(o.valor)}
            onMouseDown={e => e.preventDefault()}
            onClick={() => editor.chain().focus().setTextAlign(o.valor).run()}
            style={{
              width: 28, height: 26, display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              border: 'none', borderRadius: 4, cursor: 'pointer',
              background: actual(o.valor) ? '#deecf9' : 'transparent',
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={actual(o.valor) ? '#0078d4' : '#323130'} strokeWidth="2" strokeLinecap="round">
              <path d={o.lineas} />
            </svg>
          </button>
        ))}
      </div>
    </BubbleMenu>
  );
}
