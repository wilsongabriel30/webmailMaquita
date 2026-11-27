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
const B = process.env.MODULOS || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';
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

/* OnlyOffice 10 (27/11/2026): nombres minificados. La función del botón se
   reconoce por su forma y la lista se pregunta al modelo con los nombres que
   ella misma usa. Fuente real de la 10.0 (réplica del editor). */
const QFJ = 'function(J,V,sa){if(this.Aa.di()){var N=this.model.getSelection().Zg;if(J.B5a(N)){J=(J=this.model.SZd(N.La,N.Fa))&&J.Tof();var ba;J&&(ba=this.model.AB(N.Fa,N.La));(J||this.model.Mdh(N.La,N.Fa))&&this.UNe(V,sa,{hnd:!0,Flc:null,Clc:!1,Fa:J&&ba?ba.r1:N.Fa,La:J&&ba?ba.sa:N.La});return!1}return!0}}';
const NB = window.MaquitaBotonNativoLista;
bien(NB._forma.test(QFJ), 'OnlyOffice 10: se reconoce la función que pinta el botón de la celda');
bien(!NB._forma.test('function(J){var V=this.model.getSelection();return V}'), 'una función cualquiera no se confunde');
const leer = NB._lector(QFJ);
const vista = (conLista) => ({ model: { getSelection: () => ({ Zg: { La: 2, Fa: 7 } }),
    SZd: (c, f) => (c === 2 && f === 7 ? { Tof: () => conLista } : null) } });
bien(!!leer && leer(vista(true)) === true, 'se pregunta al modelo: celda con lista');
bien(!!leer && leer(vista(false)) === false, 'se pregunta al modelo: validación que no es lista');
