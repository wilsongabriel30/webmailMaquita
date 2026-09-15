/* Borrar una celda con lista se lleva también la lista y sus colores, como si
   fuera un texto: con la tecla Supr (emptySelection) y con el menú «Borrar»
   (asc_emptyCells); «Borrar → Formato» no; en celdas sin lista no se toca nada;
   y si nuestra parte falla, el borrado del editor ya ocurrió igual. */

const orden = [];
const validadas = { '4,11': { type: 4 }, '7,12': { type: 4 } };
let seleccion = { r1: 11, c1: 4, r2: 11, c2: 4 };
function WorksheetView() {
    this.model = {
        selectionRange: { getLast: () => seleccion },
        getDataValidation: (c, r) => validadas[c + ',' + r] || null
    };
}
WorksheetView.prototype.emptySelection = function (op) { orden.push('editor borra(' + op + ')'); return 'borrado'; };
function spreadsheet_api() {}
spreadsheet_api.prototype.asc_emptyCells = function (op) { orden.push('menú borra(' + op + ')'); };
const ws = new WorksheetView();
const editor = new spreadsheet_api();
editor.wb = { getWorksheet: () => ws };
const ventanaEditor = { document: { body: {}, querySelectorAll: () => [] }, Asc: { editor: editor } };

global.window = global;
global.document = { querySelectorAll: (s) => (s === 'iframe' ? [{ contentWindow: ventanaEditor }] : []) };
global.setInterval = () => 1;
const buzon = [];
window.MaquitaDiagnostico = { contar: (m, d) => buzon.push([m, d]) };
window.MaquitaListas = { quitar: () => { orden.push('quitar lista'); return true; } };

const B = process.env.MODULOS || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';
require(B + 'editor-ventanas.js');
require(B + 'editor-borrar-lista.js');

const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
console.log();
const M = window.MaquitaBorrarLista;
bien(M._estado.activo === true && WorksheetView.prototype.emptySelection.__maquita === true
     && spreadsheet_api.prototype.asc_emptyCells.__maquita === true, 'se engancha al borrado de la tecla y al del menú');
bien(buzon.some(b => b[0] === 'borrar lista' && b[1].activo === 'sí'), 'y lo dice en el buzón');

// Supr sobre una celda CON lista
let r = ws.emptySelection(undefined);
bien(r === 'borrado', 'el borrado del editor se hace igual y devuelve lo suyo');
bien(JSON.stringify(orden) === JSON.stringify(['editor borra(undefined)', 'quitar lista']), 'primero borra el editor y DESPUÉS se quita la lista: ' + orden.join(' → '));
bien(M._estado.quitadas === 1 && buzon.some(b => b[1].quitadas === '1'), 'lo cuenta en el buzón');

// celda SIN lista
orden.length = 0;
seleccion = { r1: 0, c1: 0, r2: 0, c2: 0 };
ws.emptySelection(undefined);
bien(JSON.stringify(orden) === JSON.stringify(['editor borra(undefined)']), 'en una celda sin lista no se toca nada');

// rango que incluye una celda con lista
orden.length = 0;
seleccion = { r1: 10, c1: 3, r2: 13, c2: 8 };
ws.emptySelection(0);
bien(orden.indexOf('quitar lista') !== -1, 'en un rango con alguna celda con lista, también');

// el menú «Borrar»
orden.length = 0;
editor.asc_emptyCells(1);
bien(JSON.stringify(orden) === JSON.stringify(['menú borra(1)', 'quitar lista']), '«Borrar → Texto» del menú: igual');
orden.length = 0;
editor.asc_emptyCells(2);
bien(JSON.stringify(orden) === JSON.stringify(['menú borra(2)']), '«Borrar → Formato» NO quita la lista (ahí no se borra contenido)');

// tope: una selección enorme no recorre un millón de celdas
const antes = Date.now();
seleccion = { r1: 0, c1: 0, r2: 1048575, c2: 16383 };
orden.length = 0;
ws.emptySelection(0);
bien(Date.now() - antes < 2000 && orden.indexOf('quitar lista') !== -1, 'con toda la hoja seleccionada responde al momento (tope de celdas miradas)');

// si quitar falla, el borrado del editor ya ocurrió
seleccion = { r1: 11, c1: 4, r2: 11, c2: 4 };
window.MaquitaListas = { quitar: () => { throw new Error('explotó'); } };
orden.length = 0;
r = ws.emptySelection(undefined);
bien(r === 'borrado' && orden.length === 1, 'si quitar la lista falla, la celda se borró igual y no se propaga el error');

// sin selección no se rompe
window.MaquitaListas = { quitar: () => { orden.push('quitar lista'); return true; } };
ws.model.selectionRange = null;
orden.length = 0;
r = ws.emptySelection(undefined);
bien(r === 'borrado' && orden.length === 1, 'sin selección, el borrado normal y nada más');
