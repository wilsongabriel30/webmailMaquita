/* Dos cosas que Wilson vio en pantalla el 02/09/2026, y que el archivo confirmó:

   1. «me sale con comillas y no debería».
      En el .xlsx, nuestra lista quedó como  """Opción 1,Opción 2"""  —tres pares—
      mientras que las buenas llevan uno:    "saldo,por ejecutar"
      El editor envuelve la fórmula Y DOBLA las comillas que ya trae, así que
      poniéndolas nosotros salían por triplicado.

   2. «no se queda estático donde yo pongo la lista».
      `asc_setDataValidation` aplica la regla A LO QUE ESTÉ SELECCIONADO. Como no
      seleccionábamos el intervalo escrito, la lista se quedaba donde estuviera
      el cursor.

   Se ejecuta con:  node prueba-lista-comillas-y-sitio.js  */

const B = process.env.MAQ_JS
    || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';

const TIPOS = { List: 'lista', None: 'ninguna', Custom: 'personalizada' };

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
Regla.prototype.asc_setType = function (v) { this.tipo = v; };
Regla.prototype.asc_setOperator = function (v) { this.operador = v; };
Regla.prototype.asc_setValue1 = function (v) { this.valor = v; };
Regla.prototype.asc_setDxf = function (v) { this.formato = v; };
Regla.prototype.asc_setLocation = function (v) { this.donde = v; };
function Formato() { }
Formato.prototype.asc_setFillColor = function (c) { this.relleno = c; };

let guardadaEnLaCelda = null;          // lo que el editor tiene puesto de verdad
let seleccionado = 'Hoja1!B6';         // dónde está el cursor
const idoA = [];                       // los intervalos a los que se ha ido

const ventanaEditor = {
    document: { body: {}, querySelectorAll: () => [] },
    Common: { Utils: { ThemeColor: { getRgbColor: (hex) => ({ hex: hex }) } } },
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
            asc_setWorksheetRange: (r) => { idoA.push(r); seleccionado = r; },
            asc_getActiveRangeStr: () => seleccionado.split('!').pop(),
            asc_getWorksheetName: () => 'Hoja1',
            asc_getActiveWorksheetIndex: () => 0,
            asc_getDataValidationProps: () => new Validacion(),
            asc_setDataValidation: (v) => {
                /* EL EDITOR DE VERDAD: envuelve en comillas y dobla las que ya
                   hubiera. Es lo que se vio en el .xlsx. */
                const dado = String((v.Formula1 && v.Formula1.asc_getValue()) || '');
                guardadaEnLaCelda = '"' + dado.replace(/"/g, '""') + '"';
            },
            asc_setCF: () => { },
            asc_getCellInfo: () => ({
                asc_getSelectionRange: () => seleccionado.split('!').pop(),
                asc_getDataValidation: () => (guardadaEnLaCelda === null ? null : {
                    asc_getType: () => TIPOS.List,
                    asc_getFormula1: () => ({ asc_getValue: () => guardadaEnLaCelda })
                })
            })
        }
    }
};

global.window = global;
global.console = console;
global.document = { body: {}, head: {}, querySelectorAll: () => [],
                    createElement: () => ({ style: {} }), addEventListener() { } };

require(B + 'editor-lista-criterios.js');
require(B + 'editor-lista-aplicar.js');
const L = window.MaquitaListas;

let bien = 0, mal = 0;
const comprueba = (r, q) => { r ? bien++ : mal++; console.log((r ? 'OK  ' : 'MAL ') + q); };
console.log();

// ── 1. Las comillas ──────────────────────────────────────────────────────
let r = L.aplicar(ventanaEditor, [
    { valor: 'Opción 1', color: '#fce8b2' },
    { valor: 'Opción 2', color: '#b7e1cd' }
], { rango: 'Hoja1!A1' });
comprueba(r.ok === true, 'la lista se aplica');
comprueba(guardadaEnLaCelda === '"Opción 1,Opción 2"',
          'y queda con UN par de comillas, como las de Excel: ' + guardadaEnLaCelda);
comprueba(guardadaEnLaCelda.indexOf('"""') === -1,
          'NO quedan las tres comillas que salían antes');

// Y al leerla de vuelta se ven los valores limpios, sin comillas.
const d = L.leerDefinicion(ventanaEditor);
comprueba(d.criterio === 'lista' && d.valores.join(',') === 'Opción 1,Opción 2',
          'al reabrirla salen los valores limpios: ' + d.valores.join(' · '));

// Aplicar diez veces seguidas no acumula comillas: era el fallo de fondo.
for (let i = 0; i < 10; i++) {
    L.aplicar(ventanaEditor, d.valores.map(v => ({ valor: v, color: '' })),
              { rango: 'Hoja1!A1' });
}
comprueba(guardadaEnLaCelda === '"Opción 1,Opción 2"',
          'y aplicándola diez veces sigue igual: ' + guardadaEnLaCelda);

// ── 2. Donde se pide, no donde está el cursor ────────────────────────────
idoA.length = 0;
seleccionado = 'Hoja1!B6';
L.aplicar(ventanaEditor, [{ valor: 'SÍ', color: '' }], { rango: "'Ejec. Tec. 2026'!J2:J40" });
comprueba(idoA.indexOf("'Ejec. Tec. 2026'!J2:J40") !== -1,
          'antes de aplicar se va AL INTERVALO que se pidió');
comprueba(seleccionado === "'Ejec. Tec. 2026'!J2:J40",
          'y la regla se pone ahí, no donde estaba el cursor');

// Sin intervalo escrito, se queda donde esté el cursor (lo de siempre).
idoA.length = 0;
seleccionado = 'Hoja1!B6';
L.aplicar(ventanaEditor, [{ valor: 'SÍ', color: '' }], {});
comprueba(seleccionado === 'Hoja1!B6',
          'sin intervalo escrito, se aplica donde esté el cursor');

// ── 3. Si el editor guardara de otra forma, se DICE ──────────────────────
const comoEstaba = ventanaEditor.Asc.editor.asc_setDataValidation;
ventanaEditor.Asc.editor.asc_setDataValidation = function () {
    guardadaEnLaCelda = '"otra cosa"';        // un editor que hace lo que quiere
};
r = L.aplicar(ventanaEditor, [{ valor: 'ENERO', color: '' }], { rango: 'Hoja1!A1' });
comprueba(r.ok === false && /guardó la lista de otra forma/.test(r.problemas[0]),
          'si queda guardada de otra forma se avisa, en vez de dejarlo pasar');
ventanaEditor.Asc.editor.asc_setDataValidation = comoEstaba;

// ── 4. Un editor sin `asc_setWorksheetRange` no rompe nada ───────────────
const irComoEstaba = ventanaEditor.Asc.editor.asc_setWorksheetRange;
delete ventanaEditor.Asc.editor.asc_setWorksheetRange;
r = L.aplicar(ventanaEditor, [{ valor: 'ENERO', color: '' }], { rango: 'Hoja1!A1' });
comprueba(r.ok === true,
          'un editor que no sepa ir al intervalo aplica igual, donde esté');
ventanaEditor.Asc.editor.asc_setWorksheetRange = irComoEstaba;

console.log('\n' + bien + ' bien, ' + mal + ' mal\n');
process.exit(mal ? 1 : 0);
