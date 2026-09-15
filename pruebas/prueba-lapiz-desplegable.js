/* El lápiz del desplegable tiene que servir TODAS las veces, no solo la
   primera (aviso de Wilson, 10/09/2026).

   Fallaba así: al pulsarlo, el desplegable se escondía con `display:none` en
   línea; el editor lo reabría poniéndole otra vez la clase «open», pero el
   `display:none` seguía ahí y la lista salía invisible (0×0) con su lápiz. */

let repasar = null;

function Elemento(doc) {
    const yo = this;
    this.ownerDocument = doc;
    this.hijos = [];
    this.className = '';
    this.attrs = {};
    this.style = {
        display: '',
        removeProperty: function (p) { this[p] = ''; },
        setProperty: function (p, v) { this[p] = v; }
    };
    this.classList = {
        _c: [],
        contains: function (c) { return this._c.indexOf(c) !== -1; },
        add: function (c) { if (!this.contains(c)) this._c.push(c); },
        remove: function (c) { this._c = this._c.filter(x => x !== c); }
    };
    this.setAttribute = function (k, v) { yo.attrs[k] = v; };
    this.appendChild = function (h) { yo.hijos.push(h); return h; };
    this.querySelector = function (sel) {
        const clase = sel.replace(/^\./, '').split(' ')[0];
        const buscar = (n) => {
            for (const h of n.hijos) {
                if (h.className === clase) return sel.indexOf(' button') !== -1 ? h.hijos[0] : h;
                const r = buscar(h);
                if (r) return r;
            }
            return null;
        };
        return buscar(yo);
    };
    this.querySelectorAll = () => [];
}

const docEditor = {
    _hojas: {},
    getElementById: (id) => docEditor._hojas[id] || null,
    createElement: () => new Elemento(docEditor),
    head: { appendChild: (h) => { docEditor._hojas[h.id] = h; } },
    body: {},
    querySelectorAll: () => []
};
const elMenu = new Elemento(docEditor);
let alAbrirse = null;
const menu = {
    cmpEl: [elMenu],
    on: function (e, fn) { if (e === 'show:after') alAbrirse = fn; return this; },
    show: function () { }
};
const ventanaEditor = {
    document: docEditor,
    Asc: { editor: {} },
    SSE: { getController: () => ({ documentHolder: { entriesMenu: menu } }) }
};

global.window = global;
global.document = {
    body: { appendChild() { } }, head: { appendChild() { } },
    createElement: () => new Elemento(docEditor),
    querySelectorAll: (s) => (s === 'iframe' ? [{ contentWindow: ventanaEditor }] : []),
    addEventListener() { }
};
global.setInterval = (fn) => { repasar = fn; return 1; };
global.setTimeout = (fn) => fn();
global.console = { log() { }, warn() { } };

const cerrados = [];
const paneles = [];
window.MaquitaMenuCerrar = { cerrar: (v, m) => { cerrados.push(m); return true; } };
window.MaquitaListasMenu = { abrirPanel: (v) => { paneles.push(v); } };

const B = process.env.MAQ_JS
    || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';
require(B + 'editor-ventanas.js');
require(B + 'editor-desplegable-aspecto.js');

const bien = (r, q) => process.stdout.write((r ? 'OK  ' : 'MAL ') + q + '\n');
process.stdout.write('\n');

repasar();
const fila = elMenu.querySelector('.maq-lapiz-lista');
const boton = fila && fila.hijos[0];
bien(!!boton && typeof boton.onclick === 'function', 'el desplegable lleva su lápiz, y es un botón');

const clic = () => boton.onclick({ preventDefault() { }, stopPropagation() { } });

// ── Primera vez ─────────────────────────────────────────────────────────
clic();
bien(paneles.length === 1, 'la primera vez abre el panel de la lista');
bien(cerrados.length === 1 && cerrados[0] === menu, 'y cierra el desplegable como cualquier menú del editor');
bien(elMenu.style.display !== 'none', 'SIN dejarle un display:none pegado');

// ── Segunda y tercera vez: el editor lo reabre ──────────────────────────
alAbrirse();
bien(elMenu.style.display !== 'none', 'al reabrirse, el desplegable se ve');
clic();
bien(paneles.length === 2, 'la segunda vez el lápiz también abre el panel');
alAbrirse();
clic();
bien(paneles.length === 3 && cerrados.length === 3, 'y la tercera');

// ── Si alguien lo dejó escondido a mano, se cura al abrirse ─────────────
elMenu.style.display = 'none';
alAbrirse();
bien(elMenu.style.display === '', 'un display:none que quedara de antes se quita al abrirse');
bien(elMenu.hijos.filter(h => h.className === 'maq-lapiz-lista').length === 1, 'y el lápiz no se duplica');

// ── Sin el cerrador de menús, se pide al propio menú ────────────────────
delete window.MaquitaMenuCerrar;
let escondido = false;
menu.hide = () => { escondido = true; };
clic();
bien(escondido && elMenu.style.display !== 'none', 'sin MaquitaMenuCerrar, lo cierra menu.hide()');
