/* Simulacro del editor: se comprueba QUÉ se le pide al aplicar una lista
   desplegable — la validación de datos y las reglas de color— y que lo que no
   debe pasar, no pasa. */

const recibido = { validacion: null, reglas: null, limpiado: false };

// ── Las piezas del editor que se usan ────────────────────────────────────
function Formula() { }
Formula.prototype.asc_setValue = function (v) { this.valor = v; };
Formula.prototype.asc_getValue = function () { return this.valor; };

function Validacion() { }
Validacion.prototype.asc_setType = function (t) { this.tipo = t; };
Validacion.prototype.asc_getType = function () { return this.tipo; };
Validacion.prototype.asc_setFormula1 = function (f) { this.formula = f; };
Validacion.prototype.asc_setFormula2 = function (f) { this.formula2 = f; };
Validacion.prototype.asc_setOperator = function (v) { this.operador = v; };
Validacion.prototype.asc_getFormula1 = function () { return this.formula; };
Validacion.prototype.asc_setShowDropDown = function (v) { this.flechita = v; };
Validacion.prototype.asc_setAllowBlank = function (v) { this.enBlanco = v; };
Validacion.prototype.asc_setShowErrorMessage = function (v) { this.avisaError = v; };
Validacion.prototype.asc_setErrorStyle = function (v) { this.estiloError = v; };
Validacion.prototype.asc_setErrorTitle = function (v) { this.tituloError = v; };
Validacion.prototype.asc_setError = function (v) { this.textoError = v; };
Validacion.prototype.asc_setShowInputMessage = function (v) { this.muestraAyuda = v; };
Validacion.prototype.asc_setPromptTitle = function (v) { this.tituloAyuda = v; };
Validacion.prototype.asc_setPrompt = function (v) { this.ayuda = v; };

function Regla() { }
Regla.prototype.asc_setType = function (v) { this.tipo = v; };
Regla.prototype.asc_setOperator = function (v) { this.operador = v; };
/* El nombre REAL, comprobado en el SDK 9.2.1: la regla tiene `asc_setValue1` y
   `asc_setValue2`, y NO tiene `asc_setValue`. El simulacro traía el que no
   existe, así que daba en verde un código que en el editor reventaba y dejaba
   la lista SIN colores (02/09/2026). */
Regla.prototype.asc_setValue1 = function (v) { this.valor = v; };
Regla.prototype.asc_setDxf = function (v) { this.formato = v; };
Regla.prototype.asc_setLocation = function (v) { this.donde = v; };

function Formato() { }
Formato.prototype.asc_setFillColor = function (c) { this.relleno = c; };

const TIPOS = { List:'lista', None:'ninguna', Custom:'personalizada',
                Date:'fecha', Decimal:'numero', Whole:'entero',
                TextLength:'largo', Time:'hora' };

let validacionExistente = null;
let avisaPrimero = false;

