/* Quitar una lista: la validación pasa a «None» por el camino que SÍ funciona en
   el 9.4 (props sin argumento) y las reglas de color se borran por ID, solo las
   que caben enteras dentro de lo seleccionado. */

const hechas = [];
let seleccion = { r1: 11, c1: 4, r2: 11, c2: 4 };
let propsRotas = false;
const props = { tipo: 4, asc_setType: function (t) { this.tipo = t; hechas.push('tipo=' + t); }, asc_getType: function () { return this.tipo; } };
const editor = {
    asc_getDataValidationProps: (extend) => {
        if (extend === true) throw new Error("Cannot read properties of undefined (reading 'clone')");
        return propsRotas ? null : props;
    },
    asc_setDataValidation: (p) => hechas.push('aplicar validación tipo ' + p.tipo),
    asc_setCF: (arr, ids) => hechas.push('borrar colores ' + JSON.stringify(ids)),
    asc_getWorksheetName: () => 'Hoja3',
    asc_getActiveWorksheetIndex: () => 2,
    wb: { getWorksheet: () => ({ model: { selectionRange: { getLast: () => seleccion } } }) }
};
const rangos = { 'E12': { r1: 11, c1: 4, r2: 11, c2: 4 }, 'E1:E100': { r1: 0, c1: 4, r2: 99, c2: 4 }, 'H13': { r1: 12, c1: 7, r2: 12, c2: 7 } };
function regla(id, ref, hoja) {
    return { asc_getId: () => id, asc_getLocation: () => [true, '=' + (hoja ? hoja + '!' : '') + '$' + ref.replace(':', ':$')] };
}
const ventana = {
    Asc: { editor: editor, c_oAscEDataValidationType: { None: 0, List: 4 } },
    AscCommonExcel: { g_oRangeCache: { getAscRange: (ref) => rangos[ref.replace(/\$/g, '')] || null } }
};
global.window = global;
global.document = { querySelectorAll: () => [] };
const buzon = [];
window.MaquitaDiagnostico = { contar: (m, d) => buzon.push([m, d]) };
window.MaquitaColoresCelda = {
    _textosDe: (cosa) => (Array.isArray(cosa) ? cosa.filter(x => typeof x === 'string') : (typeof cosa === 'string' ? [cosa] : [])),
    _trozosDe: (texto) => String(texto).replace(/^=/, '').split(',').map(t => {
        const i = t.lastIndexOf('!');
        return { hoja: i >= 0 ? t.slice(0, i) : '', ref: (i >= 0 ? t.slice(i + 1) : t).replace(/\$/g, '') };
    })
};
window.MaquitaColoresCF = { reglasPuestas: () => [regla('r1', 'E12'), regla('r2', 'E12'), regla('r3', 'E1:E100'), regla('r4', 'H13')] };

const B = process.env.MODULOS || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';
require(B + 'editor-lista-quitar.js');

const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
console.log();
const Q = window.MaquitaListaQuitar;

let ids = Q.coloresAQuitar(ventana, seleccion);
bien(JSON.stringify(ids) === JSON.stringify(['r1', 'r2']), 'se eligen las reglas de color de ESA celda: ' + ids.join(', '));
bien(ids.indexOf('r3') === -1, 'una regla que vale para E1:E100 NO se borra al borrar solo E12 (las demás celdas conservan su color)');
bien(ids.indexOf('r4') === -1, 'ni las de otras celdas');

hechas.length = 0;
let r = Q.quitar(ventana);
bien(r.ok === true && r.colores === 2, 'quitar dice qué hizo: lista fuera y 2 colores');
bien(JSON.stringify(hechas) === JSON.stringify(['borrar colores ["r1","r2"]', 'tipo=0', 'aplicar validación tipo 0']),
     'primero los colores (mientras se sabe dónde aplican) y después la validación a «None»: ' + hechas.join(' | '));
bien(buzon.some(b => b[0] === 'quitar lista' && b[1].lista === 'sí' && b[1].colores === '2'), 'lo cuenta en el buzón');

// nunca se llama con `true` (que en el 9.4 revienta)
hechas.length = 0;
let exploto = false;
try { Q.quitarLista(ventana); } catch (e) { exploto = true; }
bien(!exploto, 'no se usa la llamada que revienta en el 9.4 («…reading clone»)');

// selección grande: los colores no se tocan (y la lista sí)
seleccion = { r1: 0, c1: 0, r2: 1048575, c2: 16383 };
hechas.length = 0;
r = Q.quitar(ventana);
bien(r.colores === 0 && hechas.indexOf('aplicar validación tipo 0') !== -1, 'con toda la hoja seleccionada no se recorren los colores, pero la lista se quita igual');

// si el editor no da props, se dice que no y no se rompe nada
seleccion = { r1: 11, c1: 4, r2: 11, c2: 4 };
propsRotas = true;
r = Q.quitar(ventana);
bien(r.ok === false, 'si el editor no entrega la regla, devuelve que no pudo (sin lanzar)');
propsRotas = false;

// sin los módulos de color, la lista se quita igual
window.MaquitaColoresCF = null;
hechas.length = 0;
r = Q.quitar(ventana);
bien(r.ok === true && r.colores === 0, 'sin el módulo de colores, la lista se quita igual');
