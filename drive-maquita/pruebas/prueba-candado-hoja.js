/* Al proteger una hoja, su pestaña de abajo debe llevar un candadito, para
   saber de un vistazo cuáles están protegidas (pedido por Wilson el
   02/09/2026).

   Lo que más importa aquí: que se empareje POR NOMBRE y no por posición —con
   hojas ocultas, la tercera pestaña no es la tercera hoja— y que el candado se
   QUITE al desproteger.

   Se ejecuta con:  node prueba-candado-hoja.js  */

const B = process.env.MAQ_JS
    || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';

// ── Un DOM mínimo: las pestañas de abajo ─────────────────────────────────
function Elemento(etiqueta) {
    this.etiqueta = etiqueta;
    this.hijos = [];
    this.style = {};
    this.className = '';
    this.textContent = '';
}
Elemento.prototype.appendChild = function (h) { this.hijos.push(h); h.parentNode = this; return h; };
Elemento.prototype.removeChild = function (h) {
    const i = this.hijos.indexOf(h);
    if (i !== -1) this.hijos.splice(i, 1);
    return h;
};
Elemento.prototype.querySelectorAll = function (sel) {
    const salida = [];
    const busca = (n) => n.hijos.forEach(function (h) {
        if (sel === 'li' && h.etiqueta === 'li') salida.push(h);
        if (sel.charAt(0) === '.' && h.className === sel.slice(1)) salida.push(h);
        busca(h);
    });
    busca(this);
    return salida;
};
Elemento.prototype.querySelector = function (sel) {
    if (sel === 'span') {
        const dentro = this.hijos.filter(h => h.etiqueta === 'span');
        return dentro[0] || null;
    }
    return this.querySelectorAll(sel)[0] || null;
};

// Cuatro pestañas; la hoja «Oculta» NO tiene pestaña.
const barra = new Elemento('div');
['Buscador', 'Ejec. Tec. 2026', 'Consolidado', 'Hoja1'].forEach(function (nombre) {
    const li = new Elemento('li');
    const span = new Elemento('span');
    span.textContent = nombre;
    li.appendChild(span);
    barra.appendChild(li);
});

// Las hojas del libro: la 1 está oculta y no sale abajo.
const HOJAS = ['Buscador', 'Oculta', 'Ejec. Tec. 2026', 'Consolidado', 'Hoja1'];
let protegidas = {};                      // por índice de hoja
let repasos = 0;

const ventana = {
    document: {
        getElementById: (id) => (id === 'statusbar_bottom' ? barra : null),
        createElement: (t) => new Elemento(t)
    },
    setInterval: () => 1,
    Asc: {
        editor: {
            asc_getWorksheetsCount: () => HOJAS.length,
            asc_getWorksheetName: (i) => HOJAS[i],
            asc_isProtectedSheet: (i) => { repasos++; return !!protegidas[i]; },
            asc_registerCallback: () => { }
        }
    }
};

global.window = global;
global.console = console;
global.window.MaquitaEditor = { alAparecer: () => { } };
require(B + 'editor-hoja-protegida-candado.js');
const C = window.MaquitaCandadoHoja;

let bien = 0, mal = 0;
const comprueba = (r, q) => { r ? bien++ : mal++; console.log((r ? 'OK  ' : 'MAL ') + q); };
const candadoEn = (i) => !!barra.hijos[i].querySelector('.' + C.MARCA);
console.log();

// ── Sin nada protegido, no hay candados ──────────────────────────────────
C.repasar(ventana);
comprueba(!candadoEn(0) && !candadoEn(1) && !candadoEn(2) && !candadoEn(3),
          'sin hojas protegidas no sale ningún candado');

// ── Se protege «Consolidado», que es la hoja 3 pero la pestaña 2 ─────────
/* Aquí está la gracia: con la hoja «Oculta» de por medio, ir por posición
   habría puesto el candado en la pestaña equivocada. */
protegidas = { 3: true };
C.repasar(ventana);
comprueba(candadoEn(2), 'el candado sale en la pestaña de «Consolidado»');
comprueba(!candadoEn(0) && !candadoEn(1) && !candadoEn(3),
          'y NO en las demás: se empareja por nombre, no por posición');

// ── Repasar dos veces no pone dos candados ───────────────────────────────
C.repasar(ventana);
C.repasar(ventana);
comprueba(barra.hijos[2].querySelectorAll('.' + C.MARCA).length === 1,
          'repasando varias veces sigue habiendo UN candado');

// ── Al desproteger, el candado se va ─────────────────────────────────────
protegidas = {};
C.repasar(ventana);
comprueba(!candadoEn(2), 'al desproteger, el candado se quita');

// ── Varias hojas protegidas a la vez ─────────────────────────────────────
protegidas = { 0: true, 4: true };
C.repasar(ventana);
comprueba(candadoEn(0) && candadoEn(3),
          'con dos hojas protegidas salen los dos candados');
comprueba(!candadoEn(1) && !candadoEn(2), 'y solo esos dos');

// La hoja oculta protegida no rompe nada: no tiene pestaña donde ponerlo.
protegidas = { 1: true };
C.repasar(ventana);
comprueba(!candadoEn(0) && !candadoEn(1) && !candadoEn(2) && !candadoEn(3),
          'una hoja protegida SIN pestaña no pinta un candado en otra');

// ── El nombre se lee sin el candado que le pusimos antes ─────────────────
protegidas = { 0: true };
C.repasar(ventana);
protegidas = { 0: true };
C.repasar(ventana);
comprueba(candadoEn(0)
          && barra.hijos[0].querySelectorAll('.' + C.MARCA).length === 1,
          'el candado de antes no estropea la lectura del nombre');

// ── Si el editor no sabe decirlo, no se inventa ──────────────────────────
const sinSaber = { document: ventana.document, Asc: { editor: {} } };
comprueba(C.hojasProtegidas(sinSaber).length === 0,
          'un editor que no sabe de protección no da falsos candados');
const sinPestanas = {
    document: { getElementById: () => null, createElement: (t) => new Elemento(t) },
    Asc: ventana.Asc
};
comprueba(C.repasar(sinPestanas) === false,
          'sin pestañas, se dice que no se pudo, en vez de fallar en silencio');

// Una hoja que revienta al preguntarle no tumba las demás.
protegidas = { 4: true };
const editorRaro = Object.assign({}, ventana.Asc.editor, {
    asc_isProtectedSheet: (i) => { if (i === 2) throw new Error('esta no contesta'); return !!protegidas[i]; }
});
const conUnaRota = { document: ventana.document, Asc: { editor: editorRaro } };
C.repasar(conUnaRota);
comprueba(candadoEn(3), 'si una hoja no contesta, las demás se marcan igual');

console.log('\n' + bien + ' bien, ' + mal + ' mal\n');
process.exit(mal ? 1 : 0);
