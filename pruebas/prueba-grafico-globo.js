/* El globo del gráfico: qué barra hay bajo el cursor, cómo se escribe el valor,
   qué gráficos se atienden (columnas de una serie) y que el globo aparece,
   se mueve con el ratón y desaparece al salir. */

const geo = {
    canvasW: 600, canvasH: 429, trueW: 500, trueH: 260,
    gutter: { left: 90, top: 50 }, gapWidth: 50,
    valores: [0.58, 0.63, 0.25, 0.87], categorias: ['Esmeraldas', 'Manabí', 'Guayas-El Oro', 'Los Ríos'],
    max: 1, min: 0, nombre: 'ÍNDICE IMPLEMENTACIÓN', color: 'rgb(19,131,177)', formato: '0%'
};

const oyentes = {};
const creados = [];
function nuevoElemento() {
    const hijos = [];
    return {
        style: { cssText: '', left: '', top: '' }, hijos: hijos, className: '', textContent: '',
        set innerHTML(v) { hijos.length = 0; }, get innerHTML() { return ''; },
        appendChild: (h) => hijos.push(h), parentNode: null,
        getBoundingClientRect: () => ({ left: 40, top: 176, width: 1400, height: 780 })
    };
}
const tablero = nuevoElemento();
const tela = { getBoundingClientRect: () => ({ left: 40, top: 176, width: 1400, height: 780 }) };
// gráfico colocado en la hoja (mm) y su equivalencia con el lienzo del gráfico
const grafico = { Id: 'g1', x: 100, y: 50, extX: 158.75, extY: 113.5,
                  chart: {}, chartObj: {} };
let logico = { X: 0, Y: 0 };
const ws = {
    ConvertXYToLogic: (x, y) => logico,
    objectRender: { getDrawingObjects: () => [{ graphicObject: grafico }] }
};
const ventana = {
    Asc: { editor: { wb: { getWorksheet: () => ws } } },
    SSE: { getController: () => ({ documentHolder: { cmpEl: [tablero] } }) },
    document: {
        body: tablero,
        getElementById: (id) => (id === 'ws-canvas-graphic' ? tela : null),
        querySelector: () => tela,
        createElement: () => { const e = nuevoElemento(); creados.push(e); return e; },
        addEventListener: (tipo, fn) => { (oyentes[tipo] = oyentes[tipo] || []).push(fn); }
    }
};
global.window = global;
global.document = { querySelectorAll: (s) => (s === 'iframe' ? [{ contentWindow: ventana }] : []) };
global.setInterval = () => 1;
const buzon = [];
window.MaquitaDiagnostico = { contar: (m, d) => buzon.push([m, d]) };

const B = process.env.MODULOS || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';
require(B + 'editor-ventanas.js');
require(B + 'editor-grafico-globo.js');

const G = window.MaquitaGraficoGlobo;
let rojo = 0;
const bien = (r, q) => { if (!r) rojo++; console.log((r ? 'OK  ' : 'MAL ') + q); };
console.log();
bien(G._estado.activo === true && !!oyentes.mousemove, 'se engancha al movimiento del ratón en el editor');

// ── cómo se escribe el valor ──
bien(G.formatear(0.6333333, '0%') === '63%', 'con formato 0% el valor se escribe «63%», como en la barra');
bien(G.formatear(0.6333333, '0.0%') === '63.3%', 'y respeta los decimales del formato');
bien(G.formatear(1234.5, '') === '1234.5', 'sin formato, el número tal cual');
bien(G.formatear(null, '0%') === '', 'sin valor, nada');

// ── qué barra hay bajo el punto (píxeles del lienzo del gráfico) ──
const paso = geo.trueW / 4;               // 125
const centro0 = 90 + paso * 0.5;          // 152.5
const base = 50 + 260;                    // el eje, abajo
bien(G.barraEn(geo, centro0, base - 10) === 0, 'justo encima del eje, sobre la primera barra: es la 0');
bien(G.barraEn(geo, centro0, 50 + 260 * (1 - 0.58) + 5) === 0, 'cerca de la cima de esa barra: sigue siendo la 0');
bien(G.barraEn(geo, centro0, 50 + 260 * (1 - 0.58) - 15) === -1, 'por ENCIMA de la barra ya no (ahí no hay barra)');
bien(G.barraEn(geo, 90 + paso * 1.5, base - 10) === 1, 'la segunda barra es Manabí');
bien(G.barraEn(geo, 90 + paso * 1.5 + paso * 0.45, base - 10) === -1,
     'en el hueco entre barras, ninguna (la barra no ocupa todo su tramo)');
