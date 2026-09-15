/* La pastilla dibujada EN EL LIENZO: se simula la hoja del editor (9.4) tal como
   pinta de verdad —`_drawRowBG` pinta los fondos de la fila y, al final, llama a
   `_drawCellText` por cada celda— y se comprueba que la pastilla se pinta ANTES
   del texto de cada celda con lista: la celda en blanco, la cuadrícula por los
   cuatro lados, la cápsula del color que el editor calculó para ESA celda (o
   gris si no tiene relleno) y la flechita; que el texto va encima; que no se
   toca al imprimir ni en combinadas; que una celda con relleno pero sin lista se
   deja en paz; y que si el editor no trae `_drawCellText` no se engancha nada. */

const ops = [];
const ctx = {
    _color: null,
    setFillStyle(c) { this._color = c.getR() + ',' + c.getG() + ',' + c.getB(); return this; },
    fillRect(x, y, w, h) { ops.push(['rect', this._color, x, y, w, h]); return this; },
    beginPath() { return this; }, closePath() { return this; }, fill() { ops.push(['fill', this._color]); return this; },
    arc(x, y, r) { ops.push(['arc', this._color, x, y, r]); return this; },
    moveTo(x, y) { ops.push(['moveTo', x, y]); return this; }, lineTo() { return this; }
};
const TIPOS = { List: 4, None: 0 };
function CColor(r, g, b, a) { this.r = r; this.g = g; this.b = b; this.a = a; }
CColor.prototype.getR = function () { return this.r; }; CColor.prototype.getG = function () { return this.g; };
CColor.prototype.getB = function () { return this.b; }; CColor.prototype.getA = function () { return this.a; };

// Columna 0: lista con el relleno rojo de SU regla; 1: lista sin relleno; 2: combinada;
// 3: sin lista pero con relleno azul (no se toca); 4: lista con relleno «Opción 1» de OTRA lista (verde).
const rellenos = { '0,0': new CColor(211, 47, 47), '3,0': new CColor(0, 0, 255), '4,0': new CColor(0, 128, 0) };
const validadas = { '0,0': TIPOS.List, '1,0': TIPOS.List, '2,0': TIPOS.List, '3,0': TIPOS.None, '4,0': TIPOS.List };
const fondoPintado = [];
const textoPintado = [];

function WorksheetView() {
    this.drawingCtx = ctx;
    this.settings = { cells: { padding: 2, defaultState: { background: new CColor(255, 255, 255, 255), border: new CColor(202, 202, 202, 255) } } };
    this.model = {
        getDataValidation: (c, r) => ((c + ',' + r) in validadas
            ? (c === 4 ? { asc_getType: () => validadas[c + ',' + r] } : { type: validadas[c + ',' + r] })
            : null),
        getCell3: (r, c) => ({
            getFill: () => {
                const col = rellenos[c + ',' + r];
                return { hasFill: () => !!col, bg: () => col || null };
            }
        }),
        getMergedByCell: (r, c) => (c === 2 ? { r1: r, c1: c } : null)
    };
}
// Como en el SDK 9.4: los fondos y, al final de la misma función, el texto de cada celda.
WorksheetView.prototype._drawRowBG = function (drawingCtx, row, colStart, colEnd, offsetX, offsetY) {
    fondoPintado.push([row, colStart, colEnd, !!drawingCtx]);
    for (let col = colStart; col <= colEnd; col++) {
        this._drawCellText(drawingCtx, null, col, row, colStart, colEnd, offsetX, offsetY);
    }
};
WorksheetView.prototype._drawCellText = function (drawingCtx, cfIterator, col, row) {
    textoPintado.push([col, row]);
    ops.push(['texto', col, row, this.settings.cells.padding, this._calcTextVertPos(0, 20, 0, {}, 'abajo')]);
};
WorksheetView.prototype._calcTextVertPos = (y1, h, bl, tm, align) => align;   // devuelve la alineación con la que lo llamaron
WorksheetView.prototype._getRowHeight = () => 20;
WorksheetView.prototype._getRowTop = (r) => 100 + r * 20;
WorksheetView.prototype._getColumnWidth = () => 64;
WorksheetView.prototype._getColLeft = (c) => 30 + c * 64;
WorksheetView.prototype._getOffsetX = () => 0;
WorksheetView.prototype._getOffsetY = () => 0;
WorksheetView.prototype.draw = function () { this.dibujada = true; };
const ws = new WorksheetView();

