/* El editor construye su menú del clic derecho cuando termina de abrir el
   documento. Aquí se comprueba que el arreglo ESPERA a que exista, en vez de
   rendirse en el primer intento. */

let repasar = null;                     // el repaso de cada segundo
const puestos = [];                     // lo que se añade al menú

// El menú aparece TARDE, como en el editor de verdad.
let menu = null;
const opciones = [];                    // las opciones añadidas, para leerles el texto
const alAbrirse = {};                   // lo que el menu avisa al abrirse

function MenuItem(opciones) { this.caption = opciones.caption; }
MenuItem.prototype.on = function () { };
MenuItem.prototype.setCaption = function (t) { this.caption = t; };

const ventanaEditor = {
    document: { body: {}, querySelectorAll: () => [] },
    Common: { UI: { MenuItem: MenuItem } },
    Asc: { editor: {} },
    SSE: {
        getController: () => ({
            permissions: { isEdit: true },
            documentHolder: { get ssMenu() { return menu; } }
        })
    }
};

global.window = global;
global.document = {
    body: { appendChild() { }, removeChild() { } },
    head: { appendChild() { } },
    createElement: () => ({ style: {}, setAttribute() { }, appendChild() { },
                            querySelector: () => null, querySelectorAll: () => [],
                            dataset: {}, textContent: '' }),
    querySelectorAll: (s) => (s === 'iframe' ? [{ contentWindow: ventanaEditor }] : []),
    addEventListener() { }
};
global.setInterval = (fn) => { repasar = fn; return 1; };
global.console = console;

const B = process.env.MAQ_JS
    || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';
require(B + 'editor-ventanas.js');
require(B + 'editor-lista-aplicar.js');
require(B + 'editor-lista-panel.js');
require(B + 'editor-proteger-aplicar.js');
require(B + 'editor-proteger-personas.js');
require(B + 'editor-proteger-permisos.js');
require(B + 'editor-proteger-panel.js');
require(B + 'editor-listas-desplegables.js');

const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
console.log();

// ── El editor todavía no tiene menú ──────────────────────────────────────
bien(puestos.length === 0, 'sin menu todavia, no se añade nada');
repasar();
bien(puestos.length === 0, 'y al segundo repaso tampoco: sigue sin menu');

// ── El editor termina de abrir y crea su menú ────────────────────────────
menu = { addItem: (item) => { puestos.push(item.caption); opciones.push(item); },
         on: (evento, fn) => { alAbrirse[evento] = fn; } };
repasar();
bien(puestos.indexOf('Crear lista desplegable') !== -1,
     'en cuanto aparece el menu, se añade la opcion');
bien(puestos.indexOf('Proteger hojas e intervalos') !== -1,
     'y tambien la de proteger hojas e intervalos');
const cuantos = puestos.length;

// ── Y no se repite ───────────────────────────────────────────────────────
repasar();
repasar();
bien(puestos.length === cuantos, 'no se añade dos veces');

// ── Si el editor rehace su ventana, se vuelve a poner ────────────────────
delete ventanaEditor.__maquita_listas;
Object.keys(ventanaEditor).filter(k => k.indexOf('__maquita_') === 0)
      .forEach(k => { delete ventanaEditor[k]; });
menu = { addItem: (item) => { puestos.push(item.caption); opciones.push(item); },
         on: (evento, fn) => { alAbrirse[evento] = fn; } };   // menu nuevo
repasar();
bien(puestos.length > cuantos, 'si el editor se renueva, la opcion vuelve');

// ── «Crear» o «Editar», según lo que tenga la celda ──────────────────────
/* Se mira CADA VEZ que se abre el menu, no una sola vez al engancharlo: la
   celda sobre la que se pulsa cambia a cada clic. */
const laOpcion = opciones.filter(o => /lista desplegable/.test(o.caption)).pop();
bien(!!laOpcion, 'la opcion de la lista esta puesta');
bien(typeof alAbrirse['show:before'] === 'function',
     'el menu avisa antes de abrirse, y ahi se decide el texto');

// La celda no tiene lista todavia.
window.MaquitaListas.leerDefinicion = () => ({ criterio: '', valores: [], origen: '' });
window.MaquitaListaMemoria = { hayLista: () => false };
alAbrirse['show:before']();
bien(laOpcion.caption === 'Crear lista desplegable',
     'sin lista en la celda, dice «Crear lista desplegable»');

// La celda YA tiene una lista puesta.
window.MaquitaListas.leerDefinicion = () => ({ criterio: 'lista',
    valores: ['ENERO', 'FEBRERO'], origen: '' });
alAbrirse['show:before']();
bien(laOpcion.caption === 'Editar lista desplegable',
     'con lista en la celda, dice «Editar lista desplegable»');

// Una lista sacada de un INTERVALO tambien es una lista: es el caso normal.
window.MaquitaListas.leerDefinicion = () => ({ criterio: 'lista-rango',
    valores: [], origen: 'Consolidado!$I:$I' });
alAbrirse['show:before']();
bien(laOpcion.caption === 'Editar lista desplegable',
     'una lista sacada de una columna tambien es «Editar»');

// Solo con la definicion guardada (la validacion aun no la ve) tambien cuenta.
window.MaquitaListas.leerDefinicion = () => ({ criterio: '', valores: [], origen: '' });
window.MaquitaListaMemoria = { hayLista: () => true };
alAbrirse['show:before']();
bien(laOpcion.caption === 'Editar lista desplegable',
     'con la definicion guardada en el documento, tambien es «Editar»');

// Si preguntar falla, NO se promete lo que no se sabe.
window.MaquitaListas.leerDefinicion = () => { throw new Error('el editor no responde'); };
window.MaquitaListaMemoria = { hayLista: () => { throw new Error('tampoco'); } };
alAbrirse['show:before']();
bien(laOpcion.caption === 'Crear lista desplegable',
     'si no se puede saber, dice «Crear»: no promete editar lo que no ha visto');
