/* La flecha dentro de la casilla.

   La pastilla —con su ▼ dentro, como en Google— no se pintaba en NINGUNA celda,
   así que solo se veía la flecha del editor, que se dibuja pegada al borde.
   El motivo lo dijo el diagnóstico de Wilson:

       piezas internas   validaciones del modelo   no encontrado

   `validacionesDeLaHoja()` busca propiedades llamadas `ranges`, `type` o
   `formula1`, y en el modelo esos nombres están MINIFICADOS: nunca las
   encuentra. Aquí se comprueba el camino que no depende de eso — los intervalos
   que guardamos al crear cada lista.

   Se ejecuta con:  node prueba-pastillas-sin-modelo.js  */

const B = process.env.MAQ_JS
    || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';

let modeloDaValidaciones = false;      // el caso real: NO las da

const ws = {
    getCellLeftRelative: (col) => 10 + col * 64,
    getCellTopRelative: (fila) => 5 + fila * 17,
    visibleRange: { c1: 0, r1: 0, c2: 19, r2: 25 }
};
const hojaModelo = {};                 // sin nada reconocible: nombres minificados

const ventana = {
    Asc: {
        c_oAscEDataValidationType: { List: 'lista' },
        editor: {
            wb: { getWorksheet: () => ws },
            wbModel: { getActiveWs: () => (modeloDaValidaciones ? {
                lasValidaciones: [{ ranges: [{ c1: 3, r1: 3, c2: 3, r2: 5 }],
                                    type: 'lista' }]
            } : hojaModelo) },
            asc_getWorksheetName: () => 'Buscador',
            asc_getActiveWorksheetIndex: () => 0,
            asc_getActiveCellCoord: () => ({
                asc_getX: () => 10 + 1 * 64, asc_getY: () => 5 + 1 * 17,
                asc_getWidth: () => 64, asc_getHeight: () => 17
            }),
            asc_getActiveRangeStr: () => 'B2',
            asc_getCellInfo: () => ({ asc_getSelectionRange: () => 'B2' })
        },
        referenceType: { A: 0 }
    },
    document: { body: {}, querySelectorAll: () => [] }
};

global.window = global;
global.console = console;
global.document = { body: {}, head: {}, querySelectorAll: () => [],
                    createElement: () => ({ style: {} }), addEventListener() { } };
const avisos = [];
global.window.MaquitaDiagnostico = { contar: (q, d) => avisos.push({ q: q, d: d }) };

require(B + 'editor-rango-a1.js');
require(B + 'editor-pastillas-todas.js');
const T = window.MaquitaPastillasTodas;

// Lo que guardamos al crear las listas: B2:B4 en esta hoja, y una en OTRA hoja.
/* Los rangos salen de las REGLAS DE COLOR puestas en la hoja: cada una dice a
   qué celdas se aplica. (Antes salían de una definición guardada aparte, que el
   editor no llega a guardar.) */
function reglaEn(donde) {
    return { asc_getLocation: () => donde,
             asc_getValue1: () => '"ENERO"',
             asc_getDxf: () => ({ asc_getFillColor: () => null }) };
}
window.MaquitaColoresCF = {
    reglasPuestas: () => [reglaEn("'Buscador'!B2:B4"), reglaEn("'Consolidado'!D2:D9")]
};

let bien = 0, mal = 0;
const comprueba = (r, q) => { r ? bien++ : mal++; console.log((r ? 'OK  ' : 'MAL ') + q); };
console.log();

// ── El caso real: el modelo no suelta las validaciones ───────────────────
let celdas = T.celdasConLista(ventana);
comprueba(celdas.length === 3,
          'aunque el modelo no dé nada, se pintan las 3 celdas de B2:B4 — salen '
          + celdas.length);
comprueba(celdas[0].x === 10 + 1 * 64 && celdas[0].y === 5 + 1 * 17,
          'y cada una en su sitio: B2 cae donde dice el editor');
comprueba(avisos.some(a => a.q === 'pastillas todas'
                        && a.d['rangos recordados'] === '1'
                        && a.d['rangos del modelo'] === '0'),
          'el diagnóstico cuenta de dónde salió cada rango: 0 del modelo, 1 recordado');

