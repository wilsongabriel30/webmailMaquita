/* Desplegable con FLECHITA por libro (14/10/2026, «01. Proceso Social POA 2026»).
   Se simula la hoja del editor como en prueba-pastilla-lienzo.js y se comprueba:
   sin la marca `_MaqDesplegable` el libro sigue con pastilla; con la marca, la celda
   con lista NO se tapa (ni blanco, ni cápsula), solo se pinta la flechita a la
   derecha, y el texto conserva su margen y su alineación; sobre fondo oscuro la
   flechita va en blanco; la marca se mira por libro. */

const MODULOS = process.env.MODULOS || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen';
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

// Columna 0: lista sin relleno; 1: lista con relleno rosa (regla); 2: lista con relleno oscuro.
const rellenos = { '1,0': new CColor(251, 228, 213), '2,0': new CColor(40, 40, 40) };

function libro(conMarca) {
    return { dependencyFormulas: { getDefNameByName: (n) => (conMarca && n === '_MaqDesplegable' ? { ref: '"flecha"' } : null) } };
}
function WorksheetView(wb) {
    this.drawingCtx = ctx;
    this.settings = { cells: { padding: 2, defaultState: { background: new CColor(255, 255, 255, 255), border: new CColor(202, 202, 202, 255) } } };
    this.model = {
        workbook: wb,
        getDataValidation: () => ({ type: TIPOS.List }),
        getCell3: (r, c) => ({ getFill: () => { const col = rellenos[c + ',' + r]; return { hasFill: () => !!col, bg: () => col || null }; } }),
        getMergedByCell: () => null
    };
}
WorksheetView.prototype._drawRowBG = function (drawingCtx, row, colStart, colEnd, offsetX, offsetY) {
    for (let col = colStart; col <= colEnd; col++) this._drawCellText(drawingCtx, null, col, row, colStart, colEnd, offsetX, offsetY);
};
WorksheetView.prototype._drawCellText = function (drawingCtx, cfIterator, col, row) {
    ops.push(['texto', col, row, this.settings.cells.padding, this._calcTextVertPos(0, 20, 0, {}, 'abajo')]);
};
WorksheetView.prototype._calcTextVertPos = (y1, h, bl, tm, align) => align;
WorksheetView.prototype._getRowHeight = () => 20;
WorksheetView.prototype._getRowTop = (r) => 100 + r * 20;
WorksheetView.prototype._getColumnWidth = () => 64;
WorksheetView.prototype._getColLeft = (c) => 30 + c * 64;
WorksheetView.prototype._getOffsetX = () => 0;
WorksheetView.prototype._getOffsetY = () => 0;
WorksheetView.prototype.draw = function () {};

const sinMarca = new WorksheetView(libro(false));
const conMarca = new WorksheetView(libro(true));
const ventanaEditor = {
    document: { body: {}, querySelectorAll: () => [] },
    AscCommon: { CColor: CColor },
    location: { pathname: '/office-almacen/9.4.0/web-apps/apps/spreadsheeteditor/main/index.html' },
    Asc: { c_oAscEDataValidationType: TIPOS, c_oAscVAlign: { Center: 'centro', Bottom: 'abajo' }, editor: { wb: { getWorksheet: () => sinMarca } } }
};
global.window = global;
global.document = { querySelectorAll: (s) => (s === 'iframe' ? [{ contentWindow: ventanaEditor }] : []) };
global.setInterval = () => 1;
window.MaquitaDiagnostico = { contar: () => {} };

require(MODULOS + '/editor-ventanas.js');
require(MODULOS + '/editor-desplegable-flecha.js');
require(MODULOS + '/editor-pastilla-lienzo.js');

const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
console.log();
const F = window.MaquitaDesplegableFlecha;
bien(!!F && F.NOMBRE === '_MaqDesplegable', 'el módulo publica MaquitaDesplegableFlecha y el nombre de la marca');
bien(F.activo(sinMarca) === false && F.activo(conMarca) === true, 'la marca se mira POR LIBRO: sin ella, pastilla; con ella, flechita');
bien(F.activo(null) === false && F.activo({}) === false, 'sin hoja o sin libro: pastilla (no revienta)');

// Sin marca: lo de siempre (blanco + cápsula)
sinMarca._drawRowBG(null, 0, 0, 2, 0, 0);
bien(ops.some(o => o[0] === 'arc') && ops.some(o => o[0] === 'rect' && o[1] === '255,255,255'),
     'un libro SIN la marca sigue con su pastilla: celda en blanco y cápsula');

// Con marca
ops.length = 0;
conMarca._drawRowBG(null, 0, 0, 2, 0, 0);
bien(!ops.some(o => o[0] === 'arc'), 'con la marca no se dibuja ninguna cápsula');
bien(!ops.some(o => o[0] === 'rect'), 'ni se tapa la celda: el relleno (la regla de color) y la cuadrícula quedan como los pinta el editor');
const flechas = ops.filter(o => o[0] === 'moveTo');
bien(flechas.length === 3, 'una flechita por cada celda con lista: ' + flechas.length);
bien(flechas[0][1] === 30 + 64 - 1 - 10 - 8, 'a la derecha de la celda, centrada en la zona donde se pulsa (10 px de margen): x=' + flechas[0][1]);
bien(flechas[0][2] === 100 + 10 - 2, 'y centrada en el alto de la fila: y=' + flechas[0][2]);
const rellenosFlecha = ops.filter(o => o[0] === 'fill').map(o => o[1]);
bien(rellenosFlecha[0] === '95,99,104' && rellenosFlecha[1] === '95,99,104', 'gris de Google sobre blanco y sobre el rosa claro');
bien(rellenosFlecha[2] === '255,255,255', 'y blanca sobre un fondo oscuro, para que se vea');
const textos = ops.filter(o => o[0] === 'texto');
bien(textos.length === 3 && textos.every(t => t[3] === 2 && t[4] === 'abajo'),
     'el texto conserva su margen (2 px) y su alineación: ' + textos.map(t => t[3] + '/' + t[4]).join(' '));
{
    const iTexto = ops.findIndex(o => o[0] === 'texto');
    const iFlecha = ops.findIndex(o => o[0] === 'moveTo');
    bien(iFlecha >= 0 && iFlecha < iTexto, 'la flechita va antes del texto de su celda, como la pastilla');
}
