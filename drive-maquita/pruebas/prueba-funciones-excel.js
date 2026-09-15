/* Funciones de Excel añadidas al editor. Dos partes:
   1) el REGISTRO: se simula el editor tal como es en 9.2.1 —AddCustomFunction
      lee una cola `this.X.shift()` y AscCommon trae un analizador de JSDoc— y se
      comprueba que se localizan las piezas y se registran las 8 en orden;
   2) el CÁLCULO: cada función, con los mismos casos que documenta Microsoft. */

const registradas = [];
let colaPuesta = null;

// El editor: AddCustomFunction tal como viene minificado (lo que importa es la forma).
const editor = {
    AddCustomFunction: function (D) { var K = this.aRb && this.aRb.shift(); registradas.push([D.name, K && K.marca]); },
    asc_calculate: function () { editor.recalculado = true; }
};
// El analizador de JSDoc del editor (por dentro usa /@param\s+{…/ y /@returns?\s+{…/).
function analizadorFalso(fa) {
    const r = /@param\s+{(\??)(.+?)}/g; const s = /@returns?\s+{(.+?)}/g; void r; void s;
    return (fa.match(/@customfunction/g) || []).map(function (_x, i) { return { marca: i }; });
}
const ventanaEditor = {
    document: { body: {}, querySelectorAll: () => [] },
    Asc: { editor: editor, c_oAscCalculateType: { All: 0 } },
    AscCommon: { otra: function (a, b) { return a + b; }, AIj: analizadorFalso },
    Function: Function
};
global.window = global;
global.document = { querySelectorAll: (s) => (s === 'iframe' ? [{ contentWindow: ventanaEditor }] : []) };
global.setInterval = () => 1;
global.navigator = { userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' };
global.console = console;

require('/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/editor-ventanas.js');
require('/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/editor-funciones-excel.js');

const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
const igual = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const lanza = (f) => { try { f(); return false; } catch (e) { return true; } };
console.log();

const M = window.MaquitaFuncionesExcel;
const piezas = M.localizar(ventanaEditor);

// ── 1. Registro ──
bien(piezas && piezas.cola === 'aRb', 'localiza la cola de metadatos por su forma (this.X && this.X.shift())');
bien(piezas && piezas.analizador === analizadorFalso, 'localiza el analizador de JSDoc entre las funciones de AscCommon');
// Al cargar el módulo, editor-ventanas ya encontró el iframe y llamó a registrar().
bien(igual(registradas.map(x => x[0]), M.NOMBRES), 'registra las 8 funciones en el orden del código: ' + registradas.map(x => x[0]).join(','));
bien(registradas.every((x, i) => x[1] === i), 'cada función recibe SUS metadatos (la cola se consume en orden)');
bien(editor.recalculado === true, 'tras registrar pide recalcular el libro');
bien(M.registrar({ document: { body: {} } }) === false, 'sin editor todavía, dice «todavía no» (false) para que se reintente');
bien((M.CODIGO.match(/Api\.AddCustomFunction\(/g) || []).length === (M.CODIGO.match(/@customfunction/g) || []).length,
     'cada AddCustomFunction del código lleva su bloque JSDoc con @customfunction');

// ── 2. Cálculo ──
const f = M.impl;
bien(f.regexTest('Factura 2026-001', '^Factura \\d{4}-\\d{3}$') === true, 'REGEXTEST reconoce el patrón');
bien(f.regexTest('factura', 'FACTURA') === false && f.regexTest('factura', 'FACTURA', 1) === true,
     'REGEXTEST distingue mayúsculas salvo case_sensitivity=1');

bien(igual(f.regexExtract('Tel 0991234567 y 0987654321', '\\d{10}'), [['0991234567']]), 'REGEXEXTRACT modo 0: primera coincidencia');
bien(igual(f.regexExtract('Tel 0991234567 y 0987654321', '\\d{10}', 1), [['0991234567', '0987654321']]), 'REGEXEXTRACT modo 1: todas');
bien(igual(f.regexExtract('Juan Pérez', '(\\S+)\\s(\\S+)', 2), [['Juan', 'Pérez']]), 'REGEXEXTRACT modo 2: grupos de captura');
bien(lanza(() => f.regexExtract('sin números', '\\d+')), 'REGEXEXTRACT sin coincidencia da error (#¡VALOR! en la celda)');

bien(f.regexReplace('a1b22c333', '\\d+', '#') === 'a#b#c#', 'REGEXREPLACE ocurrencia 0: todas');
bien(f.regexReplace('a1b22c333', '\\d+', '#', 2) === 'a1b#c333', 'REGEXREPLACE ocurrencia 2: solo la segunda');
bien(f.regexReplace('a1b22c333', '\\d+', '#', -1) === 'a1b22c#', 'REGEXREPLACE ocurrencia -1: la última');
bien(f.regexReplace('Pérez, Juan', '([^,]+), (.+)', '$2 $1') === 'Juan Pérez', 'REGEXREPLACE usa $1 $2 como Excel');
bien(f.regexReplace('abc', 'b', '[$0]') === 'a[b]c', 'REGEXREPLACE entiende $0 (coincidencia entera) como Excel');

bien(f.valueToText(12.5) === '12.5' && f.valueToText(true) === 'TRUE', 'VALUETOTEXT conciso: número y lógico');
bien(f.valueToText('hola') === 'hola' && f.valueToText('hola', 1) === '"hola"', 'VALUETOTEXT estricto pone comillas al texto');
bien(f.valueToText('') === '' && f.valueToText(null) === '', 'VALUETOTEXT de celda vacía es texto vacío');

bien(Math.abs(f.percentOf([[25], [25]], [[100], [50], [50]]) - 0.25) < 1e-12, 'PERCENTOF = suma(subconjunto)/suma(total)');
bien(f.percentOf([[10, 'texto']], [[20, null], ['', 20]]) === 0.25, 'PERCENTOF ignora textos y vacíos');
bien(lanza(() => f.percentOf([[1]], [[0]])), 'PERCENTOF con total 0 da error');

const conBordes = [['', '', '', ''], ['', 'a', 'b', ''], ['', 'c', '', ''], ['', '', '', '']];
bien(igual(f.trimRange(conBordes), [['a', 'b'], ['c', '']]), 'TRIMRANGE quita filas y columnas vacías de los bordes');
bien(igual(f.trimRange(conBordes, 1, 0), [['', 'a', 'b', ''], ['', 'c', '', ''], ['', '', '', '']]), 'TRIMRANGE 1,0: solo filas vacías iniciales');
bien(igual(f.trimRange(conBordes, 3, 3), [['', '', ''], ['', 'a', 'b'], ['', 'c', '']]), 'TRIMRANGE 3,3: solo las finales');
bien(lanza(() => f.trimRange([['', ''], ['', '']])), 'TRIMRANGE de un rango todo vacío da error');
bien(lanza(() => f.trimRange(conBordes, 4)), 'TRIMRANGE rechaza códigos fuera de 0-3');

bien(f.info('system') === 'pcdos' && f.info('recalc') === 'Automatic', 'INFO devuelve system y recalc como Excel en Windows');
bien(lanza(() => f.info('memavail')), 'INFO con un tipo no admitido da error');
