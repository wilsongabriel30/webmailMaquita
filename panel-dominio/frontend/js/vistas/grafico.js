// Gráfico de línea de las últimas 24 horas en SVG, sin bibliotecas ni estilos en línea (la política de seguridad del
// portal no los admite): los colores vienen de estilos.css por clase. Un hueco en los datos corta la línea.
const SVG = 'http://www.w3.org/2000/svg';
const ANCHO = 640, ALTO = 170, IZQ = 44, DER = 8, ARR = 10, ABA = 22;

function nodo(etiqueta, atributos, texto) {
  const n = document.createElementNS(SVG, etiqueta);
  for (const [k, v] of Object.entries(atributos || {})) n.setAttribute(k, String(v));
  if (texto !== undefined) n.textContent = texto;
  return n;
}

const redondo = (v) => (v >= 100 ? Math.round(v) : Math.round(v * 10) / 10).toLocaleString('es');

/** puntos: [[segundos, valor | null], …]; `tope`: límite que se dibuja como línea discontinua (o null). */
export function grafico(titulo, puntos, unidad, tope) {
  const ahora = Date.now() / 1000, desde = ahora - 86400;
  const valores = puntos.map(p => p[1]).filter(v => typeof v === 'number');
  // El límite solo se dibuja si el uso se le acerca: si no, aplastaría la línea contra el suelo.
  if (tope && Math.max(0, ...valores) < tope * 0.5) tope = null;
  const maximo = Math.max(1, ...valores, tope || 0) * 1.1;
  const x = (t) => IZQ + ((t - desde) / 86400) * (ANCHO - IZQ - DER);
  const y = (v) => ARR + (1 - v / maximo) * (ALTO - ARR - ABA);
  const ultimo = valores.length ? valores[valores.length - 1] : null;
  const resumen = valores.length ? `${titulo}: ahora ${redondo(ultimo)} ${unidad}, máximo ${redondo(Math.max(...valores))} ${unidad}` : `${titulo}: sin datos`;
  const svg = nodo('svg', { viewBox: `0 0 ${ANCHO} ${ALTO}`, class: 'grafico', role: 'img', 'aria-label': resumen });
  svg.append(nodo('title', null, resumen));
  for (const fraccion of [0, 0.5, 1]) {
    const v = (maximo / 1.1) * fraccion;
    svg.append(nodo('line', { x1: IZQ, x2: ANCHO - DER, y1: y(v), y2: y(v), class: 'eje' }),
      nodo('text', { x: IZQ - 4, y: y(v) + 4, 'text-anchor': 'end' }, redondo(v)));
  }
  for (const horas of [24, 18, 12, 6, 0]) {
    const t = ahora - horas * 3600;
    svg.append(nodo('text', { x: x(t), y: ALTO - 6, 'text-anchor': horas === 24 ? 'start' : horas === 0 ? 'end' : 'middle' },
      horas ? `−${horas} h` : 'ahora'));
  }
  if (tope) svg.append(nodo('line', { x1: IZQ, x2: ANCHO - DER, y1: y(tope), y2: y(tope), class: 'tope' }),
    nodo('text', { x: ANCHO - DER, y: y(tope) - 3, 'text-anchor': 'end', class: 'tope-texto' }, `límite ${redondo(tope)} ${unidad}`));
  let tramo = [];
  const cerrar = () => {
    if (tramo.length === 1) svg.append(nodo('circle', { cx: tramo[0][0], cy: tramo[0][1], r: 2, class: 'punto' }));
    if (tramo.length > 1) svg.append(nodo('polyline', { points: tramo.map(p => p.join(',')).join(' '), class: 'linea' }));
    tramo = [];
  };
  let anterior = null;
  for (const [t, v] of puntos) {
    if (t < desde) continue;
    if (typeof v !== 'number' || (anterior !== null && t - anterior > 900)) cerrar();  // hueco: la medición faltó
    if (typeof v === 'number') tramo.push([Math.round(x(t) * 10) / 10, Math.round(y(v) * 10) / 10]);
    anterior = t;
  }
  cerrar();
  return svg;
}
