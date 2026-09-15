/* Los colores que le tocan a ESTA celda: con dos listas que comparten textos
   («Opción 1» en E9 y en G3, colores al revés), el mapa de E9 lleva los de E9 y
   el de G3 los de G3. Se imita el SDK 9.4: `asc_getLocation()` devuelve
   `[true, "=$E$9"]`, y la caché de rangos del editor convierte «E9» en rango. */

function Rango(c1, r1, c2, r2) { this.c1 = c1; this.r1 = r1; this.c2 = c2; this.r2 = r2; }
Rango.prototype.contains = function (c, r) { return c >= this.c1 && c <= this.c2 && r >= this.r1 && r <= this.r2; };
const LETRAS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
function celda(ref) { const m = /^([A-Z]+)(\d+)$/.exec(ref); return m ? [LETRAS.indexOf(m[1]), parseInt(m[2], 10) - 1] : null; }
function rangoDe(ref) {
    const partes = ref.split(':');
    const a = celda(partes[0]), b = celda(partes[1] || partes[0]);
    return (a && b) ? new Rango(a[0], a[1], b[0], b[1]) : null;
}

function regla(valor, color, sitio) {
    return {
        asc_getValue1: () => '="' + valor + '"',
        asc_getDxf: () => ({ asc_getFillColor: () => ({ get_r: () => parseInt(color.slice(1, 3), 16), get_g: () => parseInt(color.slice(3, 5), 16), get_b: () => parseInt(color.slice(5, 7), 16) }) }),
        asc_getLocation: () => sitio
    };
}
const reglas = [
    regla('Opción 1', '#d32f2f', [true, '=$E$9']), regla('Opción 2', '#1565c0', [true, '=$E$9']),
    regla('Opción 1', '#2e7d32', [true, '=$G$3']), regla('Opción 2', '#f9a825', [true, '=$G$3']),
    regla('Opción 9', '#000000', '=Hoja1!$A$1:$A$5,$C$1:$C$5'),          // dos trozos, con hoja
    regla('Opción 8', '#111111', 'Otra!$E$9'),                            // de OTRA hoja: no cuenta
    regla('Opción 7', '#222222', [true, ''])                             // sin ubicación: no cuenta
];
let activa = { col: 4, row: 8 };
const ventana = {
    AscCommonExcel: { g_oRangeCache: { getAscRange: rangoDe } },
    Asc: { editor: {
        asc_getCF: () => reglas,
        asc_getActiveWorksheetIndex: () => 0,
        asc_getWorksheetName: () => 'Hoja1',
        wb: { getWorksheet: () => ({ model: { selectionRange: { activeCell: activa } } }) }
    } }
};
global.window = global;
const buzon = [];
window.MaquitaDiagnostico = { contar: (m, d) => buzon.push([m, d]) };
require('/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/editor-lista-colores-cf.js');
require('/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/editor-colores-de-la-celda.js');

const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
console.log();
const C = window.MaquitaColoresCelda;

bien(JSON.stringify(C._trozosDe('=Hoja1!$E$9,$E$12:$E$20')) === JSON.stringify([{ hoja: 'Hoja1', ref: 'E9' }, { hoja: '', ref: 'E12:E20' }]),
     'una ubicación se parte en trozos sin «=», sin «$» y con su hoja aparte');
bien(JSON.stringify(C._textosDe([true, '=$E$9'])) === '["=$E$9"]', 'del [true, "=$E$9"] del 9.4 se coge el texto');

const deE9 = C.coloresDeLaCelda(ventana);
bien(deE9['Opción 1'] === '#d32f2f' && deE9['Opción 2'] === '#1565c0' && Object.keys(deE9).length === 2,
     'en E9 salen SUS colores (rojo, azul), no los de G3: ' + JSON.stringify(deE9));
activa = { col: 6, row: 2 };
const deG3 = C.coloresDeLaCelda(ventana);
bien(deG3['Opción 1'] === '#2e7d32' && deG3['Opción 2'] === '#f9a825' && Object.keys(deG3).length === 2,
     'en G3, aunque los textos sean los mismos, salen los de G3 (verde, amarillo): ' + JSON.stringify(deG3));
activa = { col: 2, row: 3 };
const deC4 = C.coloresDeLaCelda(ventana);
bien(deC4['Opción 9'] === '#000000' && Object.keys(deC4).length === 1, 'una regla con dos trozos aplica en el segundo (C4)');
activa = { col: 4, row: 8 };
bien(!C.coloresDeLaCelda(ventana)['Opción 8'], 'una regla de OTRA hoja sobre la misma referencia no cuenta');
bien(!C.coloresDeLaCelda(ventana)['Opción 7'], 'una regla sin ubicación no cuenta');
activa = { col: 10, row: 10 };
bien(Object.keys(C.coloresDeLaCelda(ventana)).length === 0, 'una celda sin reglas da un mapa vacío (y quien llama vuelve a los de la hoja)');

// Sin caché de rangos (otra versión): no se puede saber, mapa vacío, sin explotar
const sinCache = { Asc: ventana.Asc };
bien(Object.keys(C.coloresDeLaCelda(sinCache)).length === 0, 'si el editor no trae la caché de rangos, mapa vacío y sin fallo');

const avisos = buzon.filter(b => b[0] === 'colores de la celda');
bien(avisos.length >= 2 && avisos[0][1]['reglas de la celda'] === '2' && /Opción 1 \| Opción 2/.test(avisos[0][1]['valores con color']),
     'deja en el buzón cuántas reglas son de la celda y qué valores tienen color: ' + JSON.stringify(avisos[0] && avisos[0][1]));
console.log();
