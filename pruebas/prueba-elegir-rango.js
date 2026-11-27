/* Marcar el intervalo con el ratón en la propia hoja, como en Google.
   Lo que se comprueba: que el marcado se apoya en la selección NORMAL de la
   hoja —no en un modo especial que puede no arrancar—, y que al terminar se
   suelta todo, porque si no la hoja se queda sin dejar escribir. */

const pasado = { modo: [], registrados: [], quitados: [] };
const TIPOS = { None: 0, Chart: 2, DataValidation: 10 };

let rangoEnLaHoja = "'Ejec. Tec. 2026'!B2:D20";

function editorCon(opciones) {
    opciones = opciones || {};
    const editor = {
        asc_registerCallback: function (nombre, fn) {
            if (opciones.noEscucha) throw new Error('no escucho');
            pasado.registrados.push(nombre);
            // para simular que se marca: la selección normal y el aviso del modo
            if (nombre === 'asc_onSelectionChanged') editor.avisar = fn;
            if (nombre === 'asc_onSelectionRangeChanged') editor.avisarModo = fn;
        },
        asc_unregisterCallback: function (nombre) { pasado.quitados.push(nombre); },
        asc_getActiveRangeStr: function () { return rangoEnLaHoja; }
    };
    if (!opciones.sinModo) {
        editor.asc_setSelectionDialogMode = function (tipo, inicial) {
            if (opciones.modoFalla && tipo !== TIPOS.None) throw new Error('sin modo');
            pasado.modo.push({ tipo: tipo, inicial: inicial });
        };
    }
    return editor;
}

function ventanaCon(editor) {
    return {
        Asc: {
            editor: editor,
            c_oAscSelectionDialogType: TIPOS,
            referenceType: { A: 'absoluta' }
        }
    };
}

global.window = global;
global.console = console;

require('/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/editor-elegir-rango.js');

const R = window.MaquitaElegirRango;
const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
console.log('\n[Drive Maquita] marcar el intervalo en la hoja\n');

// ── Lo normal: se marca en la hoja y llega ───────────────────────────────
let marcado = [];
let editor = editorCon();
let v = ventanaCon(editor);
let arranco = R.empezar(v, { inicial: 'A1:A5', alCambiar: (r) => marcado.push(r) });

bien(arranco === true, 'se queda escuchando la hoja');
bien(R.marcando() === true, 'y queda constancia de que esta en ello');
bien(pasado.registrados[0] === 'asc_onSelectionChanged',
     'lo que se escucha es la seleccion NORMAL, la de siempre');
bien(pasado.modo[0] && pasado.modo[0].tipo === TIPOS.DataValidation,
     'y de paso se pide el marco de puntos');

editor.avisar();
rangoEnLaHoja = "'Ejec. Tec. 2026'!B2:D40";
editor.avisar();
bien(marcado.join(' > ') === "'Ejec. Tec. 2026'!B2:D20 > 'Ejec. Tec. 2026'!B2:D40",
     'cada cambio llega segun se marca, con el nombre de la hoja');

// ── 27/11/2026: CON el modo puesto, OnlyOffice 10 avisa por OTRO lado ───
// (asc_onSelectionRangeChanged, con el intervalo en el texto) y la selección
// normal no se mueve. Era lo que fallaba al marcar el origen de una lista.
bien(pasado.registrados.indexOf('asc_onSelectionRangeChanged') >= 0,
     'tambien se escucha el aviso del modo de elegir rango');
marcado = [];
rangoEnLaHoja = 'A1';                         // la seleccion normal, quieta
editor.avisarModo('Datos!$E$4:$E$119');
editor.avisarModo('=Datos!$E$4:$E$82');
bien(marcado.join(' > ') === 'Datos!$E$4:$E$119 > Datos!$E$4:$E$82',
     'lo marcado con el modo llega al campo (tambien con «=» delante)');
editor.avisar();
bien(marcado.length === 2,
     'y la seleccion normal, quieta, ya no pisa lo marcado');
editor.avisarModo('');
bien(marcado.length === 2, 'un aviso vacio no borra el campo');

// ── Y se suelta todo ─────────────────────────────────────────────────────
R.parar();
bien(R.marcando() === false, 'al parar, deja de estar marcando');
bien(pasado.quitados[0] === 'asc_onSelectionChanged'
     && pasado.quitados[1] === 'asc_onSelectionRangeChanged', 'se deja de escuchar (los dos avisos)');
bien(pasado.modo[pasado.modo.length - 1].tipo === TIPOS.None,
     'y el modo se apaga: la hoja vuelve a dejar escribir');

// ── LO QUE FALLABA: sin ese modo, el marcado tiene que seguir ────────────
pasado.modo = []; pasado.registrados = []; pasado.quitados = [];
marcado = [];
editor = editorCon({ modoFalla: true });
arranco = R.empezar(ventanaCon(editor), { alCambiar: (r) => marcado.push(r) });
bien(arranco === true, 'si el marco de puntos no arranca, se marca IGUAL');
editor.avisar();
bien(marcado.length === 1, 'y lo marcado llega: esto es lo que no funcionaba');
R.parar();
bien(pasado.modo.length === 0,
     'lo que no se puso, no se intenta quitar');

// ── Un editor viejo, sin ese modo siquiera ───────────────────────────────
marcado = [];
editor = editorCon({ sinModo: true });
bien(R.empezar(ventanaCon(editor), { alCambiar: (r) => marcado.push(r) }) === true,
     'con un editor que ni tenga ese modo, tambien se marca');
editor.avisar();
bien(marcado.length === 1, 'y llega igual');
R.parar();

// ── Lo que no puede romperse ─────────────────────────────────────────────
bien(R.empezar(ventanaCon(editorCon({ noEscucha: true })), {}) === false,
     'si no se puede escuchar la hoja, se avisa a quien lo pidio');
bien(R.marcando() === false, 'y no se queda a medias');
bien(R.empezar({}, {}) === false, 'sin editor tampoco se rompe');

const cuantos = pasado.quitados.length;
R.parar();
bien(pasado.quitados.length === cuantos, 'parar sin estar marcando no hace nada');

// Empezar dos veces no acumula escuchas.
pasado.quitados = [];
editor = editorCon();
v = ventanaCon(editor);
R.empezar(v, {});
R.empezar(v, {});
bien(pasado.quitados.length === 2, 'al empezar de nuevo se suelta lo de antes');

// Un fallo del panel al recibir el rango no tumba el marcado.
R.empezar(v, { alCambiar: function () { throw new Error('fallo del panel'); } });
editor.avisar();
bien(R.marcando() === true, 'un fallo al recibir el rango no tumba el marcado');
R.parar();
bien(R.marcando() === false, 'y se puede soltar igualmente');
console.log();
