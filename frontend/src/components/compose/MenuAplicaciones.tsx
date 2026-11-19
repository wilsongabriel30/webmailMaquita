/**
 * MenuAplicaciones — «Aplicaciones» de la cinta de redacción (pedido de Dirección, 19/11/2026).
 *
 * En la bandeja, «Más aplicaciones» despliega Traductor, Corrector ortográfico y Plantillas de
 * correo; al redactar, el mismo botón solo mostraba un aviso. Aquí despliega el mismo menú,
 * aplicado al correo que se está escribiendo.
 *
 * El menú va en un portal con posición fija: la cinta se desplaza en horizontal y lo recortaría.
 */
import { useEffect, useRef, useState, type MouseEvent as ClicReact, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import type { Editor } from '@tiptap/react';
import { showToast } from '../common/Toast';

const PLANTILLA = '<p>Estimado/a,</p><p></p><p>Le saludo cordialmente.</p><p></p><p>Atentamente,</p>';

function textoParaTraducir(editor: Editor): string {
  const { from, to } = editor.state.selection;
  const seleccion = from !== to ? editor.state.doc.textBetween(from, to, '\n') : '';
  return (seleccion || editor.getText()).trim();
}

/** Envuelve el botón «Aplicaciones» de la cinta: el clic en él abre o cierra el menú. */
export function MenuAplicaciones({ editor, children }: { editor: Editor; children: ReactNode }) {
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const anclaRef = useRef<HTMLSpanElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const alternar = (e: ClicReact<HTMLSpanElement>) => {
    if (pos) { setPos(null); return; }
    const r = e.currentTarget.getBoundingClientRect();
    setPos({ top: r.bottom + 2, left: Math.max(4, Math.min(r.left, window.innerWidth - 248)) });
  };

  useEffect(() => {
    if (!pos) return;
    const fuera = (e: MouseEvent) => {
      const t = e.target as Node;
      if (!menuRef.current?.contains(t) && !anclaRef.current?.contains(t)) setPos(null);
    };
    const tecla = (e: KeyboardEvent) => { if (e.key === 'Escape') setPos(null); };
    document.addEventListener('mousedown', fuera);
    document.addEventListener('keydown', tecla);
    return () => { document.removeEventListener('mousedown', fuera); document.removeEventListener('keydown', tecla); };
  }, [pos]);

  const opciones: { nombre: string; icono: string; accion: () => void }[] = [
    {
      nombre: 'Traductor', icono: '\u{1F310}',
      accion: () => {
        const texto = textoParaTraducir(editor);
        if (!texto) { showToast('Escriba o seleccione el texto que quiere traducir'); return; }
        window.open('https://translate.google.com/?sl=auto&tl=es&text=' + encodeURIComponent(texto.slice(0, 2000)), '_blank', 'noopener,noreferrer');
      },
    },
    {
      nombre: 'Corrector ortográfico', icono: '\u{1F4DD}',
      accion: () => showToast('El corrector ortográfico del navegador está activo. Haga clic derecho en el texto subrayado para ver sugerencias.'),
    },
    {
      nombre: 'Plantillas de correo', icono: '\u{1F4CB}',
      accion: () => {
        editor.chain().focus().insertContent(PLANTILLA).run();
        showToast('Plantilla insertada en el correo');
      },
    },
  ];

  return (
    <>
      <span ref={anclaRef} className="inline-flex" onClick={alternar}>{children}</span>
      {pos && createPortal(
        <div ref={menuRef} role="menu" aria-label="Aplicaciones"
          style={{ position: 'fixed', top: pos.top, left: pos.left, zIndex: 9999 }}
          className="bg-white border border-[#e1dfdd] rounded shadow-lg min-w-[240px] py-1">
          {opciones.map((o) => (
            <button key={o.nombre} type="button" role="menuitem"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => { setPos(null); o.accion(); }}
              className="w-full text-left px-3 py-2 text-[13px] text-[#323130] flex items-center gap-2 hover:bg-[#f3f2f1]">
              <span aria-hidden="true">{o.icono}</span>
              <span>{o.nombre}</span>
            </button>
          ))}
        </div>,
        document.body,
      )}
    </>
  );
}
