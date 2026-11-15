/**
 * estiloCelda.ts — Lista blanca de estilos que se conservan en las tablas del redactor (13/11/2026).
 *
 * Las tablas copiadas de Excel, Hojas de cálculo o Word traen colores, negritas y bordes como
 * estilos. Aquí se decide qué se conserva y se devuelve SIEMPRE en una forma que entienden los
 * programas de correo: colores en hexadecimal, bordes lado por lado y medidas en píxeles.
 * Todo lo demás (posiciones, imágenes de fondo, `mso-*`, etc.) se descarta.
 */
const LADOS = ['top', 'right', 'bottom', 'left'] as const;
const VALOR_PELIGROSO = /url\s*\(|expression|javascript:|@import|[<>]/i;

/** `rgb(31, 78, 120)` → `#1f4e78` (hay programas de correo que no entienden `rgb()`). */
function colorHex(valor: string): string {
  return valor.replace(/rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)\s*\)/gi, (_t, r, g, b) =>
    '#' + [r, g, b].map((n) => Math.min(255, parseInt(n, 10)).toString(16).padStart(2, '0')).join(''));
}

/** Grosor del borde en píxeles: Excel usa `.5pt`, `1.0pt`, `1.5pt`… y medio punto no se ve igual en todas partes. */
function grosorPx(valor: string): string {
  const m = /^([\d.]+)(pt|px)$/i.exec(valor.trim());
  if (!m) return valor || '1px';
  const n = parseFloat(m[1]) * (m[2].toLowerCase() === 'pt' ? 4 / 3 : 1);
  return `${Math.max(1, Math.round(n))}px`;
}

function bordes(st: CSSStyleDeclaration): string {
  const lados = LADOS.map((lado) => {
    const trazo = st.getPropertyValue(`border-${lado}-style`);
    if (!trazo) return null;
    if (trazo === 'none' || trazo === 'hidden') return 'none';
    const color = colorHex(st.getPropertyValue(`border-${lado}-color`));
    const colorFinal = !color || /currentcolor|initial|inherit/i.test(color) ? '#000000' : color;
    return `${grosorPx(st.getPropertyValue(`border-${lado}-width`))} ${trazo} ${colorFinal}`;
  });
  if (lados.every((l) => l === null)) return '';
  if (lados.every((l) => l === lados[0])) return `border:${lados[0]};`;
  return lados.map((l, i) => (l === null ? '' : `border-${LADOS[i]}:${l};`)).join('');
}

export interface OpcionesEstilo {
  /** Bordes y alineación vertical: solo tienen sentido en celdas. */
  celda?: boolean;
  /** Conservar `text-align` (en las celdas del redactor lo lleva ya el atributo de alineación). */
  alineacion?: boolean;
}

/**
 * Devuelve solo los estilos permitidos de `css`, normalizados, o `null` si no queda ninguno.
 * Es idempotente: pasarle su propio resultado devuelve lo mismo.
 */
export function estiloPermitido(css: string | null | undefined, opciones: OpcionesEstilo = {}): string | null {
  if (!css || !css.trim()) return null;
  const st = document.createElement('span').style;
  st.cssText = css.replace(/windowtext/gi, '#000000');
  const valor = (propiedad: string): string => {
    const v = colorHex(st.getPropertyValue(propiedad).trim());
    return v && !VALOR_PELIGROSO.test(v) && !/^(initial|inherit|unset)$/i.test(v) ? v : '';
  };
  let salida = '';
  const fondo = valor('background-color');
  if (fondo && fondo !== 'transparent') salida += `background-color:${fondo};`;
  const color = valor('color');
  if (color) salida += `color:${color};`;
  const peso = valor('font-weight');
  if (peso && peso !== '400' && peso !== 'normal') salida += `font-weight:${peso};`;
  const cursiva = valor('font-style');
  if (cursiva && cursiva !== 'normal') salida += `font-style:${cursiva};`;
  const linea = valor('text-decoration-line');
  if (linea && linea !== 'none') salida += `text-decoration:${linea};`;
  const tamano = valor('font-size');
  if (tamano) salida += `font-size:${tamano};`;
  const fuente = valor('font-family');
  if (fuente) salida += `font-family:${fuente.replace(/"/g, "'")};`;
  if (opciones.alineacion) {
    const alineacion = valor('text-align');
    if (/^(left|right|center|justify)$/.test(alineacion)) salida += `text-align:${alineacion};`;
  }
  if (opciones.celda) {
    const vertical = valor('vertical-align');
    if (/^(top|middle|bottom|baseline)$/.test(vertical)) salida += `vertical-align:${vertical};`;
    const b = bordes(st);
    if (!VALOR_PELIGROSO.test(b)) salida += b;
  }
  return salida || null;
}
