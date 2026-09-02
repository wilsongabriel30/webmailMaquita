/* Simulacro del editor: se comprueba la decisión EXACTA que toma OnlyOffice
   al arrastrar el borde de una fila —o de una columna—, que es esta:

       if (seleccion.isContainsOnlyFullRowOrCol() && seleccion.containsRow(fila))
           -> cambia TODAS las filas de la selección
       else
           -> cambia solo la fila arrastrada
*/

const TIPO = { CELDAS: 1, COLUMNA: 2, FILA: 3, TODO: 4 };

function rango(tipo, r1, r2) {
    return {
        getType: () => tipo,
        containsRow: (r) => r >= (r1 === undefined ? 0 : r1)
                         && r <= (r2 === undefined ? 1048575 : r2),
        containsCol: () => true
    };
}

function seleccion(...rangos) {
    const s = {
        ranges: rangos,
        containsRow(r) { return this.ranges.some(x => x.containsRow(r)); },
        containsCol(c) { return this.ranges.some(x => x.containsCol(c)); }
    };
    Object.setPrototypeOf(s, Seleccion.prototype);
    s.ranges = rangos;
    return s;
}

// La clase del editor, con su función tal cual viene de fábrica.
function Seleccion() { }
Seleccion.prototype.isContainsOnlyFullRowOrCol = function (porColumna) {
    for (let i = 0; i < this.ranges.length; ++i) {
        const tipo = this.ranges[i].getType();
        if (porColumna && tipo !== TIPO.COLUMNA) return false;
        if (!porColumna && tipo !== TIPO.FILA) return false;
    }
    return true;
};
Seleccion.prototype.containsRow = function (r) {
    return this.ranges.some(x => x.containsRow(r));
};
Seleccion.prototype.containsCol = function (c) {
    return this.ranges.some(x => x.containsCol(c));
};

// ── La página, con el editor en un iframe ────────────────────────────────
const ventanaEditor = {
    document: { body: {}, querySelectorAll: () => [] },
    AscCommonExcel: { SelectionRange: Seleccion }
};
global.window = global;
global.document = { querySelectorAll: (s) => (s === 'iframe' ? [{ contentWindow: ventanaEditor }] : []) };
global.setInterval = () => 1;
global.console = console;

require('/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/editor-ventanas.js');
require('/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/editor-seleccion-total.js');

// La decisión del editor, copiada de sdkjs/cell (WorksheetView.changeRowHeight)
function alcanceAlArrastrar(sel, fila) {
    return (sel.ranges && sel.isContainsOnlyFullRowOrCol() && sel.containsRow(fila))
        ? 'TODAS las filas seleccionadas' : 'solo la fila arrastrada';
}
function alcanceAlArrastrarColumna(sel, col) {
    return (sel.ranges && sel.isContainsOnlyFullRowOrCol(true) && sel.containsCol(col))
        ? 'TODAS las columnas seleccionadas' : 'solo la columna arrastrada';
}

const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
console.log();

// 1. Lo que se pedía: la esquinita.
const todo = seleccion(rango(TIPO.TODO));
bien(alcanceAlArrastrar(todo, 5) === 'TODAS las filas seleccionadas',
     'con TODO seleccionado, cambiar un alto cambia todas las filas');
bien(alcanceAlArrastrarColumna(todo, 3) === 'TODAS las columnas seleccionadas',
     'con TODO seleccionado, cambiar un ancho cambia todas las columnas');

// 2. Lo que ya funcionaba debe seguir igual.
const filas = seleccion(rango(TIPO.FILA, 2, 9));
bien(alcanceAlArrastrar(filas, 5) === 'TODAS las filas seleccionadas',
     'seleccionar varias filas sigue aplicando a todas');
bien(alcanceAlArrastrar(filas, 40) === 'solo la fila arrastrada',
     'arrastrar una fila FUERA de la seleccion solo la cambia a ella');

const columnas = seleccion(rango(TIPO.COLUMNA));
bien(alcanceAlArrastrarColumna(columnas, 3) === 'TODAS las columnas seleccionadas',
     'seleccionar varias columnas sigue aplicando a todas');

// 3. Y lo que NO debe propagarse, no se propaga.
const celdas = seleccion(rango(TIPO.CELDAS, 2, 9));
bien(alcanceAlArrastrar(celdas, 5) === 'solo la fila arrastrada',
     'con un bloque de CELDAS seleccionado, cambia solo la fila arrastrada');
bien(alcanceAlArrastrarColumna(celdas, 3) === 'solo la columna arrastrada',
     'con un bloque de CELDAS, cambia solo la columna arrastrada');

const mezcla = seleccion(rango(TIPO.TODO), rango(TIPO.CELDAS, 2, 9));
bien(alcanceAlArrastrar(mezcla, 5) === 'solo la fila arrastrada',
     'una seleccion mixta no se toma por «todo»');
