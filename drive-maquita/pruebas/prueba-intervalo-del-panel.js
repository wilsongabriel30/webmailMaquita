/* «Aplicar al intervalo» tiene que salir RELLENO al abrir el panel, como en
   Google. Salía vacío porque se leía por una vía que fallaba en silencio; esta
   prueba existe para que no vuelva a pasar (02/09/2026). */

const contado = [];

function editorCon(opciones) {
    opciones = opciones || {};
    const editor = {};
    if (!opciones.sinDirecto) {
        editor.asc_getActiveRangeStr = function (tipo) {
            if (opciones.directoFalla) throw new Error('todavia no');
            if (opciones.directoVacio) return '';
            editor.tipoPedido = tipo;
            // Como el editor de verdad: celdas solas y en absoluto.
            return opciones.conHoja ? "'Ejec. Tec. 2026'!B2:D20" : '$B$2:$D$20';
        };
    }
    editor.asc_getCellInfo = function () {
        if (opciones.infoFalla) throw new Error('sin hoja abierta');
        if (opciones.sinInfo) return null;
        return {
            asc_getSelectionRange: opciones.sinRango ? undefined
                : function () { return 'B2:D20'; }
        };
    };
    editor.asc_getWorksheetName = function () { return 'Ejec. Tec. 2026'; };
    editor.asc_getActiveWorksheetIndex = function () { return 1; };
    return editor;
}

function ventanaCon(editor) {
    return { Asc: { editor: editor, referenceType: { A: 'absoluta' } } };
}

global.window = global;
global.window.MaquitaDiagnostico = {
    contar: function (momento, datos) { contado.push(momento + ': ' + JSON.stringify(datos)); }
};
global.document = {
    body: { appendChild() { }, removeChild() { } },
    head: { appendChild() { } },
    createElement: () => ({ style: {}, setAttribute() { }, appendChild() { },
                            querySelector: () => null, querySelectorAll: () => [] }),
    querySelectorAll: () => [],
    addEventListener() { }
};
global.setInterval = () => 1;
global.console = console;

const B = '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';
require(B + 'editor-ventanas.js');
require(B + 'editor-lista-aplicar.js');

const L = window.MaquitaListas;
const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
console.log('\n[Drive Maquita] el intervalo del panel\n');

// ── Lo normal: sale relleno, y por la via del propio editor ──────────────
let editor = editorCon();
let v = ventanaCon(editor);
let rango = L.rangoElegido(editor, v);

bien(rango === "'Ejec. Tec. 2026'!B2:D20",
     'el intervalo sale RELLENO, con el nombre de la hoja: ' + rango);
bien(editor.tipoPedido === 'absoluta',
     'se pide en referencia absoluta, como hace el editor con los suyos');

// El editor lo devuelve como '$B$2:$D$20': la hoja y el formato los ponemos aqui.
editor = editorCon({ conHoja: true });
bien(L.rangoElegido(editor, ventanaCon(editor)) === "'Ejec. Tec. 2026'!B2:D20",
     'y si algun dia lo devolviera CON la hoja, no se pone dos veces');

// ── Si esa via no esta, se cae a la de antes ────────────────────────────
editor = editorCon({ sinDirecto: true });
rango = L.rangoElegido(editor, ventanaCon(editor));
bien(rango === "'Ejec. Tec. 2026'!B2:D20",
     'sin esa via, se arma a mano y sale igual: ' + rango);

editor = editorCon({ directoFalla: true });
rango = L.rangoElegido(editor, ventanaCon(editor));
bien(rango === "'Ejec. Tec. 2026'!B2:D20",
     'y si esa via revienta, tampoco se pierde el intervalo');

editor = editorCon({ directoVacio: true });
rango = L.rangoElegido(editor, ventanaCon(editor));
bien(rango === "'Ejec. Tec. 2026'!B2:D20",
     'ni si devuelve vacio');

// ── LO QUE FALLABA: si no se puede, se DICE ──────────────────────────────
contado.length = 0;
editor = editorCon({ sinDirecto: true, infoFalla: true });
rango = L.rangoElegido(editor, ventanaCon(editor));
bien(rango === '', 'cuando no hay manera, se devuelve vacio');
bien(contado.length === 1 && /intervalo vacio/.test(contado[0]),
     'pero YA NO SE QUEDA CALLADO: se cuenta por que');
bien(/sin hoja abierta/.test(contado[0]),
     'y se cuenta el motivo de verdad: ' + contado[0]);

contado.length = 0;
editor = editorCon({ sinDirecto: true, sinInfo: true });
L.rangoElegido(editor, ventanaCon(editor));
bien(/sin informacion de la celda/.test(contado[0] || ''),
     'con el editor a medio abrir, tambien se dice');

contado.length = 0;
editor = editorCon({ sinDirecto: true, sinRango: true });
L.rangoElegido(editor, ventanaCon(editor));
bien(/sin asc_getSelectionRange/.test(contado[0] || ''),
     'y si le falta esa pieza, tambien');

// ── Sin ventana no puede romperse ───────────────────────────────────────
editor = editorCon();
rango = L.rangoElegido(editor, null);
bien(rango === "'Ejec. Tec. 2026'!B2:D20",
     'sin ventana se usa la via de antes y sale igual');
console.log();
