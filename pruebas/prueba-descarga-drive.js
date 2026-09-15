/* «Descargar como → Excel» desde el editor sale por el Drive (que guarda primero
   y traduce listas y colores); PDF, CSV, «guardar copia» y todo lo demás siguen
   por el editor. Y si no estamos en la página del editor del Drive, no se toca. */

const llamadasOriginales = [];
function spreadsheet_api() {}
spreadsheet_api.prototype.asc_DownloadAs = function (o) { llamadasOriginales.push(o); };
const editor = new spreadsheet_api();
const ventanaEditor = { document: { body: {}, querySelectorAll: () => [] }, Asc: { editor: editor } };
const marcos = {};
global.window = global;
global.location = { pathname: '/archivos-almacen/editar', search: '?ruta=%2Funidades%2F5%2FNuevo%20Hoja%20de%20c%C3%A1lculo.xlsx' };
global.URLSearchParams = require('url').URLSearchParams;
global.document = {
    querySelectorAll: (s) => (s === 'iframe' ? [{ contentWindow: ventanaEditor }] : []),
    getElementById: (id) => marcos[id] || null,
    createElement: () => ({ style: {}, setAttribute() {} }),
    body: { appendChild: (m) => { marcos['maq-descarga-drive'] = m; } }
};
global.setInterval = () => 1;
const buzon = [];
window.MaquitaDiagnostico = { contar: (m, d) => buzon.push([m, d]) };
const B = process.env.MODULOS || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';
require(B + 'editor-ventanas.js');
require(B + 'editor-descarga-drive.js');

const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
console.log();
const M = window.MaquitaDescargaDrive;
const opciones = (tipo, extra) => Object.assign({ fileType: tipo, isSaveAs: false }, extra || {});

bien(M._estado.activo === true && spreadsheet_api.prototype.asc_DownloadAs.__maquita === true, 'se engancha a asc_DownloadAs del editor y queda activo');
bien(buzon.some(b => b[0] === 'descarga por el drive' && b[1].activa === 'sí'), 'y lo dice en el buzón');

editor.asc_DownloadAs(opciones(0x0101));
const marco = marcos['maq-descarga-drive'];
bien(llamadasOriginales.length === 0 && !!marco, 'a Excel (.xlsx): NO llama al editor; abre la descarga del Drive en un iframe oculto');
bien(marco && /^\/api\/almacen\/archivos\/descargar\?ruta=%2Funidades%2F5%2FNuevo%20Hoja%20de%20c%C3%A1lculo\.xlsx&guardar=1&t=\d+$/.test(marco.src),
     'la URL es la de la descarga del Drive, con la ruta del archivo y guardar=1: ' + (marco && marco.src));
bien(M._estado.desviadas === 1 && buzon.some(b => b[1].desviadas === '1'), 'y cuenta la desviación en el buzón');

editor.asc_DownloadAs(opciones(0x0105));
bien(llamadasOriginales.length === 0 && M._estado.desviadas === 2, 'a .xlsm también por el Drive');

editor.asc_DownloadAs(opciones(0x0201));
bien(llamadasOriginales.length === 1 && llamadasOriginales[0].fileType === 0x0201, 'a PDF: el editor, como siempre');
editor.asc_DownloadAs(opciones(0x0104));
bien(llamadasOriginales.length === 2, 'a CSV: el editor');
editor.asc_DownloadAs(opciones(0x0101, { isSaveAs: true }));
bien(llamadasOriginales.length === 3, '«guardar copia como» .xlsx: el editor (es otro flujo)');
editor.asc_DownloadAs(opciones(0x0101, { oDocumentMailMerge: {} }));
bien(llamadasOriginales.length === 4, 'combinación de correspondencia: el editor');
editor.asc_DownloadAs({ asc_getFileType: () => 0x0101, isSaveAs: false });
bien(llamadasOriginales.length === 4 && M._estado.desviadas === 3, 'si las opciones traen asc_getFileType en vez de la propiedad, también se reconoce');
editor.asc_DownloadAs(null);
bien(llamadasOriginales.length === 5, 'sin opciones: el editor');

global.location = { pathname: '/archivos-almacen/editar-publico', search: '?t=abc' };
editor.asc_DownloadAs(opciones(0x0101));
bien(llamadasOriginales.length === 6, 'en el editor de enlaces públicos (sin ruta ni sesión) no se toca: el editor');

global.location = { pathname: '/archivos-almacen/editar', search: '?ruta=%2Fa.xlsx' };
M._estado.activo = false;
editor.asc_DownloadAs(opciones(0x0101));
bien(llamadasOriginales.length === 7, 'si el módulo está apagado, el editor');
M._estado.activo = true;

const original = M.destino;
M.destino = null;
const antes = M._estado.desviadas;
global.document.getElementById = () => { throw new Error('explotó'); };
editor.asc_DownloadAs(opciones(0x0101));
bien(llamadasOriginales.length === 8, 'si algo nuestro falla, se llama al editor: nunca se queda sin descarga');
M.destino = original;