const ventanaEditor = {
    document: { body: {}, querySelectorAll: () => [] },
    AscCommon: { CColor: CColor },
    Asc: { c_oAscEDataValidationType: TIPOS, c_oAscVAlign: { Center: 'centro', Bottom: 'abajo' }, editor: { wb: { getWorksheet: () => ws } } }
};
// El editor de verdad anida un iframe `sdkjs-plugins`: tiene `Asc` (el de los plugins) pero NO `Asc.editor`
// ni el enumerado de tipos. `alAparecer` lo visita también, DESPUÉS del editor (04/09/2026).
const ventanaPlugins = { document: { body: {}, querySelectorAll: () => [] }, Asc: { plugin: {} }, location: { pathname: '/sdkjs-plugins/x/index.html' } };
ventanaEditor.location = { pathname: '/office-almacen/9.4.0/web-apps/apps/spreadsheeteditor/main/index.html' };
global.window = global;
global.document = { querySelectorAll: (s) => (s === 'iframe' ? [{ contentWindow: ventanaEditor }, { contentWindow: ventanaPlugins }] : []) };
global.setInterval = () => 1;
global.console = console;
const buzon = [];
window.MaquitaDiagnostico = { contar: (momento, datos) => buzon.push([momento, datos]) };

require('/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/editor-ventanas.js');
require('/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/editor-pastilla-lienzo.js');

const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
console.log();
const L = window.MaquitaPastillaLienzo;

bien(L.activo === true, 'con la hoja del editor a la vista, el módulo se engancha y queda activo');
bien(L._estado.ventana === ventanaEditor, 'la ventana del estado es la del EDITOR, aunque después se visite el marco de plugins que anida (ahí no hay enumerado y no se veía ninguna lista, 04/09)');
bien(!ventanaPlugins['__maquita_pastilla-lienzo'], 'y el marco de plugins no queda marcado como hecho: no es el editor');
{
    const activa = buzon.filter(b => b[0] === 'pastilla lienzo' && b[1].activa === 'sí');
    bien(activa.length === 1 && /spreadsheeteditor/.test(activa[0][1].marco) && activa[0][1]['tipo lista'] === '4',
         'el buzón dice en qué marco se activó y qué valor tiene «lista»: ' + JSON.stringify(activa.map(a => a[1])));
}
bien(ws.dibujada === true, 'y pide redibujar la hoja para que salgan las pastillas ya');
bien(WorksheetView.prototype._drawCellText.__maquita === true, 'envuelve _drawCellText del prototipo (todas las hojas)');
bien(WorksheetView.prototype._drawRowBG.__maquita === undefined, 'y ya NO toca _drawRowBG (ahí la pastilla salía después del texto)');

// Una fila: columnas 0-4
ws._drawRowBG(null, 0, 0, 4, 0, 0, {}, null, null);
bien(fondoPintado.length === 1 && textoPintado.length === 5, 'el editor pinta su fondo y luego el texto de las 5 celdas, como siempre');
const blancos = ops.filter(o => o[0] === 'rect' && o[1] === '255,255,255');
bien(blancos.length === 3, 'tapa en blanco las TRES celdas con lista (no la combinada ni la que no tiene lista): ' + blancos.length);
bien(blancos[0][2] === 29 && blancos[0][3] === 99 && blancos[0][4] === 65 && blancos[0][5] === 21,
     'la primera cubre la celda entera más la cuadrícula compartida: ' + blancos[0].slice(2).join(','));