const ventanaEditor = {
    document: { body: {}, querySelectorAll: () => [] },
    Common: { Utils: { ThemeColor: { getRgbColor: (hex) => ({ hex: hex }) } } },
    Asc: {
        c_oAscEDataValidationType: TIPOS,
        c_oAscCFType: { cellIs: 'celda-es' },
        c_oAscEDataValidationErrorStyle: { Stop: 'rechaza', Warning: 'avisa' },
        c_oAscEDataValidationOperator: { Between:'entre', GreaterThan:'mayor',
            LessThan:'menor', LessThanOrEqual:'menor-igual', Equal:'igual' },
        c_oAscCFOperator: { equal: 'igual' },
        CDataFormula: Formula,
        asc_CConditionalFormattingRule: Regla,
        asc_CellXfs: Formato,
        editor: {
            asc_getDataValidationProps: function (respuesta) {
                // Como el editor: la primera vez avisa con un numero; si se le
                // dice que hacer, ya entrega la validacion.
                if (avisaPrimero && respuesta === undefined) return 3;
                return new Validacion();
            },
            asc_setDataValidation: (v) => {
                recibido.validacion = v;
                /* Como el editor de verdad: la fórmula se guarda SIEMPRE entre
                   comillas, doblando las que ya trajera. Por eso pasarle
                   «"a,b"» acababa en «\"\"\"a,b\"\"\"» en el archivo
                   (02/09/2026). */
                if (v.tipo === TIPOS.List && v.formula) {
                    const dado = String(v.formula.asc_getValue() || '');
                    recibido.guardada = '"' + dado.replace(/"/g, '""') + '"';
                    validacionExistente = {
                        asc_getType: () => TIPOS.List,
                        asc_getFormula1: () => ({ asc_getValue: () => recibido.guardada })
                    };
                }
            },
            /* Como el editor DE VERDAD: las reglas llegan en un array
               INDEXADO POR HOJA, y él mira la posición de la hoja abierta. Con
               la lista pelada no encontraba ninguna y no aplicaba nada: por eso
               el .xlsx de Wilson no tenía ni un color (02/09/2026). */
            asc_getActiveWorksheetIndex: () => 0,
            asc_setCF: (reglas) => {
                recibido.reglas = (reglas && reglas[0]) || null;
            },
            asc_clearCF: () => { recibido.limpiado = true; },
            asc_getCellInfo: () => ({
                asc_getSelectionRange: () => 'A3:A200',
                asc_getDataValidation: () => validacionExistente
            })
        }
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
global.setInterval = () => 1;
global.console = console;

const B = process.env.MAQ_JS
    || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';
require(B + 'editor-ventanas.js');
require(B + 'editor-lista-aplicar.js');

const L = window.MaquitaListas;
const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
console.log();

// ── Aplicar una lista con colores ────────────────────────────────────────
let r = L.aplicar(ventanaEditor, [
    { valor: 'ENERO', color: '#fce8b2' },
    { valor: 'FEBRERO', color: '#b7e1cd' },
    { valor: 'MARZO', color: '#c6dafc' }
]);

bien(r.ok === true, 'la lista se aplica');
bien(recibido.validacion.tipo === TIPOS.List, 'se pide una validacion de tipo LISTA');
bien(recibido.guardada === '"ENERO,FEBRERO,MARZO"',
     'los valores quedan guardados con UN par de comillas: ' + recibido.guardada);
/* El ajuste va AL REVES, como en el .xlsx: true = se ESCONDE la flechita del
   editor. Desde el 02/09/2026 se esconde a proposito en las listas con
   pastilla: la flechita del editor se dibuja FUERA de la casilla y la nuestra
   va dentro, asi que se veian las dos (video de Wilson).
   Asi lo usa el propio editor. Antes se pedia true y se estaba
   ESCONDIENDO el triangulito (02/09/2026). */
bien(recibido.validacion.flechita === true,
     'se esconde la flechita del editor: la pastilla dibuja la suya DENTRO');
bien(recibido.validacion.enBlanco === true, 'se puede dejar la celda vacia');

bien(recibido.reglas.length === 3, 'sale una regla de color por valor');
const primera = recibido.reglas[0];
bien(primera.tipo === 'celda-es' && primera.operador === 'igual',
     'la regla es «si la celda es igual a…»');
bien(primera.valor === '"ENERO"', 'el valor va entre comillas: es texto, no formula');
bien(primera.formato.relleno.hex === 'fce8b2', 'con su color de fondo');
bien(primera.donde === 'A3:A200', 'aplicada al rango elegido');

// ── Lo que NO debe pasar ─────────────────────────────────────────────────
r = L.aplicar(ventanaEditor, []);
bien(r.ok === false, 'sin valores no se aplica nada');

r = L.aplicar(ventanaEditor, [{ valor: 'SI, CLARO', color: '#e6e6e6' }]);
bien(r.ok === false && /coma/.test(r.problemas[0]),
     'un valor con coma se avisa en vez de romper la lista');

r = L.aplicar(ventanaEditor, [
    { valor: 'REPETIDO', color: '#e6e6e6' },
    { valor: 'REPETIDO', color: '#fce8b2' },
    { valor: '   ', color: '#b7e1cd' }
]);
bien(recibido.guardada === '"REPETIDO"',
     'los repetidos y los vacios se descartan');

const largos = [];
for (let i = 0; i < 40; i++) largos.push({ valor: 'VALOR-LARGUISIMO-' + i, color: '#e6e6e6' });
r = L.aplicar(ventanaEditor, largos);
bien(r.ok === false && /255/.test(r.problemas[0]),
     'si no cabe en la hoja, se avisa antes de aplicar');

// ── Quitar ───────────────────────────────────────────────────────────────
recibido.validacion = null;
L.quitar(ventanaEditor);
bien(recibido.validacion.tipo === TIPOS.None && recibido.limpiado === true,
     'quitar la lista se lleva tambien sus colores');

// ── Leer lo que ya hay, para poder editarlo ──────────────────────────────
const yaPuesta = new Validacion();
yaPuesta.asc_setType(TIPOS.List);
const f = new Formula(); f.asc_setValue('"ENERO,FEBRERO"');
yaPuesta.asc_setFormula1(f);
validacionExistente = yaPuesta;
bien(JSON.stringify(L.leerActual(ventanaEditor)) === '["ENERO","FEBRERO"]',
     'al reabrir, salen los valores que ya tenia');

validacionExistente = null;
bien(L.leerActual(ventanaEditor).length === 0,
     'si la celda no tiene lista, se empieza en blanco');


// ── Las opciones avanzadas del panel ─────────────────────────────────────
r = L.aplicar(ventanaEditor, [{ valor: 'ENERO', color: '#fce8b2' }], {
    ayuda: 'Elige el mes de inicio',
    siNoVale: 'avisar',
    estilo: 'plano'
});
bien(r.ok === true, 'se aplica con las opciones avanzadas');
bien(recibido.validacion.muestraAyuda === true
     && recibido.validacion.ayuda === 'Elige el mes de inicio',
     'el texto de ayuda queda guardado en la celda');
bien(recibido.validacion.estiloError === 'avisa',
     'con «mostrar una advertencia», el dato malo solo avisa');
bien(recibido.validacion.flechita === true,
     'con «texto sin formato» tampoco sale la flechita del editor');

r = L.aplicar(ventanaEditor, [{ valor: 'ENERO', color: '#fce8b2' }], {
    siNoVale: 'rechazar', estilo: 'flecha'
});
bien(recibido.validacion.estiloError === 'rechaza',
     'con «rechazar», el dato que no esta en la lista no entra');
bien(recibido.validacion.flechita === true,
     'con «flecha» se pinta la pastilla y se esconde la del editor');
bien(recibido.validacion.muestraAyuda === false, 'sin texto de ayuda, no se pone');

// Sin ajustes se comporta como antes.
r = L.aplicar(ventanaEditor, [{ valor: 'ENERO', color: '#fce8b2' }]);
bien(r.ok === true && recibido.validacion.flechita === true,
     'sin tocar nada, la lista sale con la flecha dentro de la pastilla');


// ── Los criterios del panel ──────────────────────────────────────────────
require(B + 'editor-lista-criterios.js');

function conCriterio(id, extra) {
    return L.aplicar(ventanaEditor, [], Object.assign({ criterio: id, rango: 'B2:B50' }, extra || {}));
}

let s = conCriterio('texto-contiene', { uno: 'Quito' });
bien(s.ok && recibido.validacion.tipo === 'personalizada'
     && recibido.validacion.formula.asc_getValue().indexOf('SEARCH') !== -1
     && recibido.validacion.formula.asc_getValue().indexOf(',B2)') !== -1,
     'el texto contiene -> formula sobre la primera celda del rango');

s = conCriterio('correo');
bien(s.ok && recibido.validacion.formula.asc_getValue().indexOf('SEARCH') !== -1,
     'correo valido -> comprueba la arroba y el punto');

s = conCriterio('numero-entre', { uno: '1', dos: '100' });
bien(s.ok && recibido.validacion.tipo === 'numero'
     && recibido.validacion.operador === 'entre'
     && recibido.validacion.formula2.asc_getValue() === '100',
     'numero entre -> dos limites');

s = conCriterio('fecha-posterior', { uno: '2026-01-01' });
bien(s.ok && recibido.validacion.tipo === 'fecha' && recibido.validacion.operador === 'mayor',
     'la fecha es posterior a');

s = conCriterio('lista-rango', { uno: 'A2:A20' });
bien(s.ok && recibido.validacion.tipo === 'lista'
     && recibido.validacion.formula.asc_getValue() === '=A2:A20',
     'menu desplegable de un intervalo');

s = conCriterio('texto-contiene', {});
bien(!s.ok, 'si falta el valor del criterio, se avisa y no se aplica');

s = conCriterio('numero-entre', { uno: '1' });
bien(!s.ok, 'si falta uno de los dos limites, tampoco');


// ── Cuando el editor avisa antes de dejar poner la regla ─────────────────
avisaPrimero = true;
recibido.validacion = null;
r = L.aplicar(ventanaEditor, [{ valor: 'ENERO', color: '#fce8b2' }]);
bien(r.ok === true && recibido.validacion !== null,
     'si el editor avisa primero, se le responde y la regla SI se aplica');
avisaPrimero = false;

// ── Las comillas NO se multiplican al reeditar (02/09/2026) ──────────────
// En un archivo de verdad habia listas asi: """""""v,vf"""""""
// Cada edicion le anadia un par mas, hasta dejarla inservible.
validacionExistente = {
    asc_getType: () => TIPOS.List,
    asc_getFormula1: () => ({ asc_getValue: () => '"""v,vf"""' })
};
let leidos = L.leerActual(ventanaEditor);
bien(leidos.join(',') === 'v,vf',
     'al reabrir una lista con comillas de mas, se leen los valores limpios: '
     + leidos.join(','));

L.aplicar(ventanaEditor, leidos.map(v => ({ valor: v, color: '' })));
bien(recibido.guardada === '"v,vf"',
     'y al guardarla queda con UN par de comillas: ' + recibido.guardada);

validacionExistente = {
    asc_getType: () => TIPOS.List,
    asc_getFormula1: () => ({ asc_getValue: () => '"a,b"' })
};
bien(L.leerActual(ventanaEditor).join(',') === 'a,b',
     'una lista normal se sigue leyendo igual');

// ── El color de cada valor se lee del PROPIO ARCHIVO ────────────────────
/* Se intentó guardar la pareja «valor → color» como propiedad del documento y
   no vale: el editor la crea VACÍA con todos los tipos, y buscar cuál servía
   dejaba la interfaz sin responder. El color ya está en su regla de formato
   condicional; de ahí se lee (02/09/2026). */
require(B + 'editor-lista-colores-cf.js');

let reglasEnLaHoja = [];
ventanaEditor.Asc.editor.asc_getActiveWorksheetIndex = () => 0;
ventanaEditor.Asc.editor.asc_getCF = () => [reglasEnLaHoja];
const conColor = (valor, hex) => ({
    asc_getValue1: () => '"' + valor + '"',
    asc_getDxf: () => ({ asc_getFillColor: () => ({
        get_r: () => parseInt(hex.substr(1, 2), 16),
        get_g: () => parseInt(hex.substr(3, 2), 16),
        get_b: () => parseInt(hex.substr(5, 2), 16) }) })
});

validacionExistente = null;
r = L.aplicar(ventanaEditor, [
    { valor: 'ENERO', color: '#fce8b2' },
    { valor: 'FEBRERO', color: '#b7e1cd' }
]);
bien(r.ok === true && recibido.reglas && recibido.reglas.length === 2,
     'al aplicar salen las dos reglas de color');

// Y al reabrir, cada valor vuelve con SU color, leído de esas reglas.
reglasEnLaHoja = [conColor('ENERO', '#fce8b2'), conColor('FEBRERO', '#b7e1cd')];
validacionExistente = {
    asc_getType: () => TIPOS.List,
    asc_getFormula1: () => ({ asc_getValue: () => '"ENERO,FEBRERO"' })
};
const paraEditar = L.leerElementos(ventanaEditor);
bien(paraEditar.length === 2 && paraEditar[0].valor === 'ENERO',
     'para editar salen los valores que tiene la celda');
bien(paraEditar[0].color === '#fce8b2',
     'ENERO vuelve con SU color, leido del archivo: ' + paraEditar[0].color);
bien(paraEditar[1].color === '#b7e1cd', 'y FEBRERO con el suyo');

// Un valor sin regla de color vuelve sin color: no se inventa ninguno.
reglasEnLaHoja = [conColor('ENERO', '#fce8b2')];
bien(L.leerElementos(ventanaEditor)[1].color === '',
     'un valor sin regla de color vuelve SIN color, no con uno inventado');

// Sin lista en la celda no hay nada que editar.
validacionExistente = null;
bien(L.leerElementos(ventanaEditor).length === 0,
     'sin lista en la celda, no hay elementos que editar');

// Sin el modulo de colores, la lista se sigue pudiendo aplicar y leer.
const guardaColores = window.MaquitaColoresCF;
delete window.MaquitaColoresCF;
validacionExistente = {
    asc_getType: () => TIPOS.List,
    asc_getFormula1: () => ({ asc_getValue: () => '"a,b"' })
};
const sinColores = L.leerElementos(ventanaEditor);
bien(sinColores.length === 2 && sinColores[0].color === '',
     'sin el modulo de colores, la lista se lee igual (sin colores)');
bien(L.aplicar(ventanaEditor, [{ valor: 'X', color: '#fce8b2' }]).ok === true,
     'y se puede aplicar igual: los colores son un extra, no un requisito');
window.MaquitaColoresCF = guardaColores;

// ── Que un fallo en los colores NO se lleve por delante lo demás ─────────
/* Era justo lo que pasaba: `asc_setValue` no existe, la excepción saltaba
   después de poner la validación, y ni se pintaban los colores ni se guardaba
   la definición. La lista tiene que quedar puesta igual, y hay que enterarse. */
const avisosCF = [];
window.MaquitaDiagnostico = { contar: (q, d) => avisosCF.push(q) };
const setValue1DeVerdad = Regla.prototype.asc_setValue1;
delete Regla.prototype.asc_setValue1;          // un editor que no lo tiene

validacionExistente = null;
r = L.aplicar(ventanaEditor, [{ valor: 'ENERO', color: '#fce8b2' }]);
bien(r.ok === true, 'si los colores fallan, la LISTA queda puesta igual');
bien(avisosCF.indexOf('colores de la lista') !== -1,
     'y se avisa de que los colores no se aplicaron: nada en silencio');
bien(recibido.validacion && recibido.validacion.tipo === TIPOS.List,
     'y la validacion sigue puesta, que es lo que antes se perdia');

Regla.prototype.asc_setValue1 = setValue1DeVerdad;

console.log();

