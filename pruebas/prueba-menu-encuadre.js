/* Menú del clic derecho: que SIEMPRE quede completo dentro de la ventana, también
   cuando crece después de abrirse, y que los submenús no se salgan por ningún lado. */
const fs = require('fs'), path = require('path');
function caja(ancho, alto) {
    return { style: {}, _cls: new Set(), _w: ancho, _h: alto, dataset: {},
        classList: { add(c) { this.o._cls.add(c); }, remove(c) { this.o._cls.delete(c); },
                     contains(c) { return this.o._cls.has(c); } },
        querySelectorAll() { return []; },
        getBoundingClientRect() { const l = parseFloat(this.style.left) || 0, t = parseFloat(this.style.top) || 0;
            return { left: l, top: t, right: l + this._w, bottom: t + this._h, width: this._w, height: this._h }; } };
}
const menu = caja(320, 420); menu.classList.o = menu;
const sub = caja(320, 300); sub.classList.o = sub;
let alCambiar = null;
global.window = global; global.innerWidth = 1366; global.innerHeight = 650;
global.ResizeObserver = function (f) { alCambiar = f; this.observe = function () {}; };
global.document = { getElementById: (id) => id === 'contextMenu' ? menu : null,
    querySelectorAll: (s) => s.indexOf('.show') > 0 ? (sub._cls.has('show') ? [sub] : []) : [] };
global.itemSeleccionado = null; global.seleccionarItem = function () {}; global.actualizarEstadoFavorito = function () {};
const ruta = process.argv[2] || '/home/sistemas/Maquita/interfaces/web/estaticos/js/nextcloud/explorador-menu-contextual.js';
(0, eval)(fs.readFileSync(ruta, 'utf8').replace(/^const MARGEN/m, 'var MARGEN').replace(/^let _vig/m, 'var _vig'));

let fallos = 0;
function dentro(c, que) {
    const r = c.getBoundingClientRect();
    const ok = r.left >= 8 && r.top >= 8 && r.right <= innerWidth - 8 && r.bottom <= innerHeight - 8;
    console.log((ok ? 'BIEN ' : 'MAL  ') + que + ' -> ' + r.left + ',' + r.top); if (!ok) fallos++;
}
const ev = (x, y) => ({ clientX: x, clientY: y, preventDefault() {}, stopPropagation() {} });
mostrarContextMenu(ev(1300, 600), { dataset: {} }); dentro(menu, 'clic en la esquina inferior derecha');
mostrarContextMenu(ev(100, 100), { dataset: {} });
if (menu.style.left !== '100px' || menu.style.top !== '100px') { console.log('MAL  con sitio de sobra debe abrir en el clic'); fallos++; }
else console.log('BIEN con sitio de sobra abre en el punto del clic');
mostrarContextMenu(ev(500, 300), { dataset: {} }); menu._h = 560; alCambiar(); dentro(menu, 'crece después de abrir (opciones tardías)');
sub._item = { getBoundingClientRect: () => ({ left: 1030, right: 1350, top: 600, bottom: 632 }) };
sub._cls.add('show'); encuadrarSubmenuContextual(sub); dentro(sub, 'submenú sin sitio a la derecha ni abajo');
global.innerWidth = 400; encuadrarSubmenuContextual(sub); dentro(sub, 'submenú en pantalla angosta');
console.log(fallos ? 'FALLOS: ' + fallos : 'TODO BIEN'); process.exit(fallos ? 1 : 0);
