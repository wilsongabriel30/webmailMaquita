/* PULSAR «HECHO» DE VERDAD.

   Wilson: «ya no me deja presionar en hecho». Y el diagnóstico no registraba ni
   un «aplicar lista»: el botón ni llegaba a hacer su trabajo.

   Ninguna prueba pulsaba el botón: todas llamaban a `aplicar()` por su cuenta.
   Esta recorre el camino entero —abrir el panel, escribir, pulsar Hecho— que es
   por donde pasa la persona.

   Se ejecuta con:  node prueba-pulsar-hecho.js  */

const B = process.env.MAQ_JS
    || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';

// ── DOM de mentira, con un analizador mínimo de HTML ─────────────────────
function Elemento(etiqueta) {
    this.etiqueta = etiqueta;
    this.hijos = [];
    this.style = {};
    this.dataset = {};
    this.clases = [];
    this.oyentes = {};
    this.value = '';
    this.textContent = '';
    this.className = '';
    this.hidden = false;
}
Elemento.prototype.appendChild = function (h) { this.hijos.push(h); h.parentNode = this; return h; };
Elemento.prototype.insertBefore = function (h, ref) {
    const donde = ref ? this.hijos.indexOf(ref) : -1;
    if (donde === -1) this.hijos.push(h); else this.hijos.splice(donde, 0, h);
    h.parentNode = this; return h;
};
Elemento.prototype.removeChild = function (h) {
    const i = this.hijos.indexOf(h);
    if (i !== -1) this.hijos.splice(i, 1);
    return h;
};
Elemento.prototype.setAttribute = function () { };
Elemento.prototype.addEventListener = function (n, fn) { (this.oyentes[n] = this.oyentes[n] || []).push(fn); };
Elemento.prototype.removeEventListener = function () { };
Elemento.prototype.getBoundingClientRect = function () {
    return { top: 0, height: 20, left: 0, bottom: 20, width: 200 };
};
Elemento.prototype.focus = function () { };
Elemento.prototype.select = function () { };
Object.defineProperty(Elemento.prototype, 'classList', {
    get: function () {
        const self = this;
        return { add: (c) => { if (self.clases.indexOf(c) === -1) self.clases.push(c); },
                 remove: (c) => { const i = self.clases.indexOf(c); if (i !== -1) self.clases.splice(i, 1); },
                 toggle: () => { }, contains: (c) => self.clases.indexOf(c) !== -1 };
    }
});
const SUELTAS = ['input', 'br', 'hr', 'img', 'path', 'circle'];
function analizar(html, padre) {
    String(html).split(/(<[^>]+>)/).forEach(function (t) {
        if (!t) return;
        if (t.charAt(0) !== '<') { padre.textContent += t; return; }
        if (t.charAt(1) === '/') { if (padre.__actual) padre.__actual = padre.__actual.parentNode; return; }
        const etiqueta = (/^<\s*([a-zA-Z0-9]+)/.exec(t) || [])[1] || 'div';
        const hijo = new Elemento(etiqueta);
        const clase = /class="([^"]*)"/.exec(t);
        if (clase) hijo.className = clase[1];
        const tipo = /type="([^"]*)"/.exec(t);
        if (tipo) hijo.type = tipo[1];
        const nombre = /name="([^"]*)"/.exec(t);
        if (nombre) hijo.name = nombre[1];
        (padre.__actual || padre).appendChild(hijo);
        if (t.slice(-2) !== '/>' && SUELTAS.indexOf(etiqueta.toLowerCase()) === -1) {
            padre.__actual = hijo;
        }
    });
    padre.__actual = null;
}
function clasesDe(e) {
    return String(e.className || '').split(/\s+/).concat(e.clases || []).filter(Boolean);
}
function todos(raiz, sel, salida) {
    salida = salida || [];
    raiz.hijos.forEach(function (h) {
        if (sel.charAt(0) === '.' && clasesDe(h).indexOf(sel.slice(1)) !== -1) salida.push(h);
        else if (sel.charAt(0) === '[' ) {
            const m = /\[name="([^"]+)"\]/.exec(sel);
            if (m && h.name === m[1]) salida.push(h);
        } else if (h.etiqueta === sel) salida.push(h);
        todos(h, sel, salida);
    });
    return salida;
}
Elemento.prototype.querySelectorAll = function (s) { return todos(this, s); };
Elemento.prototype.querySelector = function (s) { return todos(this, s)[0] || null; };
Object.defineProperty(Elemento.prototype, 'innerHTML', {
    get: function () { return this._html || ''; },
    set: function (v) { this._html = v; this.hijos = []; this.textContent = ''; analizar(v, this); }
});

const cuerpo = new Elemento('body');
global.window = global;
global.console = console;
global.document = {
    body: cuerpo, head: new Elemento('head'),
    createElement: (t) => new Elemento(t),
    querySelector: (s) => cuerpo.querySelector(s),
    querySelectorAll: (s) => cuerpo.querySelectorAll(s),
    addEventListener: () => { }, getElementById: () => null
};

// ── El editor, como el de verdad ─────────────────────────────────────────
const TIPOS = { List: 'lista', None: 'ninguna' };
const HOJA = 5;
let puestas = [];
let guardada = null;

