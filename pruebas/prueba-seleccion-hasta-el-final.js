/* Simulacro del editor: se comprueba QUÉ movimiento se le pide al pulsar
   Ctrl+Shift+flecha, y que el resto de teclas siguen su curso.

   El editor mide el movimiento con un número: 1 = una celda, 1.5 = hasta el
   siguiente bloque, 2.5 = hasta el extremo de la hoja. */

const pedidos = [];
let editandoCelda = false;

const ventanaEditor = {
    document: {
        body: {},
        querySelectorAll: () => [],
        addEventListener(suceso, fn, captura) {
            if (suceso === 'keydown') this._teclado = fn;
        }
    },
    Asc: { editor: {
        asc_getCellEditMode: () => editandoCelda,
        wb: {
            _onChangeSelection(esInicio, dc, dr, esCoord, esCtrl) {
                pedidos.push({ dc: dc, dr: dr });
            }
        }
    } }
};

global.window = global;
global.document = { querySelectorAll: (s) => (s === 'iframe' ? [{ contentWindow: ventanaEditor }] : []) };
global.setInterval = () => 1;
global.console = console;

require('/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/editor-ventanas.js');
require('/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/editor-seleccion-hasta-el-final.js');

const teclado = ventanaEditor.document._teclado;

function pulsar(tecla, opciones) {
    opciones = opciones || {};
    let frenada = false;
    const e = {
        key: tecla,
        ctrlKey: opciones.ctrl !== false,
        shiftKey: opciones.shift !== false,
        altKey: !!opciones.alt,
        metaKey: !!opciones.meta,
        preventDefault() { frenada = true; },
        stopImmediatePropagation() { }
    };
    pedidos.length = 0;
    teclado(e);
    return { pedido: pedidos[0] || null, frenada: frenada };
}

const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
console.log();

// ── Lo que se pedía ──────────────────────────────────────────────────────
let r = pulsar('ArrowDown');
bien(r.pedido && r.pedido.dr === 2.5 && r.pedido.dc === 0 && r.frenada,
     'Ctrl+Shift+abajo: hasta el final de la hoja');

r = pulsar('ArrowUp');
bien(r.pedido && r.pedido.dr === -2.5 && r.pedido.dc === 0,
     'Ctrl+Shift+arriba: hasta la primera fila');

r = pulsar('ArrowRight');
bien(r.pedido && r.pedido.dc === 2.5 && r.pedido.dr === 0,
     'Ctrl+Shift+derecha: hasta la ultima columna');

r = pulsar('ArrowLeft');
bien(r.pedido && r.pedido.dc === -2.5 && r.pedido.dr === 0,
     'Ctrl+Shift+izquierda: hasta la primera columna');

// ── Lo que NO se debe tocar ──────────────────────────────────────────────
r = pulsar('ArrowDown', { shift: false });
bien(!r.pedido && !r.frenada, 'Ctrl+abajo (sin Shift) sigue como siempre');

r = pulsar('ArrowDown', { ctrl: false });
bien(!r.pedido && !r.frenada, 'Shift+abajo (sin Ctrl) sigue como siempre');

r = pulsar('ArrowDown', { alt: true });
bien(!r.pedido && !r.frenada, 'con Alt no se toca');

r = pulsar('a');
bien(!r.pedido && !r.frenada, 'escribir una letra no se toca');

r = pulsar('Home');
bien(!r.pedido && !r.frenada, 'Ctrl+Shift+Inicio sigue siendo del editor');

// Dentro de una celda, Ctrl+Shift+flecha selecciona TEXTO.
editandoCelda = true;
r = pulsar('ArrowDown');
bien(!r.pedido && !r.frenada, 'escribiendo dentro de una celda no se toca');
editandoCelda = false;

// En Mac la tecla es Cmd.
r = pulsar('ArrowDown', { ctrl: false, meta: true });
bien(r.pedido && r.pedido.dr === 2.5, 'en Mac, Cmd+Shift+abajo tambien');

// Si el editor no ofrece la pieza, la tecla NO se frena.
const guardado = ventanaEditor.Asc.editor.wb._onChangeSelection;
delete ventanaEditor.Asc.editor.wb._onChangeSelection;
r = pulsar('ArrowDown');
bien(!r.frenada, 'si el editor cambia por dentro, la tecla sigue su curso');
ventanaEditor.Asc.editor.wb._onChangeSelection = guardado;
