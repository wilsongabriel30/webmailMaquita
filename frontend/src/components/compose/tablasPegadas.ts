/**
 * tablasPegadas.ts — Tablas copiadas de Excel / Hojas de cálculo / Word que conservan su formato (13/11/2026).
 *
 * Excel no pone los colores en cada celda: los declara en un bloque `<style>` con clases
 * (`.xl65 {background:yellow; font-weight:700; border:.5pt solid windowtext}`) y los anchos en
 * `<col width>`. El redactor solo entiende lo que cada celda lleva escrito en sí misma, y los
 * programas de correo ignoran `<style>`. Por eso, al pegar, aquí se resuelven esas clases y se
 * escribe el resultado en cada celda (solo los estilos de la lista blanca de estiloCelda.ts).
 *
 * Se usa en `editorProps.transformPastedHTML` del redactor. Si algo falla, devuelve el HTML intacto.
 */
import { estiloPermitido } from './estiloCelda';

interface Reglas { porEtiqueta: Map<string, string>; porClase: Map<string, string> }

/** Lee las reglas sencillas (`td`, `.clase`, `td.clase`) de los `<style>` que vienen en el portapapeles. */
function leerReglas(doc: Document): Reglas {
  const reglas: Reglas = { porEtiqueta: new Map(), porClase: new Map() };
  const texto = Array.from(doc.querySelectorAll('style')).map((s) => s.textContent || '').join('\n')
    .replace(/<!--|-->/g, ' ').replace(/\/\*[\s\S]*?\*\//g, ' ');
  const bloque = /([^{}]+)\{([^{}]*)\}/g;
  let m: RegExpExecArray | null;
  while ((m = bloque.exec(texto))) {
    const declaraciones = m[2].trim();
    if (!declaraciones) continue;
    for (const selector of m[1].split(',')) {
      const s = /^([a-z0-9]*)(?:\.([\w-]+))?$/i.exec(selector.trim());
      if (!s || (!s[1] && !s[2])) continue;
      const mapa = s[2] ? reglas.porClase : reglas.porEtiqueta;
      const clave = (s[2] || s[1]).toLowerCase();
      mapa.set(clave, `${mapa.get(clave) || ''};${declaraciones}`);
    }
  }
  return reglas;
}

/** Estilos que le tocan a un elemento: los de su etiqueta, los de sus clases, sus atributos antiguos y su `style`. */
function cssDe(el: Element, reglas: Reglas, conEtiqueta: boolean): string {
  const partes: string[] = [];
  if (conEtiqueta) partes.push(reglas.porEtiqueta.get(el.tagName.toLowerCase()) || '');
  (el.getAttribute('class') || '').split(/\s+/).filter(Boolean)
    .forEach((c) => partes.push(reglas.porClase.get(c.toLowerCase()) || ''));
  const atributo = (nombre: string, propiedad: string) => {
    const v = el.getAttribute(nombre);
    if (v && /^[#\w ,.()%-]+$/.test(v)) partes.push(`${propiedad}:${v}`);
  };
  atributo('bgcolor', 'background-color');
  atributo('align', 'text-align');
  atributo('valign', 'vertical-align');
  if (el.tagName === 'FONT') { atributo('color', 'color'); atributo('face', 'font-family'); }
  partes.push(el.getAttribute('style') || '');
  return partes.join(';');
}

function enPixeles(valor: string | null): number {
  const m = /^\s*([\d.]+)\s*(px|pt)?\s*$/i.exec(valor || '');
  if (!m) return 0;
  return Math.round(parseFloat(m[1]) * ((m[2] || 'px').toLowerCase() === 'pt' ? 4 / 3 : 1));
}

/** Anchos de las columnas según `<col width>` (respetando `span`), en píxeles. */
export function anchosDeColumnas(tabla: HTMLTableElement): number[] {
  const anchos: number[] = [];
  tabla.querySelectorAll(':scope > col, :scope > colgroup > col').forEach((col) => {
    const ancho = enPixeles(col.getAttribute('width')) || enPixeles((col as HTMLElement).style.width);
    const repeticiones = Math.max(1, parseInt(col.getAttribute('span') || '1', 10) || 1);
    for (let i = 0; i < repeticiones; i++) anchos.push(ancho);
  });
  return anchos;
}

/** Escribe en cada celda el ancho de su(s) columna(s), teniendo en cuenta las celdas combinadas. */
export function repartirAnchos(tabla: HTMLTableElement, anchos: number[]): void {
  if (!anchos.some((a) => a > 0)) return;
  let ocupadas: number[] = [];
  Array.from(tabla.rows).forEach((fila) => {
    let columna = 0;
    Array.from(fila.cells).forEach((celda) => {
      while (ocupadas[columna] > 0) columna++;
      const ancho = Math.max(1, celda.colSpan || 1);
      const propios = anchos.slice(columna, columna + ancho);
      if (propios.length === ancho && propios.every((a) => a > 0)) {
        celda.setAttribute('colwidth', propios.map((a) => Math.max(25, a)).join(','));
      }
      for (let i = 0; i < ancho; i++) ocupadas[columna + i] = Math.max(1, celda.rowSpan || 1);
      columna += ancho;
    });
    ocupadas = ocupadas.map((n) => Math.max(0, (n || 0) - 1));
  });
}

function ponerEstilo(el: Element, estilo: string | null): void {
  if (estilo) el.setAttribute('style', estilo);
  else el.removeAttribute('style');
}

/** `editorProps.transformPastedHTML`: deja en cada celda (y en su texto) el formato que traía la tabla. */
export function tablasPegadasConEstilos(html: string): string {
  if (!html || !/<table[\s>]/i.test(html)) return html;
  try {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const reglas = leerReglas(doc);
    doc.querySelectorAll('table').forEach((tabla) => {
      repartirAnchos(tabla, anchosDeColumnas(tabla));
      tabla.querySelectorAll('td, th').forEach((celda) => {
        ponerEstilo(celda, estiloPermitido(cssDe(celda, reglas, true), { celda: true, alineacion: true }));
      });
      // Texto con formato propio dentro de una celda (una palabra en rojo, un trozo en negrita…).
      tabla.querySelectorAll('span, font, p, div, a, b, i, u').forEach((el) => {
        if (!el.hasAttribute('class') && !el.hasAttribute('style') && el.tagName !== 'FONT') return;
        const estilo = estiloPermitido(cssDe(el, reglas, false));
        if (el.tagName !== 'FONT') { ponerEstilo(el, estilo); return; }
        const tramo = doc.createElement('span');
        while (el.firstChild) tramo.appendChild(el.firstChild);
        ponerEstilo(tramo, estilo);
        el.replaceWith(tramo);
      });
    });
    // El editor, al leer lo pegado, vuelve a aplicar las reglas de `<style>` ENCIMA de lo que cada
    // elemento lleva escrito (y la regla general `td {border:none; color:black}` de Excel borraría
    // lo recién resuelto). Ya están resueltas arriba, así que la hoja de estilos se retira.
    doc.querySelectorAll('style').forEach((hoja) => hoja.remove());
    return doc.documentElement.outerHTML;
  } catch {
    return html;
  }
}
