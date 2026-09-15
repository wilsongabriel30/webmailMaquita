/* POR QUÉ LOS COLORES NO SALÍAN, y por qué ahora se respetan.

   Esto se ha equivocado DOS veces, y las dos por suponer cómo se llamaba a
   `asc_setCF` en vez de leer lo que hace. Queda escrito para no repetirlo:

   1. Primero se le pasaba la lista pelada de reglas. Mal.

   2. Después, un array indexado por hoja. También mal, y más traicionero:
      NO daba error —el diagnóstico cantaba «reglas puestas: 2»— pero el .xlsx
      salía con CERO reglas de color (comprobado en el archivo de Wilson del
      03/09/2026, guardado a las 08:23).

      La razón está en la propia función del editor: quien REMATA cada regla
      —le pone la `priority`, que nace en `null`— es una función interna que
      solo corre si se le pasa UNA regla, o un preajuste. Con el array por hoja
      no corre nunca, y una regla sin prioridad no se pinta ni se guarda.

   3. Lo que sí funciona, porque es lo que hace la propia interfaz del editor
      al crear una regla: `asc_setCF([unaRegla], [])`, UNA POR LLAMADA. Y además
      se le pone la prioridad y las celdas a mano, para no depender de esa
      función interna ni de lo que esté seleccionado.

   Y para RESPETAR los colores al reeditar, se leen del propio archivo —de las
   reglas puestas—, no de un metadato que el editor no llega a guardar.

   El simulacro de aquí abajo imita al editor DE VERDAD, incluido lo que más
   importa: que una regla sin prioridad NO llega al documento.

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

/* Como en el SDK: la regla NACE con la prioridad sin poner. Es el detalle del
   que dependía todo, así que el simulacro lo copia igual. */
function Regla() { this.prioridad = null; }
Regla.prototype.asc_setPriority = function (v) { this.prioridad = v; };
Regla.prototype.asc_setType = function (v) { this.tipo = v; };
Regla.prototype.asc_setOperator = function (v) { this.operador = v; };
/* Como el editor DE VERDAD (03/09/2026): envuelve el texto en comillas y,
   si ya las traía, las dobla y lo vuelve a envolver. Por eso hay que dárselo
   SIN comillas. */
Regla.prototype.asc_setValue1 = function (v) {
    v = String(v);
    this.valor = v.charAt(0) === '"' ? '"' + v.replace(/"/g, '""') + '"' : '"' + v + '"';
};
// Como el editor de verdad (03/09/2026): lo devuelve con «=» delante.
Regla.prototype.asc_getValue1 = function () { return '=' + this.valor; };
Regla.prototype.asc_setDxf = function (v) { this.formato = v; };
Regla.prototype.asc_getDxf = function () { return this.formato; };
Regla.prototype.asc_setLocation = function (v) { this.donde = v; };
function Formato() { }
Formato.prototype.asc_setFillColor = function (c) { this.relleno = c; };
Formato.prototype.asc_getFillColor = function () { return this.relleno; };

let puestasEnLaHoja = [];              // lo que el editor acaba guardando
let guardada = null;
let soloLectura = false;
let llamadas = [];                     // cuántas reglas llevó cada llamada
let descartadas = 0;                   // las que se cayeron sin prioridad

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
    /* Como el editor DE VERDAD (función `GSj` del SDK 9.2.1):

       — con UNA regla suelta, la remata: si viene sin prioridad, se la pone;
       — con dos o más, las busca en la posición de la hoja y NO las remata;
       — y una regla que se quede sin prioridad no llega al documento.

       Ojo: NO devuelve nada. Por eso mirar lo que devuelve no sirve para saber
       si funcionó, y hay que volver a leer las reglas. */
    asc_setCF: function (reglas, borradas, preajuste) {
        if (soloLectura) return false;
        llamadas.push((reglas || []).length);

        let entran = null;
        if (reglas && reglas.length === 1 && !Array.isArray(reglas[0])) {
            const sola = reglas[0];
            if (sola.prioridad === null) sola.prioridad = 1;   // el remate
            entran = [sola];
        } else if (reglas && reglas[HOJA]) {
            entran = reglas[HOJA];                             // sin rematar
        }

        (entran || []).forEach(function (regla) {
            if (regla.prioridad === null || regla.prioridad === undefined) {
                descartadas++;         // el editor no la pinta ni la guarda
                return;
            }
            puestasEnLaHoja.push(regla);
        });
        return undefined;
    },
    /* Como el de verdad: hay que decir el ÁMBITO (hoja entera, selección…).
       Sin él devuelve null —y así salía siempre «reglas leídas: 0»—. Y lo que
       devuelve es [reglas, "=celdas seleccionadas"], no las reglas a secas. */
    asc_getCF: function (tipo) {
        if (tipo === undefined || tipo === null) return null;
        return [puestasEnLaHoja, '=B2:B20'];
    },
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
        c_oAscSelectionForCFType: { selection: 0, worksheet: 1, table: 2, pivot: 3 },
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
          'la primera regla compara con ENERO, con UN par de comillas (las pone el editor): '
          + puestasEnLaHoja[0].valor);
comprueba(!!puestasEnLaHoja[0].formato.relleno,
          'y lleva su color de fondo');

// ── LO QUE FALLABA: el remate de cada regla ─────────────────────────────
comprueba(descartadas === 0,
          'NINGUNA regla se cae por venir sin prioridad: se descartaron '
          + descartadas);
comprueba(puestasEnLaHoja.every(r => r.prioridad > 0),
          'todas llegan con su prioridad puesta: '
          + puestasEnLaHoja.map(r => r.prioridad).join(','));
comprueba(llamadas.length === 2 && llamadas.every(n => n === 1),
          'se llama al editor UNA VEZ POR REGLA, que es la forma que funciona: '
          + JSON.stringify(llamadas));

// Las celdas van SIN el nombre de la hoja: con él, el editor puede quedarse
// sin celdas, y una regla sin celdas no pinta nada.
comprueba(puestasEnLaHoja[0].donde === 'B2:B20',
          'y las celdas van sin el nombre de la hoja delante: '
          + puestasEnLaHoja[0].donde);

comprueba(avisos.some(a => a.q === 'colores de la lista'
                        && a.d['aceptadas'] === '2'),
          'el diagnóstico deja escrito cuántas reglas se pusieron');
comprueba(avisos.some(a => a.q === 'colores de la lista'
                        && a.d['confirmadas en el documento'] === '2'),
          'y CONFIRMA leyéndolas del documento, en vez de dar por bueno el envío');

// ── 2. Si el editor NO las admite, se dice ──────────────────────────────
soloLectura = true;
avisos.length = 0;
puestasEnLaHoja = [];
const r2 = L.aplicar(ventana, ELEMENTOS, { rango: 'Hoja1!B2:B20' });
comprueba(r2.ok === true, 'la lista se pone igual: los colores son un extra');
comprueba(avisos.some(a => a.d && /no admitió las reglas/.test(a.d.problema || '')),
          'pero se AVISA de que los colores no se aplicaron');
soloLectura = false;

// ── 2b. El valor de la regla viene con «=» delante y entre comillas ──────
comprueba(CF._valorDe({ asc_getValue1: () => '="Hola"' }) === 'Hola',
          'de ="Hola" sale Hola (el «=» lo pone el editor)');
comprueba(CF._valorDe({ asc_getValue1: () => '"""Opción 1"""' }) === 'Opción 1',
          'y de las comillas triples de las reglas viejas sale Opción 1');

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
    asc_getValue1: () => '="SIN COLOR"',
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
