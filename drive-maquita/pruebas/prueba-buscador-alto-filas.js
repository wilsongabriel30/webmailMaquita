/* Al cambiar el desplegable de un buscador, las filas toman su alto (12/10/2026).
   Lo que se comprueba: que el buscador se reconoce por su primera celda (y nada
   más), y qué filas se reajustan al crecer o achicarse el resultado. */

global.window = global;
global.console = console;

require('/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/editor-buscador-alto-filas.js');

const B = window.MaquitaBuscadorAltoFilas;
const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
console.log('\n[Drive Maquita] el alto de las filas de un buscador\n');

/** Hoja falsa: { 'fila,col': fórmula }. */
function hojaCon(formulas) {
    return {
        getRange3: function (r, c) {
            return { getFormula: function () { return formulas[r + ',' + c] || ''; } };
        }
    };
}

const PRIMERA = 'IF($AX$3=0,NA(),IF($AX4="","",IF(INDEX(ConsolidadoT!$G$4:$G$5485,$AX4)="","",INDEX(ConsolidadoT!$G$4:$G$5485,$AX4))))';
const b = B.buscador(hojaCon({ '3,0': PRIMERA }));
bien(b && b.fila0 === 3 && b.col0 === 0, 'reconoce el buscador por su primera celda (A4)');
bien(b && b.cuentaFila === 2 && b.cuentaColumna === 49, 'y su contador ($AX$3 → fila 2, columna 49)');
bien(B.buscador(hojaCon({ '3,0': 'SUM(A1:A9)' })) === null, 'una hoja con otras fórmulas NO es buscador');
bien(B.buscador(hojaCon({ '4,0': 'IF($AX5="","",IF(INDEX(ConsolidadoT!$G$4:$G$5485,$AX5)="","",INDEX(ConsolidadoT!$G$4:$G$5485,$AX5)))' })) === null,
     'una celda del resultado que no es la primera no basta');
bien(B.buscador(hojaCon({})) === null, 'una hoja vacía NO es buscador');
const b2 = B.buscador(hojaCon({ '5,2': PRIMERA.replace('$AX$3', '$BC$5') }));
bien(b2 && b2.fila0 === 5 && b2.col0 === 2 && b2.cuentaFila === 4 && b2.cuentaColumna === 54, 'el buscador puede estar en otro sitio (C6, contador $BC$5)');

const t1 = B.filasAReajustar(b, 500, 8);
bien(t1[0] === 3 && t1[1] === 502, 'de 500 filas a 8: se reajustan las 500 (las que quedan vacías vuelven a un renglón)');
const t2 = B.filasAReajustar(b, 8, 470);
bien(t2[0] === 3 && t2[1] === 472, 'de 8 a 470: se reajustan las 470');
const t3 = B.filasAReajustar(b, 0, 0);
bien(t3[0] === 3 && t3[1] === 3, 'sin resultado: solo la primera fila (la del #N/A)');

// ── El alto exacto de Google (12/10/2026) ────────────────────────────────
bien(B.renglones('Plan Modular') === 1, 'un texto sin salto: un renglón');
bien(B.renglones('Talleres\n (5 x 3 zonas)') === 2, 'con un salto: dos renglones');
bien(B.renglones('Talleres de formación\n(3 x 2 años)\n') === 2, 'el salto del final no cuenta');
bien(B.renglones('') === 1 && B.renglones(null) === 1 && B.renglones(1.5) === 1, 'vacío o número: un renglón');
bien(B.alto(1) === 12.75 && B.alto(2) === 21.75 && B.alto(3) === 30.75, 'altos: 12,75 / 21,75 / 30,75 pt (como la sincronización)');
const tramos = B.tramosDeAlto([12.75, 12.75, 21.75, 21.75, 12.75], 3);
bien(JSON.stringify(tramos) === JSON.stringify([[3, 4, 12.75], [5, 6, 21.75], [7, 7, 12.75]]), 'filas seguidas con el mismo alto van juntas (3 cambios, no 5)');

// ── El alto propio de Google manda si es mayor (13/10/2026) ──────────────
bien(B.alto(1, 15) === 15 && B.alto(2, 15) === 21.75 && B.alto(3, 15) === 30.75, 'con base 15 (Google del 13/10): 15 / 21,75 / 30,75 pt');
bien(B.alto(1, 30) === 30 && B.alto(2, 30) === 30, 'si Google dio 30 pt a la fila, un renglón o dos miden 30');
bien(B.alto(1, 0) === 12.75 && B.alto(1, undefined) === 12.75, 'sin base: la regla de siempre');
const hojaAltos = { getRowHeight: function (r) { return r === 5 ? 21.75 : (r === 7 ? 30.75 : 15); } };
bien(B.altoBase(hojaAltos, { fila0: 3 }, 10) === 15, 'la base es el menor alto de las filas del resultado (las de un renglón)');
bien(B.altoBase({}, { fila0: 3 }, 10) === 12.75, 'si el editor no da altos, 12,75');
