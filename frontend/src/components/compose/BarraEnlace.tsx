/**
 * Enlaces en el cuerpo del mensaje que se redacta: al pasar el puntero sobre un texto vinculado
 * (o al poner el cursor dentro) se muestra a dónde lleva, con las acciones Abrir, Cambiar y
 * Quitar; y Ctrl + clic (⌘ + clic en Mac) lo abre en otra pestaña, como en Word y Outlook.
 * Antes solo se veía el texto azul y subrayado, sin forma de saber ni de abrir el enlace.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { Editor } from '@tiptap/react';
import { abrirEnlace as abrir, normalizarEnlace } from './enlaces';

const ESPERA_OCULTAR_MS = 300;

function enlaceDe(destino: EventTarget | null, raiz: HTMLElement): HTMLAnchorElement | null {
  const a = destino instanceof Element ? destino.closest('a[href]') : null;
  return a instanceof HTMLAnchorElement && raiz.contains(a) ? a : null;
}

interface Visible { href: string; x: number; y: number; ancla: HTMLAnchorElement }

const ESTILO_BOTON: React.CSSProperties = {
  border: 'none', background: 'transparent', color: '#0f6cbd', cursor: 'pointer',
  fontSize: 12, padding: '2px 6px', borderRadius: 4, whiteSpace: 'nowrap',
};

export function BarraEnlace({ editor }: { editor: Editor | null }) {
  const [visible, setVisible] = useState<Visible | null>(null);
  const temporizador = useRef<number | null>(null);
  const sobreBarra = useRef(false);

  const cancelarOcultar = useCallback(() => {
    if (temporizador.current !== null) { window.clearTimeout(temporizador.current); temporizador.current = null; }
  }, []);
  const ocultarLuego = useCallback(() => {
    cancelarOcultar();
    temporizador.current = window.setTimeout(() => { if (!sobreBarra.current) setVisible(null); }, ESPERA_OCULTAR_MS);
  }, [cancelarOcultar]);
  const mostrar = useCallback((a: HTMLAnchorElement) => {
    cancelarOcultar();
    const r = a.getBoundingClientRect();
    const x = Math.max(8, Math.min(r.left, window.innerWidth - 380));
    setVisible({ href: a.getAttribute('href') || '', x, y: r.bottom + 4, ancla: a });
  }, [cancelarOcultar]);

  useEffect(() => {
    if (!editor || editor.isDestroyed) return;
    const raiz = editor.view.dom as HTMLElement;
    const alEntrar = (e: MouseEvent) => { const a = enlaceDe(e.target, raiz); if (a) mostrar(a); };
    const alSalir = (e: MouseEvent) => { if (enlaceDe(e.target, raiz)) ocultarLuego(); };
    // Ctrl + clic abre el enlace; el clic normal sigue colocando el cursor para escribir.
    const alPulsar = (e: MouseEvent) => {
      if (!(e.ctrlKey || e.metaKey) || e.button !== 0) return;
      const a = enlaceDe(e.target, raiz);
      if (!a) return;
      e.preventDefault();
      e.stopPropagation();
      abrir(a.getAttribute('href') || '');
    };
    const alMoverCursor = () => {
      if (!editor.isActive('link')) return;
      const { node } = editor.view.domAtPos(editor.state.selection.from);
      const a = enlaceDe(node.nodeType === Node.TEXT_NODE ? node.parentElement : node, raiz);
      if (a) mostrar(a);
    };
    const cerrar = () => setVisible(null);
    raiz.addEventListener('mouseover', alEntrar);
    raiz.addEventListener('mouseout', alSalir);
    raiz.addEventListener('click', alPulsar, true);
    editor.on('selectionUpdate', alMoverCursor);
    window.addEventListener('scroll', cerrar, true);
    return () => {
      raiz.removeEventListener('mouseover', alEntrar);
      raiz.removeEventListener('mouseout', alSalir);
      raiz.removeEventListener('click', alPulsar, true);
      editor.off('selectionUpdate', alMoverCursor);
      window.removeEventListener('scroll', cerrar, true);
      cancelarOcultar();
    };
  }, [editor, mostrar, ocultarLuego, cancelarOcultar]);

  if (!editor || !visible) return null;

  /** Selecciona el enlace completo para cambiarlo o quitarlo. */
  const conEnlaceSeleccionado = () => {
    if (!visible.ancla.isConnected) return null;
    const pos = editor.view.posAtDOM(visible.ancla, 0);
    return editor.chain().focus().setTextSelection(pos + 1).extendMarkRange('link');
  };
  const cambiar = () => {
    const nuevo = window.prompt('Dirección del enlace:', visible.href);
    if (nuevo === null) return;
    const url = normalizarEnlace(nuevo);
    const cadena = conEnlaceSeleccionado();
    if (!cadena) return;
    if (url) cadena.setLink({ href: url }).run(); else cadena.unsetLink().run();
    setVisible(null);
  };
  const quitar = () => { conEnlaceSeleccionado()?.unsetLink().run(); setVisible(null); };
  const mac = /Mac|iPhone|iPad/.test(navigator.platform);

  return (
    <div
      role="toolbar"
      aria-label="Enlace"
      onMouseEnter={() => { sobreBarra.current = true; cancelarOcultar(); }}
      onMouseLeave={() => { sobreBarra.current = false; ocultarLuego(); }}
      onMouseDown={e => e.preventDefault()}
      style={{
        position: 'fixed', left: visible.x, top: visible.y, zIndex: 9999, maxWidth: 372,
        background: '#fff', border: '1px solid #d2d0ce', borderRadius: 6,
        boxShadow: '0 2px 8px rgba(0,0,0,0.15)', padding: '6px 8px', fontSize: 12, color: '#323130',
      }}
    >
      <div title={visible.href} style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#0f6cbd' }}>
        {visible.href || '(enlace vacío)'}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 2, marginTop: 4 }}>
        <span style={{ color: '#605e5c', marginRight: 'auto', paddingRight: 8, whiteSpace: 'nowrap' }}>
          {mac ? '⌘ + clic para abrir' : 'Ctrl + clic para abrir'}
        </span>
        <button type="button" style={ESTILO_BOTON} onClick={() => abrir(visible.href)}>Abrir</button>
        <button type="button" style={ESTILO_BOTON} onClick={cambiar}>Cambiar</button>
        <button type="button" style={{ ...ESTILO_BOTON, color: '#a4262c' }} onClick={quitar}>Quitar</button>
      </div>
    </div>
  );
}
