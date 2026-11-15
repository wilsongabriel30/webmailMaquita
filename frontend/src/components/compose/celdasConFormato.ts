/**
 * celdasConFormato.ts — Celdas de tabla que conservan su formato en el redactor (13/11/2026).
 *
 * Las celdas de serie del editor solo guardan combinaciones, ancho y alineación: el color de fondo,
 * el color del texto, la negrita y los bordes de una tabla pegada de Excel se perdían al pegar.
 * Estas celdas añaden un atributo de estilo, limitado a la lista blanca de estiloCelda.ts, que se
 * conserva al pegar, al guardar el borrador y al enviar.
 *
 * `tablasParaCorreo` prepara las tablas para el envío: los programas de correo no conocen la hoja
 * de estilos del redactor, así que todo lo que se ve debe ir escrito en cada tabla y celda.
 */
import type { Attributes } from '@tiptap/core';
import { TableCell } from '@tiptap/extension-table-cell';
import { TableHeader } from '@tiptap/extension-table-header';
import { estiloPermitido } from './estiloCelda';
import { anchosDeColumnas, repartirAnchos } from './tablasPegadas';

const tablasConAnchos = new WeakSet<HTMLTableElement>();

/**
 * Al reabrir un borrador, el servidor ya quitó a las celdas su ancho (`colwidth`) y solo queda el
 * de las columnas (`<col>`): se vuelve a repartir a cada celda, una vez por tabla, para que la
 * tabla no se estire a todo el ancho.
 */
function completarAnchos(celda: HTMLElement): void {
  const tabla = celda.closest('table');
  if (!tabla || tablasConAnchos.has(tabla)) return;
  tablasConAnchos.add(tabla);
  repartirAnchos(tabla, anchosDeColumnas(tabla));
}

/** Atributos de serie de la celda + anchos recuperados de las columnas + formato de la lista blanca. */
function atributosConFormato(deSerie: Attributes | undefined): Attributes {
  const anchoDeSerie = deSerie?.colwidth?.parseHTML;
  return {
    ...deSerie,
    colwidth: {
      ...deSerie?.colwidth,
      parseHTML: (el: HTMLElement) => { completarAnchos(el); return anchoDeSerie ? anchoDeSerie(el) : null; },
    },
    formato: {
      default: null,
      parseHTML: (el: HTMLElement) => estiloPermitido(el.getAttribute('style'), { celda: true }),
      renderHTML: (atributos: { formato?: string | null }) => (atributos.formato ? { style: atributos.formato } : {}),
    },
  };
}

export const CeldaConFormato = TableCell.extend({
  addAttributes() {
    return atributosConFormato(this.parent?.());
  },
});

export const EncabezadoConFormato = TableHeader.extend({
  addAttributes() {
    return atributosConFormato(this.parent?.());
  },
});

const BORDE_POR_DEFECTO = 'border:1px solid #d0d0d0;';

/** Pone `css` DELANTE del estilo que ya tenga el elemento: lo propio de la celda siempre gana. */
function anteponer(el: Element, css: string): void {
  if (!css) return;
  el.setAttribute('style', css + (el.getAttribute('style') || ''));
}

const tieneBorde = (el: Element) => /(^|;)\s*border/i.test(el.getAttribute('style') || '');

/** Estilos en línea para que la tabla se vea en el correo recibido igual que en el redactor. */
export function tablasParaCorreo(html: string): string {
  if (!html || html.indexOf('<table') === -1) return html;
  try {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    doc.querySelectorAll('table').forEach((tabla) => {
      const celdas = Array.from(tabla.querySelectorAll('td,th'));
      // Una tabla que trae sus propios bordes (Excel) se respeta tal cual, también donde no tiene.
      const bordesPropios = celdas.some(tieneBorde);
      anteponer(tabla, 'border-collapse:collapse;' + (bordesPropios ? '' : BORDE_POR_DEFECTO));
      celdas.forEach((celda) => {
        const anchos = (celda.getAttribute('colwidth') || '').split(',').map((a) => parseInt(a, 10));
        const ancho = anchos.every((a) => a > 0) ? `width:${anchos.reduce((s, a) => s + a, 0)}px;` : '';
        const encabezado = celda.tagName === 'TH' ? 'background:#f3f2f1;font-weight:600;text-align:left;' : '';
        // El estilo propio se reescribe en la forma que entienden los programas de correo (colores
        // en hexadecimal, bordes lado por lado): al pasar por el editor el navegador lo abrevia.
        const propio = estiloPermitido(celda.getAttribute('style'), { celda: true, alineacion: true }) || '';
        celda.setAttribute('style', (bordesPropios ? '' : BORDE_POR_DEFECTO) + 'padding:6px 8px;' + ancho + encabezado + propio);
        // El editor envuelve el texto de cada celda en un párrafo; sin esto, el correo recibido
        // muestra las filas mucho más altas por el margen de los párrafos.
        Array.from(celda.children).filter((h) => h.tagName === 'P').forEach((p) => anteponer(p, 'margin:0;'));
      });
    });
    return doc.body.innerHTML;
  } catch {
    return html;
  }
}