bien(G.barraEn(geo, 10, base - 10) === -1, 'fuera del área de trazado (sobre el eje), ninguna');
bien(G.barraEn(geo, centro0, 20) === -1, 'por encima del área de trazado, ninguna');
const geoCorta = Object.assign({}, geo, { valores: [0.25] , categorias: ['Solo'] });
bien(G.barraEn(geoCorta, 90 + geo.trueW * 0.5, base - 5) === 0, 'con una sola categoría también');

// ── qué gráficos se atienden ──
function grafDe(barDir, series) {
    return { chartObj: { calcProp: { widthCanvas: 600, heightCanvas: 429, trueWidth: 500, trueHeight: 260,
                                     chartGutter: { _left: 90, _top: 50 } } },
             chart: { plotArea: { charts: [{ barDir: barDir, gapWidth: 50, series: series }],
                                  valAx: { scaling: { max: 1, min: 0 } } } } };
}
const serie = {
    val: { numRef: { numCache: { formatCode: '0%', pts: [{ idx: 0, val: 0.58 }, { idx: 1, val: 0.63 }] } } },
    cat: { strRef: { strCache: { pts: [{ idx: 0, val: 'Esmeraldas' }, { idx: 1, val: 'Manabí' }] } } },
    dLbls: { numFmt: { formatCode: '0%' } },
    spPr: { Fill: { fill: { color: { color: { RGBA: { R: 19, G: 131, B: 177 } } } } } },
    getSeriesName: () => 'ÍNDICE IMPLEMENTACIÓN'
};
let datos = G.datosDelGrafico(grafDe(1, [serie]));
bien(!!datos && datos.categorias[1] === 'Manabí' && datos.valores[1] === 0.63,
     'de un gráfico de columnas saca categorías y valores');
bien(datos.nombre === 'ÍNDICE IMPLEMENTACIÓN' && datos.color === 'rgb(19,131,177)' && datos.formato === '0%',
     'y el nombre de la serie, su color y el formato');
bien(G.datosDelGrafico(grafDe(0, [serie])) === null, 'un gráfico de barras horizontales no se atiende');
bien(G.datosDelGrafico(grafDe(1, [serie, serie])) === null,
     'ni uno de varias series (mejor no decir nada que decir un dato equivocado)');
bien(G.datosDelGrafico({}) === null, 'ni algo que no es un gráfico');

// ── el globo, de principio a fin ──
grafico.chartObj = grafDe(1, [serie]).chartObj;
grafico.chart = grafDe(1, [serie]).chart;
// el ratón sobre la barra 1 (Manabí): se traduce a milímetros dentro del gráfico
const fx = 90 + (500 / 2) * 1.5, fy = 50 + 260 * 0.8;
logico = { X: grafico.x + fx / 600 * grafico.extX, Y: grafico.y + fy / 429 * grafico.extY };
G.mirar(ventana, 700, 500);
const globo = creados.find((e) => (e.className || '') === 'maq-globo-grafico');
bien(!!globo, 'aparece el globo');
bien(G._estado.ultimo === 'g1:1', 'y sabe que está sobre la barra de Manabí');
bien(globo.hijos.length === 2 && globo.hijos[0].textContent === 'Manabí',
     'primera línea: la categoría');
const segunda = globo.hijos[1];
bien(segunda.hijos.length === 2 && /ÍNDICE IMPLEMENTACIÓN: 63%/.test(segunda.hijos[1].textContent),
     'segunda línea: el cuadradito de color y «ÍNDICE IMPLEMENTACIÓN: 63%»');
bien(/rgb\(19,131,177\)/.test(segunda.hijos[0].style.cssText), 'el cuadradito lleva el color de la serie');
bien(globo.style.left === String(700 + 14 - 40) + 'px' && globo.style.top === String(500 + 14 - 176) + 'px',
     'el globo sale junto al cursor (descontando de dónde cuelga): ' + globo.style.left + ',' + globo.style.top);
bien(buzon.some((b) => b[0] === 'globo del gráfico' && b[1].categoria === 'Manabí'), 'lo cuenta en el buzón');

// fuera de la barra: se esconde
logico = { X: grafico.x + 5 / 600 * grafico.extX, Y: grafico.y + 5 / 429 * grafico.extY };
G.mirar(ventana, 700, 500);
bien(globo.parentNode === null || G._estado.ultimo === '', 'al salir de la barra, el globo desaparece');

// fuera del lienzo no se calcula nada
G.mirar(ventana, 5, 5);
bien(G._estado.ultimo === '', 'fuera del área de la hoja tampoco se enseña nada');

if (rojo) process.exitCode = 1;
