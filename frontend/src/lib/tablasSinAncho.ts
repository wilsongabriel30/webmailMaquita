/**
 * tablasSinAncho.ts — Tablas pegadas desde Excel/Hojas de cálculo con ancho cero (05/11/2026).
 *
 * Al copiar una tabla de Excel o Google Sheets a Zimbra/Outlook, el HTML queda con
 * `<table style="table-layout: fixed; width: 0px">` y las columnas en `<col width>`.
 * Chrome respeta el ancho 0: todas las celdas se aplastan y el texto sale en letras
 * verticales (reporte de Gabriel Espinel, tesoreriaproyectos@). Aquí se cambia ese ancho
 * por «auto» (y lo mismo en celdas y filas) para que la tabla se dimensione por su contenido.
 * Solo toca la etiqueta de apertura de table/td/th/tr/col; no altera el resto del HTML.
 */
const ETIQUETAS = /<(table|td|th|tr|col|colgroup|div)\b[^>]*>/gi;
const ANCHO_CERO_ESTILO = /(^|[;\s"'])(width|min-width)\s*:\s*0(?:px|pt|em|%)?\s*(?=;|"|'|$)/gi;
const ANCHO_CERO_ATRIBUTO = /\swidth\s*=\s*(["']?)0(?:px)?\1(?=[\s>/])/gi;

export function corregirTablasSinAncho(html: string): string {
  if (!html || !/width\s*[:=]\s*["']?0/i.test(html)) return html;
  return html.replace(ETIQUETAS, (etiqueta) => {
    let salida = etiqueta.replace(ANCHO_CERO_ESTILO, '$1$2: auto');
    salida = salida.replace(ANCHO_CERO_ATRIBUTO, '');
    return salida;
  });
}
