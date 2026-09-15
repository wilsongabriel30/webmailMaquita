/* Inmovilizar filas y columnas desde el clic derecho (10/09/2026).

   Se comprueba el núcleo (`editor-inmovilizar.js`: leer, fijar filas y
   columnas por separado, y la trampa de `asc_freezePane(undefined)`) y el menú
   (`editor-inmovilizar-menu.js`: dónde se pone, el «Congelar paneles» del
   editor escondido, los textos con la celda y las marcas). */

let repasar = null;
const llamadas = [];                    // lo que se le pide al editor
const buzon = [];                       // lo que se cuenta al diagnóstico
let fijo = null;                        // { fila, col } inmovilizados, o null
let activa = { row: 4, col: 3 };        // D5

// ── El editor simulado, con SOLO lo que tiene el de verdad ───────────────
const editor = {
    asc_getSheetViewSettings: () => ({
        pane: fijo ? { topLeftFrozenCell: { getRow0: () => fijo.fila, getCol0: () => fijo.col } } : null
    }),
    asc_freezePane: function (tipo, col, fila) {
        llamadas.push([tipo, col, fila]);
        if (tipo === null) { fijo = (col || fila) ? { fila: fila, col: col } : null; return; }
        // Sin nada fijo, el del editor inmoviliza en la celda activa: la trampa.
        fijo = fijo ? null : { fila: activa.row, col: activa.col };
    },
    wb: { getWorksheet: () => ({ model: { selectionRange: { get activeCell() { return activa; } } } }) }
};

function MenuItem(o) {
    this.caption = o.caption; this.value = o.value; this.menu = o.menu;
    this.visible = true; this.disabled = false; this.checked = false; this.eventos = {};
}
MenuItem.prototype.on = function (e, fn) { this.eventos[e] = fn; };
MenuItem.prototype.setCaption = function (t) { this.caption = t; };
MenuItem.prototype.setVisible = function (v) { this.visible = v; };
MenuItem.prototype.setDisabled = function (d) { this.disabled = d; };
MenuItem.prototype.isDisabled = function () { return this.disabled; };
MenuItem.prototype.setChecked = function (c) { this.checked = c; };
function Menu(o) {
    this.items = (o.items || []).map(i => new MenuItem(i));
    this.eventos = {};
}
Menu.prototype.on = function (e, fn) { this.eventos[e] = fn; };

const nativo = new MenuItem({ caption: 'Congelar paneles' });
let menu = null;
function menuDelEditor() {
    const m = new Menu({ items: [] });
    m.items = [new MenuItem({ caption: 'Enlace' }), new MenuItem({ caption: '--' }), nativo,
               new MenuItem({ caption: '--' }), new MenuItem({ caption: 'Crear lista desplegable' })];
    m.addItem = function (i) { this.items.push(i); };
    m.insertItem = function (n, i) { this.items.splice(n, 0, i); };
    return m;
}
let puedeEditar = true;
const ventanaEditor = {
    document: { body: {}, querySelectorAll: () => [] },
    Common: { UI: { MenuItem: MenuItem, Menu: Menu } },
    Asc: { editor: editor },
    SSE: {
        getController: () => ({
            permissions: { get isEdit() { return puedeEditar; } },
            documentHolder: { get ssMenu() { return menu; }, pmiFreezePanes: nativo }
        })
    }
};

global.window = global;
global.document = {
    body: { appendChild() { } }, head: { appendChild() { } },
    createElement: () => ({ style: {}, setAttribute() { }, appendChild() { } }),
    querySelectorAll: (s) => (s === 'iframe' ? [{ contentWindow: ventanaEditor }] : []),
    addEventListener() { }
};
global.setInterval = (fn) => { repasar = fn; return 1; };
global.setTimeout = (fn) => fn();       // lo del clic, en el acto
let alertado = '';
global.alert = (t) => { alertado = t; };
global.console = { log() { }, warn() { } };

const B = process.env.MAQ_JS
    || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';
require(B + 'editor-ventanas.js');
window.MaquitaDiagnostico = { contar: (m, d) => buzon.push(Object.assign({ momento: m }, d)) };
require(B + 'editor-inmovilizar.js');
require(B + 'editor-inmovilizar-menu.js');

const bien = (r, q) => process.stdout.write((r ? 'OK  ' : 'MAL ') + q + '\n');
const I = window.MaquitaInmovilizar;
const v = ventanaEditor;
process.stdout.write('\n');

// ── El núcleo ────────────────────────────────────────────────────────────
bien(I.leer(v).filas === 0 && I.leer(v).columnas === 0, 'sin nada fijo, lee 0 filas y 0 columnas');
bien(I.letra(0) === 'A' && I.letra(25) === 'Z' && I.letra(26) === 'AA' && I.letra(27) === 'AB',
     'las letras de columna: A, Z, AA, AB');
bien(I.celdaActiva(v).fila === 4 && I.celdaActiva(v).col === 3, 'la celda activa sale en índices (D5 = 4, 3)');

llamadas.length = 0;
I.fijar(v, 0, 0);
bien(llamadas.length === 0,
     'quitar sin nada fijo NO llama al editor (si no, congelaría en la celda activa)');

