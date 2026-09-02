/* Seleccionar arrastrando un recuadro: que marque lo que toca, que no arranque
   con un clic normal y que no se meta donde no debe. */
const escuchas = {};
let reconstruido = 0;

function fila(nombre, arriba) {
    return {
        nombre: nombre,
        classList: {
            _s: false,
            contains: function (c) { return c === 'selected' && this._s; },
            toggle: function (c, v) { this._s = !!v; },
            add: function () { this._s = true; },
            remove: function () { this._s = false; }
        },
        getBoundingClientRect: function () {
            return { left: 10, right: 200, top: arriba, bottom: arriba + 30 };
        },
        closest: function () { return null; }
    };
}
const filas = [fila('a.txt', 0), fila('b.txt', 40), fila('c.txt', 80), fila('d.txt', 300)];

const estilos = [];
global.window = global;
global.document = {
    body: { appendChild: function () {}, removeChild: function () {} },
    head: { appendChild: function (n) { estilos.push(n); } },
    createElement: function () { return { style: {}, className: '', parentNode: null,
                                          textContent: '' }; },
    querySelectorAll: function (sel) {
        if (sel === '#listView') return [{ querySelectorAll: function () { return filas; } }];
        return [];
    },
    addEventListener: function (s, f, captura) {
        if (captura) { (escuchas['cap_' + s] = escuchas['cap_' + s] || []).push(f); }
        else { escuchas[s] = f; }
    },
    removeEventListener: function (s, f, captura) {
        var lista = escuchas['cap_' + s] || [];
        var i = lista.indexOf(f); if (i !== -1) lista.splice(i, 1);
    }
};
global.console = console;
window.reconstruirSeleccion = function () { reconstruido++; };

require('/home/sistemas/Maquita/interfaces/web/estaticos/js/nextcloud/explorador-seleccion-area.js');

const bien = function (r, q) { console.log((r ? 'OK  ' : 'MAL ') + q); };
function hueco() { return { closest: function (sel) { return sel === '#listView' ? {} : null; } }; }
function sobreArchivo() {
    return { closest: function (sel) {
        return sel.indexOf('gd-card') !== -1 ? {} : (sel === '#listView' ? {} : null); } };
}
function marcadas() { return filas.filter(function (f) { return f.classList._s; })
                                  .map(function (f) { return f.nombre; }); }
console.log();

// ── Arrastrar por encima de las tres primeras ───────────────────────────
escuchas.mousedown({ button: 0, target: hueco(), clientX: 5, clientY: 0 });
escuchas.mousemove({ clientX: 250, clientY: 100, preventDefault: function () {} });
bien(marcadas().join(',') === 'a.txt,b.txt,c.txt',
     'el recuadro marca lo que toca: ' + marcadas().join(','));
bien(!marcadas().includes('d.txt'), 'y no lo que queda fuera');
escuchas.mouseup({});
bien(reconstruido === 1, 'al soltar se avisa una vez, para la barra y «Mover»');

// ── Un clic normal NO es un arrastre ────────────────────────────────────
filas.forEach(function (f) { f.classList._s = false; });
reconstruido = 0;
escuchas.mousedown({ button: 0, target: hueco(), clientX: 5, clientY: 0 });
escuchas.mousemove({ clientX: 7, clientY: 2, preventDefault: function () {} });
escuchas.mouseup({});
bien(marcadas().length === 0 && reconstruido === 0,
     'moverse 2 pixeles sigue siendo un clic, no marca nada');

// ── Sobre un archivo manda el arrastre de siempre ───────────────────────
escuchas.mousedown({ button: 0, target: sobreArchivo(), clientX: 5, clientY: 0 });
escuchas.mousemove({ clientX: 250, clientY: 100, preventDefault: function () {} });
bien(marcadas().length === 0, 'empezando sobre un archivo no se dibuja recuadro');
escuchas.mouseup({});

// ── Con el boton derecho tampoco ────────────────────────────────────────
escuchas.mousedown({ button: 2, target: hueco(), clientX: 5, clientY: 0 });
escuchas.mousemove({ clientX: 250, clientY: 100, preventDefault: function () {} });
bien(marcadas().length === 0, 'el boton derecho no dibuja recuadro');
escuchas.mouseup({});


// ── Lo que fallaba: al soltar, el clic en el hueco borraba la seleccion ──
filas.forEach(function (f) { f.classList._s = false; });
reconstruido = 0;
escuchas['cap_click'] = [];      // se parte de limpio: antes hubo otros arrastres
escuchas.mousedown({ button: 0, target: hueco(), clientX: 5, clientY: 0 });
escuchas.mousemove({ clientX: 250, clientY: 100, preventDefault: function () {} });
escuchas.mouseup({});

var tragadores = escuchas['cap_click'] || [];
bien(tragadores.length === 1, 'tras arrastrar se prepara para anular ESE clic');

var frenado = false;
tragadores[0]({ stopPropagation: function () { frenado = true; },
                preventDefault: function () {} });
bien(frenado, 'el clic de despues del arrastre se anula: la seleccion se queda');
bien((escuchas['cap_click'] || []).length === 0,
     'y solo ese: el siguiente clic vuelve a funcionar normal');
bien(marcadas().length === 3, 'lo marcado sigue marcado, listo para mover o copiar');

// ── El clic derecho sobre lo marcado no deshace la seleccion ────────────
var menu = (escuchas['cap_contextmenu'] || [])[0];
var paro = false;
var sobreMarcado = filas[0];
sobreMarcado.closest = function () { return sobreMarcado; };
menu({ target: sobreMarcado, stopPropagation: function () { paro = true; } });
bien(paro, 'clic derecho sobre lo marcado: se abre el menu para TODO lo marcado');
