/* Vista de filtro (núcleo, barra y menú) contra un simulacro del editor 9.4 tal
   como se comporta de verdad (réplica del 04/09/2026):
   - crear y renombrar son ASÍNCRONOS (bloqueo colaborativo);
   - `asc_getActiveNamedSheetView()` SIN el índice de hoja devuelve null siempre
     (por eso la barra del 01/09 nunca salía);
   - las vistas son objetos con asc_getName / asc_getIsActive / asc_setName.
   Se comprueba el ciclo de Google: crear «Filtro temporal 1» → filtrar → guardar
   con nombre → salir (la temporal se borra, la guardada se queda) → volver. */

const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
const espera = (ms) => new Promise((r) => setTimeout(r, ms));

const modelo = [];
let activa = null;
let autoFilter = null;
const eventos = {};
function Vista(nombre) { this.name = nombre; }
Vista.prototype.asc_getName = function () { return this.name; };
Vista.prototype.asc_getIsActive = function () { return activa === this; };
Vista.prototype.asc_setName = function (n) { const t = this; setTimeout(function () { t.name = n; if (eventos.lista) eventos.lista(); }, 10); };
const api = {
    asc_getActiveWorksheetIndex: () => 0,
    asc_getNamedSheetViews: () => modelo.slice(),
    asc_getActiveNamedSheetView: (i) => (i === undefined ? null : (activa ? activa.name : null)),
    asc_setActiveNamedSheetView: (n) => { activa = n === null ? null : (modelo.find((v) => v.name === n) || null); if (eventos.cambio) eventos.cambio(); },
    asc_addNamedSheetView: (dup, setActive) => { setTimeout(function () { const v = new Vista('Vista' + (modelo.length + 1)); modelo.push(v); if (setActive) api.asc_setActiveNamedSheetView(v.name); }, 10); },
    asc_deleteNamedSheetViews: (arr) => { arr.forEach((v) => { const i = modelo.indexOf(v); if (i >= 0) modelo.splice(i, 1); }); if (eventos.lista) eventos.lista(); },
    asc_registerCallback: (ev, fn) => { eventos[ev === 'asc_onChangeActiveNamedSheetView' ? 'cambio' : 'lista'] = fn; },
    asc_addAutoFilter: () => { autoFilter = { Ref: { getName: () => 'A1:C16' } }; },
    wb: { getWorksheet: () => ({ model: { get AutoFilter() { return autoFilter; } } }) }
};
const ventana = { Asc: { editor: api }, setInterval: () => 1, document: { body: {} } };

global.window = global;
const buzon = [];
window.MaquitaDiagnostico = { contar: (m, d) => buzon.push([m, d]) };
const B = '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';
require(B + 'editor-vista-filtro.js');
require(B + 'editor-vista-filtro-barra.js');
require(B + 'editor-vista-filtro-menu.js');
const V = window.MaquitaVistaFiltro, Barra = window.MaquitaVistaFiltroBarra, Menu = window.MaquitaVistaFiltroMenu;
const textos = () => Menu.entradas().map((e) => (e.marca || '') + (e.texto || '--') + (e.apagada ? '!' : ''));

(async function () {
    console.log();
    bien(V.preparar(ventana) === true && eventos.cambio && eventos.lista, 'se prepara con la ventana del editor y se suscribe a sus dos eventos de vistas');
    bien(V.activa() === null && V.vistas().length === 0 && Barra.contenido() === null, 'sin vistas: nada activo y sin barra');
    let t = textos();
    bien(t[0] === '+Crear vista de filtro' && t.indexOf('No hay vistas guardadas!') >= 0 && t[t.length - 1] === '✕Salir de vista!'
         && t.indexOf('Guardar vista con nombre…!') >= 0,
         'el menú de Google: crear, opciones apagadas, «no hay vistas guardadas» y salir apagado: ' + t.join(' | '));

    // Crear: asíncrono, se llama «Filtro temporal 1» y pone filtro en la hoja
    let creada = null;
    V.crear(function (n) { creada = n; });
    await espera(600);
    bien(creada === 'Filtro temporal 1' && V.activa() === 'Filtro temporal 1',
         'crear espera a que el editor active la vista y la llama «Filtro temporal 1» (con el ÍNDICE de hoja al preguntar cuál está activa): ' + V.activa());
    bien(V.esTemporal('Filtro temporal 1') && V.intervalo() === 'A1:C16', 'es temporal y, como no había filtro en la hoja, puso uno: intervalo ' + V.intervalo());
    const c = Barra.contenido();
    bien(c && c.nombre === 'Filtro temporal 1' && c.intervalo === 'A1:C16' && c.temporal === true, 'la barra muestra nombre, intervalo y «Guardar vista»: ' + JSON.stringify(c));
    t = textos();
    bien(t.indexOf('✓Filtro temporal 1') >= 0 && t.indexOf('Guardar vista con nombre…') >= 0 && t[t.length - 1] === '✕Salir de vista',
         'en el menú la activa va con ✓ y guardar/salir se encienden: ' + t.join(' | '));

    // Guardar con nombre: renombra (asíncrono) y deja de ser temporal
    bien(V.guardar('Mis pendientes') === true, 'guardar con nombre acepta');
    await espera(400);
    bien(V.activa() === 'Mis pendientes' && !V.esTemporal('Mis pendientes') && Barra.contenido().temporal === false,
         'la vista pasa a llamarse «Mis pendientes», ya no es temporal y la barra esconde «Guardar vista»');
    bien(textos().indexOf('Guardar vista con nombre…!') >= 0, 'y en el menú «guardar» se apaga');

    // Salir de una guardada: se queda
    bien(V.salir() === true, 'salir acepta');
    await espera(400);
    bien(V.activa() === null && V.vistas().map((x) => x.nombre).join() === 'Mis pendientes' && Barra.contenido() === null,
         'al salir de una guardada, se queda en el archivo y la barra desaparece');

    // Otra temporal y salir: se borra
    V.crear();
    await espera(600);
    bien(V.activa() === 'Filtro temporal 1' && V.vistas().length === 2, 'una temporal nueva vuelve a ser «Filtro temporal 1» (el número libre)');
    V.salir();
    await espera(500);
    bien(V.vistas().map((x) => x.nombre).join() === 'Mis pendientes', 'al salir de una temporal, se borra; la guardada sigue');

    // Volver a la guardada desde el menú
    const entrada = Menu.entradas().find((e) => e.tipo === 'vista' && e.nombre === 'Mis pendientes');
    Menu.ejecutar(entrada);
    await espera(400);
    bien(V.activa() === 'Mis pendientes', 'desde el menú se vuelve a entrar en la guardada');

    // Renombrar y borrar
    V.renombrar('Mis pendientes', 'Pendientes 2026');
    await espera(400);
    bien(V.activa() === 'Pendientes 2026', 'cambiar nombre: ' + V.activa());
    V.borrar('Pendientes 2026');
    await espera(400);
    bien(V.activa() === null && V.vistas().length === 0, 'eliminar la vista activa: sale y desaparece');

    const avisos = buzon.filter((b) => b[0] === 'vista de filtro').map((b) => b[1].accion);
    bien(avisos.indexOf('crear') >= 0 && avisos.indexOf('guardar') >= 0 && avisos.indexOf('salir') >= 0 && avisos.indexOf('borrar') >= 0,
         'cada acción deja rastro en el buzón: ' + avisos.join(', '));
    console.log();
})();
