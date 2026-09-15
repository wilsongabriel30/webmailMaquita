/* Un solo botón para abrir la lista: cuando el cursor está en una celda con
   lista (venga del panel o de Excel/Google), el editor NO pinta su botón de
   fuera de la celda; en las demás celdas (sin lista, total de tabla) pinta como
   siempre. Y solo mientras la pastilla del lienzo esté activa. */

const pintados = [];
let activa = { col: 0, row: 1 };
const validadas = { '0,1': { type: 4 }, '1,1': { asc_getType: () => 4 }, '2,1': { type: 2 }, '3,1': { type: 4 } };
function WorksheetView() {
    this.model = {
        getSelection: () => ({ activeCell: activa }),
        getDataValidation: (c, r) => validadas[c + ',' + r] || null,
        isTableTotal: (c, r) => c === 3
    };
}
WorksheetView.prototype.drawOverlayButtons = function (vr, ox, oy) { pintados.push([activa.col, activa.row]); return false; };
const ws = new WorksheetView();
const ventanaEditor = { document: { body: {}, querySelectorAll: () => [] }, Asc: { editor: { wb: { getWorksheet: () => ws } } } };
const ventanaPlugins = { document: { body: {}, querySelectorAll: () => [] }, Asc: { plugin: {} } };
global.window = global;
global.document = { querySelectorAll: (s) => (s === 'iframe' ? [{ contentWindow: ventanaEditor }, { contentWindow: ventanaPlugins }] : []) };
global.setInterval = () => 1;
const buzon = [];
window.MaquitaDiagnostico = { contar: (m, d) => buzon.push([m, d]) };
window.MaquitaPastillaLienzo = { activo: true };
const B = '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';
require(B + 'editor-ventanas.js');
require(B + 'editor-boton-nativo-lista.js');

const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
console.log();
const M = window.MaquitaBotonNativoLista;
bien(M._estado.activo === true && WorksheetView.prototype.drawOverlayButtons.__maquita === true, 'se engancha a drawOverlayButtons del editor y queda activo');
bien(buzon.some(b => b[0] === 'boton nativo lista' && b[1].apagado === 'sí'), 'y lo dice en el buzón');

ws.drawOverlayButtons({}, 0, 0);
bien(pintados.length === 0 && M._estado.apagados === 1, 'con el cursor en una celda con lista (type), el editor NO pinta su botón');
activa = { col: 1, row: 1 };
ws.drawOverlayButtons({}, 0, 0);
bien(pintados.length === 0 && M._estado.apagados === 2, 'igual si la regla solo trae asc_getType (lista de Excel/Google)');
activa = { col: 2, row: 1 };
ws.drawOverlayButtons({}, 0, 0);
bien(pintados.length === 1, 'en una celda con validación que NO es lista, pinta como siempre');
activa = { col: 5, row: 5 };
ws.drawOverlayButtons({}, 0, 0);
bien(pintados.length === 2, 'en una celda sin validación, pinta como siempre');
activa = { col: 3, row: 1 };
ws.drawOverlayButtons({}, 0, 0);
bien(pintados.length === 3, 'en el total de una tabla (mismo botón, otro uso) no se toca');

window.MaquitaPastillaLienzo = { activo: false };
activa = { col: 0, row: 1 };
ws.drawOverlayButtons({}, 0, 0);
bien(pintados.length === 4, 'si la pastilla del lienzo no está activa, el botón del editor vuelve (es la única forma de abrir la lista)');

ws.model.getDataValidation = () => { throw new Error('explotó'); };
window.MaquitaPastillaLienzo = { activo: true };
ws.drawOverlayButtons({}, 0, 0);
bien(pintados.length === 5, 'si algo nuestro falla, el editor pinta el suyo (nunca se queda sin botón)');

const otro = { Asc: { editor: { wb: { getWorksheet: () => ({ model: {} }) } } } };
bien(M.enganchar(otro) === null, 'un editor sin drawOverlayButtons no se toca');
console.log();
