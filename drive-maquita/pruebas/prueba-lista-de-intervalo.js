/* En los archivos de verdad la lista casi nunca está escrita: apunta a una
   COLUMNA de otra hoja —«Consolidado!$I:$I»—. Eso se descartaba como «no hay
   lista», así que el menú decía «Crear» y el panel salía en blanco ENCIMA de
   una lista que sí existía (visto en BIBLIOTECA PROCESOS FORMATIVOS, la celda
   K5 de la captura de Wilson, 02/09/2026).

   Aquí se comprueba que una lista de intervalo se reconoce, se abre por donde
   estaba, y que la lista desplegable solo pinta de color LO QUE TIENE color.

   Se ejecuta con:  node prueba-lista-de-intervalo.js  */

const B = process.env.MAQ_JS
    || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';

const TIPOS = { List: 'lista', None: 'ninguna', Custom: 'personalizada' };
let formulaDeLaCelda = null;            // lo que devuelve la validación de la celda

const ventanaEditor = {
    document: { body: {}, querySelectorAll: () => [] },
    Asc: {
        c_oAscEDataValidationType: TIPOS,
        editor: {
            asc_getActiveRangeStr: () => 'K5',
            asc_getWorksheetName: () => 'Buscador',
            asc_getActiveWorksheetIndex: () => 0,
            asc_getCellInfo: () => ({
                asc_getSelectionRange: () => 'K5',
                asc_getDataValidation: () => (formulaDeLaCelda === null ? null : {
                    asc_getType: () => TIPOS.List,
                    asc_getFormula1: () => ({ asc_getValue: () => formulaDeLaCelda })
                })
            })
        },
        referenceType: { A: 0 }
    }
};

global.window = global;
global.console = console;
global.document = { body: {}, head: {}, querySelectorAll: () => [],
                    createElement: () => ({ style: {} }), addEventListener() { } };

require(B + 'editor-lista-aplicar.js');
const L = window.MaquitaListas;

let bien = 0, mal = 0;
const comprueba = (r, q) => { r ? bien++ : mal++; console.log((r ? 'OK  ' : 'MAL ') + q); };
console.log();

// ── Una lista que apunta a una columna de otra hoja ──────────────────────
formulaDeLaCelda = 'Consolidado!$I:$I';
let d = L.leerDefinicion(ventanaEditor);
comprueba(d.criterio === 'lista-rango',
          'una lista sacada de un intervalo SE RECONOCE como lista');
comprueba(d.origen === 'Consolidado!$I:$I',
          'y se sabe de dónde saca los valores: ' + d.origen);
comprueba(d.valores.length === 0,
          'no se inventan valores: los pone la columna, no nosotros');

// ── Una lista escrita a mano ─────────────────────────────────────────────
formulaDeLaCelda = '"ENERO,FEBRERO,MARZO"';
d = L.leerDefinicion(ventanaEditor);
comprueba(d.criterio === 'lista', 'una lista escrita también se reconoce');
comprueba(d.valores.join(',') === 'ENERO,FEBRERO,MARZO', 'con sus tres valores');
comprueba(d.origen === '', 'y sin intervalo de origen, porque no lo tiene');

// ── Una celda sin lista ──────────────────────────────────────────────────
formulaDeLaCelda = null;
d = L.leerDefinicion(ventanaEditor);
comprueba(d.criterio === '' && d.valores.length === 0,
          'una celda sin lista se dice que no la tiene');

// Una fórmula vacía tampoco es una lista.
formulaDeLaCelda = '';
comprueba(L.leerDefinicion(ventanaEditor).criterio === '',
          'una regla de lista sin fórmula tampoco cuenta');

// Un intervalo escrito a secas, sin hoja delante.
formulaDeLaCelda = '$A$2:$A$40';
comprueba(L.leerDefinicion(ventanaEditor).criterio === 'lista-rango',
          'un intervalo de la misma hoja también vale');

// ── Y lo de siempre sigue igual ──────────────────────────────────────────
formulaDeLaCelda = 'Consolidado!$I:$I';
comprueba(L.leerActual(ventanaEditor).length === 0,
          'leerActual sigue devolviendo solo los valores ESCRITOS');

// ── El color en la lista desplegable ─────────────────────────────────────
/* Google pinta la pastilla SOLO en los valores que tienen color. En una lista
   sacada de una columna no hay colores: va en texto plano. */
function Enlace(texto) {
    this.textContent = texto;
    this.style = {};
    this.clases = [];
    this.classList = {
        add: (c) => { if (this.clases.indexOf(c) === -1) this.clases.push(c); },
        remove: (c) => { const i = this.clases.indexOf(c); if (i !== -1) this.clases.splice(i, 1); },
        contains: (c) => this.clases.indexOf(c) !== -1
    };
}
const enlaces = [new Enlace('ENERO'), new Enlace('FEBRERO'), new Enlace('Ambiente')];
const menu = { cmpEl: [{ querySelectorAll: () => enlaces }] };

global.window.MaquitaEditor = { alAparecer: () => { } };
require(B + 'editor-desplegable-aspecto.js');
const A = window.MaquitaDesplegableAspecto;

window.MaquitaListaMemoria = {
    leer: () => [{ valor: 'ENERO', color: '#fce8b2' },
                 { valor: 'FEBRERO', color: '' }]
};
const pintadas = A.pintarValores(ventanaEditor, menu);
comprueba(pintadas === 1, 'solo se pinta el valor que TIENE color');
comprueba(enlaces[0].style.background === '#fce8b2'
          && enlaces[0].classList.contains('maq-con-color'),
          'ENERO sale con su pastilla amarilla');
comprueba(!enlaces[1].style.background && !enlaces[1].classList.contains('maq-con-color'),
          'FEBRERO, sin color guardado, sale en TEXTO PLANO');
comprueba(!enlaces[2].style.background,
          'y un valor que ni siquiera es de nuestra lista, tampoco se pinta');

// Sin colores guardados —lista sacada de una columna— no se pinta ninguno.
window.MaquitaListaMemoria = { leer: () => [] };
comprueba(A.pintarValores(ventanaEditor, menu) === 0,
          'una lista sacada de una columna va entera en texto plano');
comprueba(!enlaces[0].style.background,
          'y se limpia lo pintado antes: el menú se reutiliza para otras celdas');

// Sin memoria cargada no revienta.
delete window.MaquitaListaMemoria;
comprueba(A.pintarValores(ventanaEditor, menu) === 0,
          'sin el módulo de memoria, la lista se abre igual (sin colores)');
comprueba(A.pintarValores(ventanaEditor, null) === 0,
          'y sin menú, tampoco se rompe');

console.log('\n' + bien + ' bien, ' + mal + ' mal\n');
process.exit(mal ? 1 : 0);