I.fijar(v, 3, 2);
bien(JSON.stringify(llamadas.pop()) === '[null,2,3]', 'fijar 3 filas y 2 columnas: asc_freezePane(null, 2, 3)');
bien(I.leer(v).filas === 3 && I.leer(v).columnas === 2, 'y se lee lo mismo');

I.filas(v, 1);
bien(I.leer(v).filas === 1 && I.leer(v).columnas === 2, 'cambiar las filas no toca las columnas');
I.columnas(v, 0);
bien(I.leer(v).filas === 1 && I.leer(v).columnas === 0, 'quitar las columnas deja las filas');

llamadas.length = 0;
bien(I.filas(v, 1).sinCambios === true && llamadas.length === 0, 'pedir lo que ya está no llama al editor');

I.fijar(v, 0, 0);
bien(JSON.stringify(llamadas.pop()) === '[null,null,null]' && I.leer(v).filas === 0,
     'quitarlo todo con algo fijo: asc_freezePane(undefined)');

const fallo = editor.asc_freezePane;
editor.asc_freezePane = () => { throw new Error('hoja bloqueada'); };
const r = I.fijar(v, 2, 0);
bien(r.ok === false && /bloqueada/.test(r.error), 'si el editor falla, se dice (no hay fallos mudos)');
bien(buzon.some(b => b.momento === 'inmovilizar' && /bloqueada/.test(b.error)), 'y llega al buzón de diagnóstico');
editor.asc_freezePane = fallo;

// ── El menú ──────────────────────────────────────────────────────────────
repasar();
bien(menu === null, 'sin menú todavía, no pasa nada');
menu = menuDelEditor();
repasar();
const pos = menu.items.indexOf(nativo);
const nuestro = menu.items[pos + 1];
bien(nuestro && nuestro.caption === 'Inmovilizar' && !!nuestro.menu,
     '«Inmovilizar» entra justo detrás del «Congelar paneles» del editor, con submenú');
bien(nativo.visible === false, 'el «Congelar paneles» del editor queda escondido');
const cuantos = menu.items.length;
repasar(); repasar();
bien(menu.items.length === cuantos, 'no se añade dos veces');

// El editor rellena el menú antes de enseñarlo.
nativo.setVisible(true);
bien(nuestro.visible === true && nativo.visible === false,
     'el editor pide ver el suyo: sale el nuestro y el suyo sigue escondido');
nativo.setVisible(false);
bien(nuestro.visible === false, 'escribiendo en una celda el editor esconde el suyo: el nuestro también');
nativo.setVisible(true);
nativo.setDisabled(true);
bien(nuestro.disabled === true, 'hoja bloqueada: el nuestro se bloquea igual');
nativo.setDisabled(false);
bien(nuestro.disabled === false, 'y se desbloquea igual');
bien(nativo.isVisible() === true, 'la raya de separación de encima se sigue poniendo');

// Al abrirse: textos con la celda del clic y marcas.
fijo = null;
menu.eventos['show:before']();
const sub = nuestro.menu.items;
const por = (val) => sub.filter(i => i.value === val)[0];
bien(por('fN').caption === 'Hasta la fila actual (5)', 'dice «Hasta la fila actual (5)»');
bien(por('cN').caption === 'Hasta la columna actual (D)', 'dice «Hasta la columna actual (D)»');
bien(por('fc').caption === 'Filas y columnas hasta la celda actual (D5)', 'y «… hasta la celda actual (D5)»');
bien(por('f0').checked && por('c0').checked && !por('f1').checked, 'sin nada fijo, marcadas «Sin filas» y «Sin columnas»');

// El caso que falló en la réplica: el editor repite el aviso al abrir el submenú.
menu.eventos['show:before']();
menu.eventos['show:before']();
bien(nuestro.visible === true, 'abrir el submenú (avisos repetidos) no esconde «Inmovilizar»');

// Elegir.
const elegir = (val) => nuestro.menu.eventos['item:click'](nuestro.menu, por(val));
elegir('fN');
bien(I.leer(v).filas === 5 && I.leer(v).columnas === 0, '«Hasta la fila actual» deja 5 filas fijas');
elegir('c2');
bien(I.leer(v).filas === 5 && I.leer(v).columnas === 2, '«2 columnas» añade columnas sin quitar las filas');
menu.eventos['show:before']();
bien(por('fN').checked && por('c2').checked && !por('f0').checked, 'y el menú lo marca');
elegir('f0');
bien(I.leer(v).filas === 0 && I.leer(v).columnas === 2, '«Sin filas» deja las columnas');
elegir('c0');
bien(fijo === null, '«Sin columnas» con las filas ya quitadas: nada fijo');
activa = { row: 1, col: 1 };            // B2
elegir('fc');
bien(I.leer(v).filas === 2 && I.leer(v).columnas === 2, '«hasta la celda actual» en B2: 2 filas y 2 columnas');

puedeEditar = false;
alertado = '';
elegir('f1');
bien(/solo para lectura/.test(alertado) && I.leer(v).filas === 2, 'en solo lectura avisa y no toca nada');
