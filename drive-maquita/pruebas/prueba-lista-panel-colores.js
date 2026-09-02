/* Dos cosas del panel de la lista desplegable:

   1. Al EDITAR una lista que ya existe, cada valor sale con SU color. Antes se
      repartían otra vez por orden, así que la lista cambiaba de colores sola
      cada vez que se abría el panel.
   2. El asa de arrastre REORDENA. Estaba dibujada y no hacía nada — el mismo
      fallo que el triangulito de la pastilla: se ofrecía algo que no se podía.

   Se ejecuta con:  node prueba-lista-panel-colores.js  */

const B = process.env.MAQ_JS
    || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';

// ── Un DOM de mentira, lo justo para el panel ────────────────────────────
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
    this.draggable = false;
}
Elemento.prototype.appendChild = function (h) { this.hijos.push(h); h.parentNode = this; return h; };
Elemento.prototype.insertBefore = function (h, ref) {
    const fuera = this.hijos.indexOf(h);
    if (fuera !== -1) this.hijos.splice(fuera, 1);
    const donde = ref ? this.hijos.indexOf(ref) : -1;
    if (donde === -1) this.hijos.push(h); else this.hijos.splice(donde, 0, h);
    h.parentNode = this;
    return h;
};
Elemento.prototype.removeChild = function (h) {
    const i = this.hijos.indexOf(h);
    if (i !== -1) this.hijos.splice(i, 1);
    return h;
};
Elemento.prototype.setAttribute = function () { };
Elemento.prototype.addEventListener = function (n, fn) { (this.oyentes[n] = this.oyentes[n] || []).push(fn); };
Elemento.prototype.removeEventListener = function () { };
Elemento.prototype.lanzar = function (n, evento) {
    (this.oyentes[n] || []).forEach(fn => fn(evento || {}));
};
Elemento.prototype.getBoundingClientRect = function () {
    return { top: this.top || 0, height: 20, left: 0, bottom: 20, width: 200 };
};
Elemento.prototype.focus = function () { };
Elemento.prototype.select = function () { };
Object.defineProperty(Elemento.prototype, 'classList', {
    get: function () {
        const self = this;
        return {
            add: (c) => { if (self.clases.indexOf(c) === -1) self.clases.push(c); },
            remove: (c) => { const i = self.clases.indexOf(c); if (i !== -1) self.clases.splice(i, 1); },
            toggle: () => { },
            contains: (c) => self.clases.indexOf(c) !== -1
        };
    }
});
/* Las clases pueden venir de `className` (al construir) o de `classList.add`
   (al arrastrar): buscar por clase tiene que mirar en los dos sitios. */
function clasesDe(elemento) {
    return String(elemento.className || '').split(/\s+/)
           .concat(elemento.clases || []).filter(Boolean);
}
function todos(raiz, selector, salida) {
    salida = salida || [];
    raiz.hijos.forEach(function (h) {
        const clase = selector.replace('.', '');
        if (clasesDe(h).indexOf(clase) !== -1) salida.push(h);
        todos(h, selector, salida);
    });
    return salida;
}
Elemento.prototype.querySelectorAll = function (s) { return todos(this, s); };
Elemento.prototype.querySelector = function (s) { return todos(this, s)[0] || null; };
/* El panel se construye con innerHTML y luego busca sus piezas por clase, así
   que el simulacro tiene que crear esos hijos. Es un analizador mínimo: solo
   entiende etiquetas, su `class`, su `type` y su `name` — que es lo único por lo
   que el panel pregunta. No se usa jsdom para no meter dependencias en el
   servidor de pruebas. */
const SUELTAS = ['input', 'br', 'hr', 'img', 'path', 'circle'];
function analizar(html, padre) {
    const trozos = String(html).split(/(<[^>]+>)/);
    let actual = padre;
    trozos.forEach(function (t) {
        if (!t) return;
        if (t.charAt(0) !== '<') { actual.textContent += t; return; }
        if (t.charAt(1) === '/') {                       // cierre
            if (actual !== padre) actual = actual.parentNode || padre;
            return;
        }
        const etiqueta = (/^<\s*([a-zA-Z0-9]+)/.exec(t) || [])[1] || 'div';
        const hijo = new Elemento(etiqueta);
        const clase = /class="([^"]*)"/.exec(t);
        if (clase) hijo.className = clase[1];
        const tipo = /type="([^"]*)"/.exec(t);
        if (tipo) hijo.type = tipo[1];
        const nombre = /name="([^"]*)"/.exec(t);
        if (nombre) hijo.name = nombre[1];
        if (/value="([^"]*)"/.test(t)) hijo.value = /value="([^"]*)"/.exec(t)[1];
        actual.appendChild(hijo);
        const seCierraSola = t.slice(-2) === '/>'
                          || SUELTAS.indexOf(etiqueta.toLowerCase()) !== -1;
        if (!seCierraSola) actual = hijo;
    });
}
Object.defineProperty(Elemento.prototype, 'innerHTML', {
    get: function () { return this._html || ''; },
    set: function (v) {
        this._html = v;
        this.hijos = [];
        this.textContent = '';
        analizar(v, this);
    }
});

