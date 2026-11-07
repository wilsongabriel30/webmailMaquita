/**
 * Correo citado (reenvío o respuesta) que NO se puede modificar pero sí marcar (07/11/2026).
 *
 * El texto reenviado sigue bloqueado para prevenir fraudes (nadie puede cambiar lo que dijo
 * otra persona), pero quien reenvía puede resaltar o subrayar partes para señalar lo importante.
 * Cada marca solo ENVUELVE texto existente; antes de aceptar el cambio se compara el texto
 * completo antes y después: si cambiara una sola letra, la marca no se aplica.
 */
import { useCallback, useRef, type ReactNode } from 'react';
import { sanitizeHtml } from '../../lib/sanitize';

type Tipo = 'resaltado' | 'subrayado';
const CLASE = 'maq-marca';

function nodosDeTexto(raiz: HTMLElement, rango: Range): Text[] {
  // Partir los extremos para marcar exactamente lo seleccionado.
  if (rango.startContainer.nodeType === Node.TEXT_NODE && rango.startOffset > 0) {
    const t = rango.startContainer as Text;
    if (rango.startOffset < t.length) {
      const resto = t.splitText(rango.startOffset);
      if (rango.endContainer === t) rango.setEnd(resto, rango.endOffset - t.length);
      rango.setStart(resto, 0);
    }
  }
  if (rango.endContainer.nodeType === Node.TEXT_NODE) {
    const t = rango.endContainer as Text;
    if (rango.endOffset > 0 && rango.endOffset < t.length) t.splitText(rango.endOffset);
  }
  const lista: Text[] = [];
  const paseo = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT);
  for (let n = paseo.nextNode(); n; n = paseo.nextNode()) {
    const t = n as Text;
    if (!t.data.trim() || !rango.intersectsNode(t)) continue;
    if (t === rango.startContainer && rango.startOffset >= t.length) continue;
    if (t === rango.endContainer && rango.endOffset === 0) continue;
    lista.push(t);
  }
  return lista;
}

function envolver(t: Text, tipo: Tipo) {
  const el = document.createElement(tipo === 'subrayado' ? 'u' : 'span');
  el.className = `${CLASE} ${CLASE}-${tipo}`;
  if (tipo === 'resaltado') el.setAttribute('style', 'background-color:#fff100');
  t.parentNode?.insertBefore(el, t);
  el.appendChild(t);
}

function quitarMarcas(raiz: HTMLElement, rango: Range | null) {
  raiz.querySelectorAll<HTMLElement>(`.${CLASE}`).forEach(el => {
    if (rango && !rango.intersectsNode(el)) return;
    const padre = el.parentNode;
    if (!padre) return;
    while (el.firstChild) padre.insertBefore(el.firstChild, el);
    padre.removeChild(el);
  });
  raiz.normalize();
}

export function CitaMarcable({ html, onCambiar }: { html: string; onCambiar: (html: string) => void }) {
  const ref = useRef<HTMLDivElement>(null);

  const rangoDentro = useCallback((): Range | null => {
    const sel = window.getSelection();
    const raiz = ref.current;
    if (!sel || !sel.rangeCount || !raiz) return null;
    const r = sel.getRangeAt(0);
    if (r.collapsed || !raiz.contains(r.commonAncestorContainer)) return null;
    return r;
  }, []);

  const aplicar = useCallback((accion: Tipo | 'quitar') => {
    const raiz = ref.current;
    if (!raiz) return;
    const rango = rangoDentro();
    if (!rango && accion !== 'quitar') return;
    // Se trabaja sobre una copia: el DOM visible no se toca hasta pasar la comprobación.
    const copia = raiz.cloneNode(true) as HTMLDivElement;
    let rangoCopia: Range | null = null;
    if (rango) {
      const ruta = (n: Node) => { const p: number[] = []; for (let x: Node | null = n; x && x !== raiz; x = x.parentNode) p.unshift([...(x.parentNode?.childNodes || [])].indexOf(x as ChildNode)); return p; };
      const ir = (p: number[]) => p.reduce<Node>((n, i) => n.childNodes[i], copia);
      rangoCopia = document.createRange();
      rangoCopia.setStart(ir(ruta(rango.startContainer)), rango.startOffset);
      rangoCopia.setEnd(ir(ruta(rango.endContainer)), rango.endOffset);
    }
    const antes = copia.textContent;
    if (accion === 'quitar') quitarMarcas(copia, rangoCopia);
    else nodosDeTexto(copia, rangoCopia!).forEach(t => envolver(t, accion));
    if (copia.textContent !== antes) return;  // jamás se acepta un cambio de texto
    window.getSelection()?.removeAllRanges();
    onCambiar(copia.innerHTML);
  }, [onCambiar, rangoDentro]);

  const boton = (texto: ReactNode, titulo: string, accion: Tipo | 'quitar') => (
    <button
      type="button"
      title={titulo}
      aria-label={titulo}
      onMouseDown={e => { e.preventDefault(); aplicar(accion); }}
      style={{ border: '1px solid #d2d0ce', background: '#fff', borderRadius: 4, padding: '2px 8px', fontSize: 12, cursor: 'pointer', color: '#323130' }}
    >{texto}</button>
  );

  return (
    <div style={{ padding: '0 24px 16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', fontSize: 12, color: '#605e5c', margin: '4px 0 6px' }}>
        <span>El correo citado no se puede modificar. Seleccione un texto para marcarlo:</span>
        {boton(<span style={{ background: '#fff100', padding: '0 3px' }}>Resaltar</span>, 'Resaltar el texto seleccionado', 'resaltado')}
        {boton(<u>Subrayar</u>, 'Subrayar el texto seleccionado', 'subrayado')}
        {boton('Quitar marcas', 'Quitar las marcas del texto seleccionado (o todas si no hay selección)', 'quitar')}
      </div>
      <div
        ref={ref}
        contentEditable={false}
        className="compose-quoted-content"
        style={{ color: '#605e5c', userSelect: 'text', cursor: 'text', fontSize: 13 }}
        dangerouslySetInnerHTML={{ __html: sanitizeHtml(html) }}
      />
    </div>
  );
}
