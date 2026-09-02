/* El desplegable que sale al pulsar la flechita de una celda tiene que verse
   como el de Google. Aquí se comprueba que el estilo entra en la ventana del
   editor y que la marca acaba en el menú correcto —no en todos—. */

let repasar = null;
const puesto = { estilos: [], clases: [] };

function Elemento() {
    this.classList = {
        _c: [],
        contains: function (c) { return this._c.indexOf(c) !== -1; },
        add: function (c) { this._c.push(c); puesto.clases.push(c); }
    };
}

let menuHecho = null;              // el editor lo crea tarde
let alAbrirse = null;

const docEditor = {
    _hojas: {},
    getElementById: function (id) { return docEditor._hojas[id] || null; },
    createElement: function () { return { id: '', textContent: '' }; },
    head: {
        appendChild: function (hoja) {
            docEditor._hojas[hoja.id] = hoja;
            puesto.estilos.push(hoja);
        }
    },
    body: {},
    querySelectorAll: () => []
};

const ventanaEditor = {
    document: docEditor,
    Asc: { editor: {} },
    SSE: {
        getController: () => ({
            documentHolder: { get entriesMenu() { return menuHecho; } }
        })
    }
};

global.window = global;
global.document = {
    body: { appendChild() { }, removeChild() { } },
    head: { appendChild() { } },
    createElement: () => ({ style: {}, setAttribute() { }, appendChild() { },
                            querySelector: () => null, querySelectorAll: () => [] }),
    querySelectorAll: (s) => (s === 'iframe' ? [{ contentWindow: ventanaEditor }] : []),
    addEventListener() { }
};
global.setInterval = (fn) => { repasar = fn; return 1; };
global.console = console;

const B = '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';
require(B + 'editor-ventanas.js');
require(B + 'editor-desplegable-aspecto.js');

const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
console.log('\n[Drive Maquita] la forma del desplegable de la celda\n');

// ── El editor todavía no tiene ese menú ──────────────────────────────────
repasar();
bien(puesto.estilos.length === 0, 'sin el menu, no se toca nada');

// ── Ya lo tiene ──────────────────────────────────────────────────────────
const elMenu = new Elemento();
menuHecho = {
    cmpEl: [elMenu],
    on: function (evento, fn) { if (evento === 'show:after') alAbrirse = fn; return this; }
};
repasar();

bien(puesto.estilos.length === 1, 'el estilo entra una vez');
const css = puesto.estilos[0].textContent;
bien(puesto.estilos[0].id === 'maq-estilo-desplegable', 'con su nombre, para no repetirlo');
bien(/border-radius:8px/.test(css), 'la caja va redondeada, como la de Google');
bien(/border-radius:16px/.test(css), 'y cada opcion en pastilla de extremos redondeados');
bien(/box-shadow/.test(css), 'con sombra suave en vez del recuadro gris');
bien(/prefers-color-scheme: dark/.test(css), 'y acompaña en modo oscuro');
bien(elMenu.classList.contains('maq-desplegable'),
     'la marca va al menu de la celda, que es el unico que se viste');

// ── No se repite ─────────────────────────────────────────────────────────
const cuantos = puesto.estilos.length, marcas = puesto.clases.length;
repasar(); repasar();
bien(puesto.estilos.length === cuantos, 'el estilo no se mete dos veces');
alAbrirse();
bien(puesto.clases.length === marcas, 'ni la marca se repite al reabrirlo');

// ── Si el editor rehace su menu, se vuelve a marcar ──────────────────────
const otro = new Elemento();
menuHecho.cmpEl = [otro];
alAbrirse();
bien(otro.classList.contains('maq-desplegable'),
     'si el editor lo rehace, al abrirlo se viste otra vez');
console.log();