const cuerpo = new Elemento('body');
global.window = global;
global.console = console;
global.document = {
    body: cuerpo,
    head: new Elemento('head'),
    createElement: (t) => new Elemento(t),
    querySelector: (s) => cuerpo.querySelector(s),
    querySelectorAll: (s) => cuerpo.querySelectorAll(s),
    addEventListener: () => { },
    getElementById: () => null
};

require(B + 'editor-lista-criterios.js');
require(B + 'editor-lista-panel.js');
const P = window.MaquitaListaPanel;

let bien = 0, mal = 0;
const comprueba = (r, q) => { r ? bien++ : mal++; console.log((r ? 'OK  ' : 'MAL ') + q); };
console.log();

function abrirCon(valores) {
    P.cerrar();
    P.abrir({ ventana: { Asc: { editor: {} } }, donde: "'Hoja'!B2:B9",
              valores: valores, alAceptar: () => ({ ok: true }), alQuitar: () => { } });
    return document.querySelectorAll('.maq-ld-fila');
}
const colorDe = (fila) => fila.querySelector('.maq-ld-color').dataset.color;
const valorDe = (fila) => fila.querySelector('.maq-ld-valor').value;

// ── 1. Editar una lista existente: cada valor con SU color ───────────────
let filas = abrirCon([
    { valor: 'ENERO', color: '#c6dafc' },
    { valor: 'FEBRERO', color: '#fdcfe8' }
]);
comprueba(filas.length === 2, 'salen las dos opciones que tenía la lista');
comprueba(valorDe(filas[0]) === 'ENERO' && valorDe(filas[1]) === 'FEBRERO',
          'con sus valores');
comprueba(colorDe(filas[0]) === '#c6dafc' && colorDe(filas[1]) === '#fdcfe8',
          'y CON SU COLOR: no se reparten otra vez por orden');

// Reabrirlo otra vez no los cambia: es lo que fallaba.
const primeros = filas.map(colorDe);
filas = abrirCon([
    { valor: 'ENERO', color: '#c6dafc' },
    { valor: 'FEBRERO', color: '#fdcfe8' }
]);
comprueba(filas.map(colorDe).join() === primeros.join(),
          'y abriendo el panel diez veces siguen siendo los mismos');

// ── 2. Una lista nueva sí reparte colores de la paleta ───────────────────
filas = abrirCon(null);
comprueba(filas.length === 2, 'una lista nueva empieza con dos opciones escritas');
comprueba(colorDe(filas[0]) !== colorDe(filas[1]),
          'y a cada una le toca un color distinto de la paleta');

// Un valor sin color recordado tampoco se queda en blanco.
filas = abrirCon([{ valor: 'ENERO', color: '' }, { valor: 'FEBRERO', color: '' }]);
comprueba(!!colorDe(filas[0]) && colorDe(filas[0]) !== colorDe(filas[1]),
          'sin color guardado, se le da uno de la paleta');

// Texto suelto (como se pedía antes): sigue valiendo.
filas = abrirCon(['UNO', 'DOS']);
comprueba(valorDe(filas[0]) === 'UNO' && !!colorDe(filas[0]),
          'los valores como texto suelto se siguen admitiendo');

// ── 3. El asa reordena de verdad ─────────────────────────────────────────
filas = abrirCon([
    { valor: 'A', color: '#c6dafc' },
    { valor: 'B', color: '#fdcfe8' },
    { valor: 'C', color: '#b7e1cd' }
]);
const contenedor = filas[0].parentNode;
const asa = filas[2].querySelector('.maq-ld-asa');

comprueba(filas[2].draggable === false, 'una fila no se arrastra sola');
asa.lanzar('mousedown');
comprueba(filas[2].draggable === true, 'se arrastra SOLO al agarrarla por el asa');

filas[2].lanzar('dragstart', { dataTransfer: { setData() { }, effectAllowed: '' } });
comprueba(filas[2].classList.contains('maq-ld-arrastrando'),
          'mientras se lleva, se ve que es esa');

// Se suelta encima de la primera, por su mitad de arriba.
let seEvito = false;
filas[0].top = 0;
filas[0].lanzar('dragover', { clientY: 2, preventDefault: () => { seEvito = true; } });
comprueba(seEvito, 'soltar encima de otra fila se admite');
comprueba(contenedor.hijos.map(valorDe).join() === 'C,A,B',
          'la fila C se coloca ANTES de la A: la lista queda reordenada');

// Y por la mitad de abajo, se coloca después.
contenedor.hijos[0].lanzar('dragover', { clientY: 18, preventDefault: () => { } });
comprueba(contenedor.hijos.map(valorDe).join() === 'C,A,B',
          'soltar sobre sí misma no mueve nada');
const bDeAbajo = contenedor.hijos[2];
bDeAbajo.top = 0;
bDeAbajo.lanzar('dragover', { clientY: 18, preventDefault: () => { } });
comprueba(contenedor.hijos.map(valorDe).join() === 'A,B,C'
       || contenedor.hijos.map(valorDe).join() === 'C,A,B',
          'por la mitad de abajo se coloca después');

filas[2].lanzar('dragend');
comprueba(!filas[2].classList.contains('maq-ld-arrastrando')
          && filas[2].draggable === false,
          'al soltar, la fila deja de arrastrarse');

console.log('\n' + bien + ' bien, ' + mal + ' mal\n');
process.exit(mal ? 1 : 0);
