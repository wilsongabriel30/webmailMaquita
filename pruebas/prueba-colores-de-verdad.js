/* POR QUÉ LOS COLORES NO SALÍAN, y por qué ahora se respetan.

   1. `asc_setCF(reglas, borradas, una)` NO recibe una lista de reglas: recibe un
      array INDEXADO POR HOJA. Por dentro hace `reglas[indiceDeLaHoja]`. Al
      pasarle la lista pelada miraba una posición vacía y no aplicaba ninguna:
      por eso el .xlsx de Wilson no tenía ni una regla de color (02/09/2026).

   2. Para RESPETAR los colores al reeditar, se leen del propio archivo —de las
      reglas puestas—, y no de un metadato que el editor no llega a guardar.

   Se ejecuta con:  node prueba-colores-de-verdad.js  */

const B = process.env.MAQ_JS
    || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';

const TIPOS = { List: 'lista', None: 'ninguna' };
const HOJA = 5;                        // el libro está abierto en la hoja 5

// ── El editor, imitando lo que hace de verdad con las reglas ─────────────
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
Regla.prototype.asc_getValue1 = function () { return this.valor; };
Regla.prototype.asc_setDxf = function (v) { this.formato = v; };
Regla.prototype.asc_getDxf = function () { return this.formato; };
Regla.prototype.asc_setLocation = function (v) { this.donde = v; };
function Formato() { }
Formato.prototype.asc_setFillColor = function (c) { this.relleno = c; };
Formato.prototype.asc_getFillColor = function () { return this.relleno; };

let puestasEnLaHoja = [];              // lo que el editor acaba guardando
let guardada = null;
let soloLectura = false;

const editor = {
    asc_getActiveWorksheetIndex: () => HOJA,
    asc_getWorksheetName: () => 'Hoja1',
    asc_getActiveRangeStr: () => 'B2',
    asc_getDataValidationProps: () => new Validacion(),
    asc_setDataValidation: (v) => {
        const dado = String((v.Formula1 && v.Formula1.asc_getValue()) || '');
        guardada = '"' + dado.replace(/"/g, '""') + '"';
    },
    asc_getCellInfo: () => ({
        asc_getSelectionRange: () => 'B2',
        asc_getDataValidation: () => (guardada === null ? null : {
            asc_getType: () => TIPOS.List,
            asc_getFormula1: () => ({ asc_getValue: () => guardada })
        })
    }),
    /* Como el editor DE VERDAD: las reglas se buscan en la posición de la hoja.
       Si llegan en una lista pelada, no encuentra nada y no guarda ninguna. */
    asc_setCF: function (reglas, borradas, una) {
        if (soloLectura) return false;
        if (reglas && reglas[HOJA] && reglas[HOJA].length) {
            puestasEnLaHoja = puestasEnLaHoja.concat(reglas[HOJA]);
        }
        return undefined;
    },
    asc_getCF: function () { return [puestasEnLaHoja]; },
    asc_getWorksheetsCount: () => 8
};

const ventana = {
    document: { body: {}, querySelectorAll: () => [] },
    Common: { Utils: { ThemeColor: { getRgbColor: function (hex) {
        return { get_r: () => parseInt(hex.substr(0, 2), 16),
                 get_g: () => parseInt(hex.substr(2, 2), 16),
                 get_b: () => parseInt(hex.substr(4, 2), 16) };
    } } } },
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
        editor: editor
    }
};

global.window = global;
global.console = console;
global.document = { body: {}, head: {}, querySelectorAll: () => [],
                    createElement: () => ({ style: {} }), addEventListener() { } };
const avisos = [];
global.window.MaquitaDiagnostico = { contar: (q, d) => avisos.push({ q: q, d: d }) };

require(B + 'editor-lista-criterios.js');
require(B + 'editor-lista-colores-cf.js');
require(B + 'editor-lista-aplicar.js');
const L = window.MaquitaListas;
const CF = window.MaquitaColoresCF;