const grises = ops.filter(o => o[0] === 'rect' && o[1] === '202,202,202');
bien(grises.length === 12, 'repone la cuadrícula por los cuatro lados de cada una (gris exacto del editor)');
const capsulas = ops.filter(o => o[0] === 'arc');
bien(capsulas.length === 6 && capsulas[0][1] === '211,47,47', 'la cápsula de la columna 0 lleva el rojo que el editor calculó para ESA celda');
bien(capsulas[2][1] === '224,224,224', 'la celda con lista y sin relleno lleva la cápsula gris');
bien(capsulas[4][1] === '0,128,0', 'y la de la otra lista lleva SU verde, aunque el texto se repita en otras listas (y esa regla solo trae asc_getType)');
bien(!ops.some(o => o[0] === 'rect' && o[1] === '0,0,255'), 'la celda con relleno azul pero sin lista no se toca');
bien(ops.some(o => o[0] === 'moveTo'), 'con su flechita');
bien(capsulas[0][2] === 40.5 && capsulas[0][3] === 109.5 && capsulas[0][4] === 6.5,
     'cápsula con aire (4 px a los lados, 3 arriba y abajo) y extremos redondos: ' + capsulas[0].slice(2).join(','));

// El orden: primero la pastilla, DESPUÉS el texto de esa celda
const iTexto0 = ops.findIndex(o => o[0] === 'texto' && o[1] === 0);
const iCapsula0 = ops.findIndex(o => o[0] === 'arc');
bien(iCapsula0 >= 0 && iCapsula0 < iTexto0, 'la pastilla se pinta antes del texto de su celda, y el texto queda encima');
{
    const margenes = ops.filter(o => o[0] === 'texto').map(o => o[1] + ':' + o[3]).join(' ');
    bien(margenes === '0:12 1:12 2:2 3:2 4:12', 'el texto de las celdas con pastilla entra con margen (aire 4 + radio 7 + 1 = 12 px); las demás con los 2 px de siempre: ' + margenes);
    const vertical = ops.filter(o => o[0] === 'texto').map(o => o[1] + ':' + o[4]).join(' ');
    bien(vertical === '0:centro 1:centro 2:abajo 3:abajo 4:centro', 'y va CENTRADO en vertical dentro de la cápsula; las demás celdas como estaban: ' + vertical);
    bien(!Object.prototype.hasOwnProperty.call(ws, '_calcTextVertPos'), 'el centrado no se queda pegado a la hoja al terminar la celda');
    bien(ws.settings.cells.padding === 2, 'y el margen del editor vuelve a 2 px al terminar cada celda');
}

// Al imprimir (drawingCtx propio) no se pinta nada
ops.length = 0;
ws._drawRowBG({ propio: true }, 0, 0, 4, 0, 0, {}, null, null);
bien(ops.filter(o => o[0] !== 'texto').length === 0, 'al imprimir o exportar no se dibuja ninguna pastilla');

// Un fallo nuestro no deja la hoja sin texto, y se dice
ops.length = 0;
ws.model.getDataValidation = () => { throw new Error('explotó a propósito'); };
ws._drawRowBG(null, 0, 0, 0, 0, 0, {}, null, null);
bien(ops.some(o => o[0] === 'texto') && L._estado.error === 'explotó a propósito',
     'si algo nuestro falla, el editor sigue pintando el texto y el error queda registrado');

// Un editor sin _drawCellText: no se toca
const otro = { Asc: { editor: { wb: { getWorksheet: () => ({ model: {} }) } } } };
bien(L.enganchar(otro) === null, 'si el editor no trae _drawCellText, no se engancha nada (quedan las capas HTML)');

// Al buzón, cuando la hoja termina de pintarse: cuántas vio, cuántas pintó y el error
setTimeout(function () {
    const aviso = buzon.filter(b => b[0] === 'pastilla lienzo' && b[1]['celdas con lista']).pop();
    bien(!!aviso && aviso[1]['celdas con lista'] === '3' && aviso[1].pintadas === '3'
         && aviso[1].error === 'explotó a propósito',
         'al terminar de pintar deja en el buzón cuántas celdas con lista vio, cuántas pintó y el error: '
         + JSON.stringify(aviso && aviso[1]));
    console.log();
}, 1200);
