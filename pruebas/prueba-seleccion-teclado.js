/* Marcar varios con Mayusculas + flechas.
   El caso que fallaba: marcar con el RATON (el foco se queda fuera de la
   lista) y despues seguir con el teclado. */
const escuchas = [];
const marcados = [];
let filaConFoco = null;              // null = el foco NO esta en la lista

var siguienteTop = 0;
function fila(nombre, seleccionada) {
    var miTop = siguienteTop; siguienteTop += 40;
    return {
        nombre: nombre,
        classList: {
            _s: !!seleccionada,
            contains: function (c) { return c === 'selected' && this._s; },
            add: function () { this._s = true; },
            remove: function () { this._s = false; }
        },
        getBoundingClientRect: function () { return { top: miTop }; },
        closest: function () { return null; },   // vista de lista
        hasAttribute: function () { return true; },
        setAttribute: function () { },
        focus: function () { filaConFoco = this; },
        scrollIntoView: function () { }
    };
}

const filas = [fila('a.txt'), fila('b.txt'), fila('c.txt'), fila('d.txt'), fila('e.txt')];

global.window = global;
global.document = {
    activeElement: { closest: function () { return filaConFoco; } },
    querySelector: function () { return null; },
    querySelectorAll: function (sel) {
        if (sel === '#listView') return [{ querySelectorAll: function () { return filas; } }];
        return [];
    },
    addEventListener: function (s, f) { if (s === 'keydown') escuchas.push(f); }
};
global.console = console;
global.setTimeout = function (f) { f(); };
window.seleccionarItem = function (ev, el) { marcados.push({ el: el.nombre, rango: ev.shiftKey }); };

require('/home/sistemas/Maquita/interfaces/web/estaticos/js/nextcloud/explorador-seleccion-teclado.js');

const teclado = escuchas[0];
const bien = function (r, q) { console.log((r ? 'OK  ' : 'MAL ') + q); };
function pulsar(tecla, opciones) {
    opciones = opciones || {};
    marcados.length = 0;
    let frenada = false;
    teclado({ key: tecla, shiftKey: opciones.shift !== false, ctrlKey: !!opciones.ctrl,
              altKey: !!opciones.alt, metaKey: false,
              preventDefault: function () { frenada = true; } });
    return { marcados: marcados.slice(), frenada: frenada };
}
console.log();

// ── El caso real: se marco «b.txt» con el raton; el foco esta FUERA ──────
filaConFoco = null;
filas[1].classList._s = true;

let r = pulsar('ArrowDown');
bien(r.marcados.length === 1 && r.marcados[0].el === 'c.txt' && r.marcados[0].rango,
     'con el foco fuera, Mayusculas+abajo marca el siguiente');
bien(r.frenada, 'y la pagina no se desplaza');
bien(filaConFoco === filas[2], 'el foco va detras de la seleccion');

filaConFoco = null;
r = pulsar('ArrowUp');
bien(r.marcados.length === 1 && r.marcados[0].el === 'a.txt',
     'Mayusculas+arriba marca el anterior');

filaConFoco = null;
r = pulsar('End');
bien(r.marcados[0].el === 'e.txt', 'Mayusculas+Fin marca hasta el ultimo');

filaConFoco = null;
r = pulsar('Home');
bien(r.marcados[0].el === 'a.txt', 'Mayusculas+Inicio marca hasta el primero');

// ── Con el foco dentro se hace lo MISMO: un solo camino ────────────────
// (antes se delegaba en el otro modulo, y ese reparto hacia que la seleccion
//  dejara de crecer a partir del segundo archivo.)
filas.forEach(function (f) { f.classList._s = false; });
filas[1].classList._s = true;
filaConFoco = filas[1];
r = pulsar('ArrowDown');
bien(r.marcados.length === 1 && r.marcados[0].el === 'c.txt',
     'con el foco dentro se sigue el mismo camino');

// Y la seleccion CRECE pulsacion tras pulsacion, que es lo que fallaba.
filas.forEach(function (f) { f.classList._s = false; });
filas[0].classList._s = true;
filaConFoco = null;
var recorrido = [];
for (var v = 0; v < 3; v++) {
    var paso = pulsar('ArrowDown');
    if (paso.marcados.length) {
        recorrido.push(paso.marcados[0].el);
        // El rango real lo hace seleccionarItem; aqui se simula que crece.
        filas.forEach(function (f, i) { f.classList._s = i <= v + 1; });
    }
}
bien(recorrido.join(',') === 'b.txt,c.txt,d.txt',
     'tres pulsaciones avanzan tres archivos: ' + recorrido.join(','));

// ── Lo que NO debe pasar ────────────────────────────────────────────────
filaConFoco = null;
bien(pulsar('ArrowDown', { shift: false }).marcados.length === 0,
     'la flecha sola no marca');
bien(pulsar('ArrowDown', { ctrl: true }).marcados.length === 0, 'con Ctrl no se toca');
bien(pulsar('a').marcados.length === 0, 'una letra no marca nada');

// Sin nada marcado, se empieza por el principio en vez de no hacer nada:
// si no, con el teclado no habria forma de empezar a marcar.
filas.forEach(function (f) { f.classList._s = false; });
filaConFoco = null;
r = pulsar('ArrowDown');
bien(r.marcados.length === 1 && r.marcados[0].el === 'a.txt',
     'sin nada marcado, se empieza por el primero');
