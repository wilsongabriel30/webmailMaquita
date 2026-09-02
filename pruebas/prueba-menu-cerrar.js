/* El menú del clic derecho tiene que DESAPARECER al elegir una de nuestras
   opciones. Se comprueban los tres casos: cuando el editor sabe cerrarlo,
   cuando su camino limpio no hace nada —lo que fallaba—, y cuando el menú
   abierto ni siquiera es el que teníamos agarrado. */

const pasado = { hideAll: 0, hide: 0, eventos: [] };

// ── Un trocito de DOM, como el que monta el editor ───────────────────────
function Elemento(clases, conMenu) {
    this.classList = {
        _c: (clases || '').split(' ').filter(Boolean),
        contains: function (c) { return this._c.indexOf(c) !== -1; },
        remove: function (c) { this._c = this._c.filter(function (x) { return x !== c; }); }
    };
    this._conMenu = conMenu !== false;
}
Elemento.prototype.querySelector = function (sel) {
    return (sel === '.dropdown-menu' && this._conMenu) ? {} : null;
};
Elemento.prototype.abierto = function () { return this.classList.contains('open'); };

function ventanaCon(opciones) {
    const abiertos = opciones.abiertos || [];
    const v = {
        document: {
            querySelectorAll: function (sel) {
                // Como el navegador: «.open» devuelve los que TIENEN la clase
                // ahora mismo, no los que la tenían al empezar.
                if (sel === '.open') {
                    return abiertos.filter(function (e) { return e.abierto(); });
                }
                return [];              // sin iframes dentro
            }
        },
        // El jQuery del editor: aquí solo sirve para anotar los avisos.
        $: function (el) {
            return { trigger: function (evento) { pasado.eventos.push(evento); } };
        }
    };
    if (opciones.conGestor !== false) {
        v.Common = { UI: { Menu: { Manager: { hideAll: function () {
            pasado.hideAll++;
            if (opciones.hideAllCierra) abiertos.forEach(function (e) {
                e.classList.remove('open');
            });
            return !!opciones.hideAllCierra;
        } } } } };
    }
    return v;
}

/** El menú del editor, con su contenedor. */
function menuCon(contenedor, puedeCerrarse) {
    return {
        parentEl: {
            hasClass: function (c) { return contenedor.classList.contains(c); }
        },
        hide: function () {
            pasado.hide++;
            if (puedeCerrarse) contenedor.classList.remove('open');
        }
    };
}

global.window = { document: { querySelectorAll: () => [] } };
global.document = { head: { appendChild() { } } };
global.setTimeout = (fn) => { fn(); return 1; };     // la segunda pasada, ya
global.console = console;

require('/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/editor-menu-cerrar.js');

const C = window.MaquitaMenuCerrar;
const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
console.log('\n[Drive Maquita] cerrar el menu del clic derecho\n');

// ── Caso 1: el editor lo cierra por su camino limpio ─────────────────────
let caja = new Elemento('open');
let v = ventanaCon({ abiertos: [caja], hideAllCierra: true });
let listo = C.cerrar(v, menuCon(caja, true));
bien(listo === true, 'el menu se cierra');
bien(pasado.hideAll === 1, 'primero se intenta el camino limpio del editor');
bien(caja.abierto() === false, 'y deja de estar a la vista');
bien(pasado.eventos.length === 0, 'si ya se cerro solo, no se toca el DOM a mano');

// ── Caso 2: el que fallaba — ni hideAll ni hide hacen nada ───────────────
pasado.hideAll = 0; pasado.hide = 0; pasado.eventos = [];
caja = new Elemento('open');
v = ventanaCon({ abiertos: [caja], hideAllCierra: false });
listo = C.cerrar(v, menuCon(caja, false));
bien(listo === true, 'aun asi el menu se cierra: esto es lo que fallaba');
bien(caja.abierto() === false, 'se le quita por el DOM la clase que lo muestra');
bien(pasado.eventos.join(',') === 'hide.bs.dropdown,hidden.bs.dropdown',
     'y se avisa antes y despues, para que el editor se entere');
bien(pasado.hideAll === 1 && pasado.hide === 1,
     'sin saltarse sus dos caminos: se prueban antes de tocar nada');

// ── Caso 3: el menu abierto NO es el que teniamos agarrado ───────────────
pasado.eventos = [];
const otro = new Elemento('open');                 // otro menu del editor
const elNuestro = new Elemento('');                // el nuestro, ya cerrado
v = ventanaCon({ abiertos: [otro], hideAllCierra: false });
listo = C.cerrar(v, menuCon(elNuestro, false));
bien(otro.abierto() === false,
     'se cierra el que este a la vista, aunque no sea el que teniamos');

// ── Lo que NO se toca ────────────────────────────────────────────────────
const ajeno = new Elemento('open', false);         // un «open» que no es menu
v = ventanaCon({ abiertos: [ajeno], hideAllCierra: false });
C.cerrar(v, menuCon(new Elemento(''), false));
bien(ajeno.abierto() === true,
     'un elemento «open» que no envuelve un menu se deja en paz');

// ── Un editor sin nada de esto no puede romper la opcion ─────────────────
listo = C.cerrar({}, { parentEl: null });
bien(listo === true, 'si no hay menu que cerrar, se da por cerrado y no se rompe');
listo = C.cerrar(ventanaCon({ abiertos: [], conGestor: false }), null);
bien(listo === true, 'ni aunque el editor no tenga gestor de menus');

// ── Saber si esta abierto ────────────────────────────────────────────────
bien(C.abierto(menuCon(new Elemento('open'), true)) === true,
     'se sabe cuando el menu esta a la vista');
bien(C.abierto(null) === false, 'y sin menu, no lo esta');
console.log();