function Formula() { }
Formula.prototype.asc_setValue = function (v) { this.valor = v; };
Formula.prototype.asc_getValue = function () { return this.valor; };
function Validacion() { }
['Type', 'Formula1', 'Formula2', 'Operator', 'ShowDropDown', 'AllowBlank',
 'ShowErrorMessage', 'ErrorStyle', 'ErrorTitle', 'Error', 'ShowInputMessage',
 'PromptTitle', 'Prompt'].forEach(function (n) {
    Validacion.prototype['asc_set' + n] = function (v) { this[n] = v; };
});
Validacion.prototype.asc_getType = function () { return this.Type; };
Validacion.prototype.asc_getFormula1 = function () { return this.Formula1; };
function Regla() { }
Regla.prototype.asc_setType = function () { };
Regla.prototype.asc_setOperator = function () { };
Regla.prototype.asc_setValue1 = function (v) { this.valor = v; };
Regla.prototype.asc_getValue1 = function () { return this.valor; };
Regla.prototype.asc_setDxf = function (v) { this.formato = v; };
Regla.prototype.asc_getDxf = function () { return this.formato; };
Regla.prototype.asc_setLocation = function () { };
function Formato() { }
Formato.prototype.asc_setFillColor = function (c) { this.relleno = c; };
Formato.prototype.asc_getFillColor = function () { return this.relleno; };

const ventanaEditor = {
    document: global.document,
    Common: { Utils: { ThemeColor: { getRgbColor: (h) => ({
        get_r: () => parseInt(h.substr(0, 2), 16),
        get_g: () => parseInt(h.substr(2, 2), 16),
        get_b: () => parseInt(h.substr(4, 2), 16) }) } } },
    Asc: {
        c_oAscEDataValidationType: TIPOS,
        c_oAscCFType: { cellIs: 'celda-es' },
        c_oAscCFOperator: { equal: 'igual' },
        c_oAscEDataValidationErrorStyle: { Stop: 'rechaza', Warning: 'avisa' },
        c_oAscEDataValidationOperator: {},
        CDataFormula: Formula,
        asc_CConditionalFormattingRule: Regla,
        asc_CellXfs: Formato,
        referenceType: { A: 0 },
        editor: {
            asc_getActiveWorksheetIndex: () => HOJA,
            asc_getWorksheetName: () => 'Hoja1',
            asc_getActiveRangeStr: () => 'B2',
            asc_getDataValidationProps: () => new Validacion(),
            asc_setDataValidation: (v) => {
                const dado = String((v.Formula1 && v.Formula1.asc_getValue()) || '');
                guardada = '"' + dado.replace(/"/g, '""') + '"';
            },
            asc_setCF: (reglas) => {
                if (reglas && reglas[HOJA]) puestas = puestas.concat(reglas[HOJA]);
            },
            asc_getCF: () => [puestas],
            asc_getCellInfo: () => ({
                asc_getSelectionRange: () => 'B2',
                asc_getDataValidation: () => (guardada === null ? null : {
                    asc_getType: () => TIPOS.List,
                    asc_getFormula1: () => ({ asc_getValue: () => guardada })
                })
            })
        }
    }
};

require(B + 'editor-lista-criterios.js');
require(B + 'editor-lista-colores-cf.js');
require(B + 'editor-lista-memoria.js');
require(B + 'editor-rango-a1.js');
require(B + 'editor-lista-aplicar.js');
require(B + 'editor-lista-panel.js');

let bien = 0, mal = 0;
const comprueba = (r, q) => { r ? bien++ : mal++; console.log((r ? 'OK  ' : 'MAL ') + q); };
console.log();

// ── Abrir el panel, como lo abre el clic derecho ────────────────────────
let resultado = null;
window.MaquitaListaPanel.abrir({
    ventana: ventanaEditor,
    donde: 'Hoja1!B2:B20',
    valores: window.MaquitaListas.leerElementos(ventanaEditor),
    alAceptar: function (elementos, ajustes) {
        return window.MaquitaListas.aplicar(ventanaEditor, elementos, ajustes);
    },
    alQuitar: function () { }
});
const panel = document.querySelector('.maq-ld-panel') || cuerpo.hijos[cuerpo.hijos.length - 1];
comprueba(!!panel, 'el panel se abre');

const hecho = document.querySelector('.maq-ld-hecho');
comprueba(!!hecho && typeof hecho.onclick === 'function', 'el botón «Hecho» está ahí');

// ── PULSARLO. Esto es lo que fallaba. ───────────────────────────────────
let reventó = null;
try {
    hecho.onclick();
} catch (e) {
    reventó = e;
}
comprueba(reventó === null,
          'al pulsar «Hecho» no revienta' + (reventó ? ': ' + reventó.message : ''));
comprueba(guardada === '"Opción 1,Opción 2"',
          'y la lista queda aplicada: ' + guardada);
comprueba(puestas.length === 2,
          'con sus dos reglas de color: ' + puestas.length);
comprueba(document.querySelectorAll('.maq-ld-panel').length === 0
          || !document.querySelector('.maq-ld-hecho'),
          'y el panel se cierra solo, como debe');

console.log('\n' + bien + ' bien, ' + mal + ' mal\n');
process.exit(mal ? 1 : 0);