// La lista de OTRA hoja no se pinta en esta.
comprueba(!celdas.some(c => c.x === 10 + 3 * 64),
          'una lista de otra hoja no se pinta aquí');

// ── Fuera de lo que se ve, no se pinta ───────────────────────────────────
ws.visibleRange = { c1: 0, r1: 10, c2: 19, r2: 25 };
comprueba(T.celdasConLista(ventana).length === 0,
          'si el intervalo queda fuera de la pantalla, no se pinta nada');
ws.visibleRange = { c1: 0, r1: 0, c2: 19, r2: 25 };

// ── Si el modelo SÍ las da, se usan las dos vías ─────────────────────────
modeloDaValidaciones = true;
window.__maqPastillasContadas = false;
celdas = T.celdasConLista(ventana);
comprueba(celdas.length === 6,
          'con modelo y memoria se pintan las de ambas vías: ' + celdas.length);
modeloDaValidaciones = false;

// ── Sin memoria y sin modelo, no se inventa nada ─────────────────────────
delete window.MaquitaColoresCF;
comprueba(T.celdasConLista(ventana).length === 0,
          'sin nada de dónde sacarlo, no se pinta: mejor ninguna que descolocada');

// ── El desfase: las dos formas de medir NO coinciden, y da igual ────────
/* Las posiciones internas van respecto al área de datos; las públicas incluyen
   los encabezados de fila y columna. Antes se EXIGÍA que coincidieran y no
   coinciden nunca, así que no se pintaba ninguna pastilla («medidas fiables NO»
   en el diagnóstico de Wilson). Ahora se mide la diferencia con la celda activa
   y se aplica a las demás. */
window.MaquitaColoresCF = { reglasPuestas: () => [reglaEn("'Buscador'!B2:B4")] };
const ENCABEZADO_X = 26, ENCABEZADO_Y = 20;
ventana.Asc.editor.asc_getActiveCellCoord = () => ({
    asc_getX: () => 10 + 1 * 64 + ENCABEZADO_X,
    asc_getY: () => 5 + 1 * 17 + ENCABEZADO_Y,
    asc_getWidth: () => 64, asc_getHeight: () => 17
});
celdas = T.celdasConLista(ventana);
comprueba(celdas.length === 3,
          'con encabezados de por medio se siguen pintando las 3: ' + celdas.length);
comprueba(celdas[0].x === 10 + 1 * 64 + ENCABEZADO_X
          && celdas[0].y === 5 + 1 * 17 + ENCABEZADO_Y,
          'y caen donde el editor las pinta de verdad, no 26 px a la izquierda');
comprueba(celdas[1].y === 5 + 2 * 17 + ENCABEZADO_Y,
          'la de debajo también lleva la misma corrección');

// Pero si el TAMAÑO no cuadra, es que algo cambió de verdad: no se pinta.
ventana.Asc.editor.asc_getActiveCellCoord = () => ({
    asc_getX: () => 10 + 1 * 64, asc_getY: () => 5 + 1 * 17,
    asc_getWidth: () => 200, asc_getHeight: () => 60      // nada que ver
});
comprueba(T.celdasConLista(ventana).length === 0,
          'si el TAMAÑO de la celda no cuadra, no se pinta ninguna');
ventana.Asc.editor.asc_getActiveCellCoord = () => ({
    asc_getX: () => 10 + 1 * 64, asc_getY: () => 5 + 1 * 17,
    asc_getWidth: () => 64, asc_getHeight: () => 17
});

// ── Y si las medidas del editor dejan de cuadrar, tampoco ────────────────
window.MaquitaListaMemoria = { _todo: () => ({ "'Buscador'!B2:B4": [{ v: 'X', c: '' }] }) };
const comoEstaba = ws.getCellLeftRelative;
ws.getCellLeftRelative = (col) => 999 + col * 3;  // los ANCHOS ya no cuadran
comprueba(T.celdasConLista(ventana).length === 0,
          'si los anchos internos dejan de cuadrar, no se pinta ninguna');
ws.getCellLeftRelative = comoEstaba;

console.log('\n' + bien + ' bien, ' + mal + ' mal\n');
process.exit(mal ? 1 : 0);