let bien = 0, mal = 0;
const comprueba = (r, q) => { r ? bien++ : mal++; console.log((r ? 'OK  ' : 'MAL ') + q); };
console.log();

// ── 1. Las reglas llegan DONDE EL EDITOR LAS BUSCA ──────────────────────
const ELEMENTOS = [
    { valor: 'ENERO', color: '#fce8b2' },
    { valor: 'FEBRERO', color: '#b7e1cd' }
];
const r = L.aplicar(ventana, ELEMENTOS, { rango: 'Hoja1!B2:B20' });
comprueba(r.ok === true, 'la lista se aplica');
comprueba(puestasEnLaHoja.length === 2,
          'y las DOS reglas de color llegan a la hoja: ' + puestasEnLaHoja.length);
comprueba(puestasEnLaHoja[0].valor === '"ENERO"',
          'la primera regla compara con ENERO');
comprueba(!!puestasEnLaHoja[0].formato.relleno,
          'y lleva su color de fondo');
comprueba(avisos.some(a => a.q === 'colores de la lista'
                        && a.d['reglas puestas'] === '2'),
          'el diagnóstico deja escrito cuántas reglas se pusieron');

// ── 2. Si el editor NO las admite, se dice ──────────────────────────────
soloLectura = true;
avisos.length = 0;
puestasEnLaHoja = [];
const r2 = L.aplicar(ventana, ELEMENTOS, { rango: 'Hoja1!B2:B20' });
comprueba(r2.ok === true, 'la lista se pone igual: los colores son un extra');
comprueba(avisos.some(a => a.d && /no admitió las reglas/.test(a.d.problema || '')),
          'pero se AVISA de que los colores no se aplicaron');
soloLectura = false;

// ── 3. Los colores se leen del propio archivo ───────────────────────────
puestasEnLaHoja = [];
L.aplicar(ventana, ELEMENTOS, { rango: 'Hoja1!B2:B20' });
const mapa = CF.coloresPorValor(ventana);
comprueba(mapa.ENERO === '#fce8b2' && mapa.FEBRERO === '#b7e1cd',
          'se lee de las reglas qué color tiene cada valor: '
          + JSON.stringify(mapa));

// ── 4. Y al reeditar, SE RESPETAN ───────────────────────────────────────
const paraEditar = L.leerElementos(ventana);
comprueba(paraEditar.length === 2, 'al reabrir salen los dos valores');
comprueba(paraEditar[0].valor === 'ENERO' && paraEditar[0].color === '#fce8b2',
          'ENERO vuelve con SU amarillo: ' + paraEditar[0].color);
comprueba(paraEditar[1].color === '#b7e1cd',
          'y FEBRERO con SU verde: ' + paraEditar[1].color);

// Aplicando otra vez lo que salió, los colores no cambian.
puestasEnLaHoja = [];
L.aplicar(ventana, paraEditar, { rango: 'Hoja1!B2:B20' });
const otraVez = CF.coloresPorValor(ventana);
comprueba(otraVez.ENERO === '#fce8b2' && otraVez.FEBRERO === '#b7e1cd',
          'y reeditando diez veces siguen siendo los mismos');

// ── 5. Lo que NO se sabe, no se inventa ─────────────────────────────────
puestasEnLaHoja = [{
    asc_getValue1: () => '"SIN COLOR"',
    asc_getDxf: () => ({ asc_getFillColor: () => null })
}];
comprueba(Object.keys(CF.coloresPorValor(ventana)).length === 0,
          'una regla sin color no apunta ningún color');

puestasEnLaHoja = [];
comprueba(Object.keys(CF.coloresPorValor(ventana)).length === 0,
          'sin reglas, no hay colores que respetar');

const sinNada = { Asc: { editor: {} } };
comprueba(CF.reglasPuestas(sinNada).length === 0,
          'un editor que no sabe de reglas no da falsos colores');

console.log('\n' + bien + ' bien, ' + mal + ' mal\n');
process.exit(mal ? 1 : 0);
