/**
 * Firma del mensaje que se redacta. Se muestra debajo del cuerpo, fuera del editor, para
 * conservar su HTML tal cual; se puede retocar ahí mismo o quitar con la ×.
 *
 * Si se quita por error (con la × o borrando todo su contenido) queda el aviso «Se quitó la
 * firma · Deshacer» y Ctrl + Z la devuelve. Antes no había forma de recuperarla: Ctrl + Z no
 * hacía nada porque, al pulsar la ×, el foco quedaba fuera del editor. Por lo mismo, Ctrl + Z
 * con el foco fuera de un campo deshace ahora el último cambio del cuerpo del mensaje.
 */
import { useEffect, useRef, useState } from 'react';
import type { Editor } from '@tiptap/react';
import { sanitizeSignatureHtml } from '../../lib/sanitize';

interface Props { html: string; onCambiar: (html: string) => void; editor: Editor | null }

function estaVacia(nodo: HTMLElement): boolean {
  return !(nodo.textContent || '').trim() && !nodo.querySelector('img,table,hr');
}

function enCampoEditable(destino: EventTarget | null): boolean {
  return destino instanceof HTMLElement
    && (destino.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(destino.tagName));
}

export function FirmaRedaccion({ html, onCambiar, editor }: Props) {
  const [quitada, setQuitada] = useState('');
  const mostrada = useRef(html);
  useEffect(() => { if (html) mostrada.current = html; }, [html]);

  const quitar = () => { setQuitada(mostrada.current); onCambiar(''); };
  const restaurar = () => { onCambiar(quitada); setQuitada(''); };
  const pendiente = !html && !!quitada;

  useEffect(() => {
    const alTeclear = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey) || e.shiftKey || e.altKey || e.key.toLowerCase() !== 'z') return;
      if (enCampoEditable(e.target)) {
        // Dentro del cuerpo, el editor deshace lo suyo; la firma vuelve solo si ya no le queda nada.
        const enCuerpo = !!editor && !editor.isDestroyed && editor.view.dom.contains(e.target as Node);
        if (!pendiente || !enCuerpo || editor.can().undo()) return;
      }
      if (pendiente) { e.preventDefault(); onCambiar(quitada); setQuitada(''); return; }
      if (editor && !editor.isDestroyed && editor.can().undo()) { e.preventDefault(); editor.chain().focus().undo().run(); }
    };
    document.addEventListener('keydown', alTeclear);
    return () => document.removeEventListener('keydown', alTeclear);
  }, [editor, pendiente, quitada, onCambiar]);

  if (pendiente) {
    return (
      <div role="status" style={{ margin: '8px 24px 0', padding: '6px 10px', fontSize: 12, color: '#605e5c', background: '#faf9f8', border: '1px dashed #c8c6c4', borderRadius: 4, display: 'flex', alignItems: 'center', gap: 8 }}>
        <span>Se quitó la firma.</span>
        <button type="button" onClick={restaurar} title="Vuelve a poner la firma (Ctrl + Z)"
          style={{ border: 'none', background: 'none', color: '#0f6cbd', cursor: 'pointer', fontSize: 12, padding: 0, textDecoration: 'underline' }}>
          Deshacer
        </button>
        <button type="button" onClick={() => setQuitada('')} title="Dejar el mensaje sin firma" aria-label="Cerrar este aviso"
          style={{ marginLeft: 'auto', border: 'none', background: 'none', color: '#a19f9d', cursor: 'pointer', fontSize: 14, padding: '0 4px' }}>
          ×
        </button>
      </div>
    );
  }
  if (!html) return null;
  return (
    <div className="compose-signature" style={{ position: 'relative', padding: '0 24px', marginTop: 8, color: '#605e5c' }}>
      <button
        type="button"
        onClick={quitar}
        title="Quitar firma (se puede deshacer)"
        style={{ position: 'absolute', top: 0, right: 24, background: 'none', border: 'none', cursor: 'pointer', color: '#a19f9d', fontSize: 14, padding: '2px 6px', borderRadius: 3 }}
        onMouseEnter={(e) => { e.currentTarget.style.color = '#323130'; e.currentTarget.style.background = '#f3f2f1'; }}
        onMouseLeave={(e) => { e.currentTarget.style.color = '#a19f9d'; e.currentTarget.style.background = 'none'; }}
      >×</button>
      <div
        id="compose-signature-edit"
        contentEditable
        suppressContentEditableWarning
        onBlur={(e) => { if (estaVacia(e.currentTarget)) quitar(); else onCambiar(e.currentTarget.innerHTML); }}
        style={{ outline: 'none' }}
        title="Puede editar su firma aquí"
        dangerouslySetInnerHTML={{ __html: sanitizeSignatureHtml(html) }}
      />
    </div>
  );
}
