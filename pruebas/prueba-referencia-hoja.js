/* 27/11/2026 (Ajustes Drive Maquita – Excel, Karen Armas).
   Referencias a otra hoja escritas a mano, piezas de una hoja protegida con
   excepciones y fecha del calendario como número de serie. */
const B = process.env.MODULOS || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';
global.window = global;
global.document = { createElement() { return { style: {} }; }, head: { appendChild() { } } };
global.MaquitaEditor = { alAparecer() { } };
require(B + 'editor-referencia-hoja.js');
require(B + 'editor-proteger-hoja-rangos.js');
require(B + 'editor-calendario-fecha.js');
const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);

const hojas = ['Datos', '0. Índice global', '1. BD Aplicación Destrezas'];
const v = { Asc: { editor: {
    asc_getWorksheetsCount: () => hojas.length, asc_getWorksheetName: (i) => hojas[i],
    asc_getActiveWorksheetIndex: () => 2 } } };
const R = window.MaquitaReferencia;
const n = (t) => R.normalizar(v, t);
bien(n('datos!e4:e119').texto === 'Datos!$E$4:$E$119', 'hoja con otra mayúscula y celdas relativas');
bien(n('=Datos!E4:E119').texto === 'Datos!$E$4:$E$119', 'con el signo igual delante');
bien(n('1. BD Aplicación Destrezas!A5:E13').texto === "'1. BD Aplicación Destrezas'!$A$5:$E$13",
     'hoja con espacios y punto: se ponen las comillas');
bien(n('0. indice global!b8:b27').texto === "'0. Índice global'!$B$8:$B$27", 'sin tilde también se reconoce');
bien(!n('Otra!A1').ok && /No existe la hoja/.test(n('Otra!A1').problema), 'hoja que no existe: se dice');
bien(!n('Datos!E4:F').ok, 'intervalo mal escrito: se dice');
bien(n('Provincias').texto === 'Provincias', 'un nombre definido se respeta');
bien(R.conHoja(v, '$E$4:$E$119') === "'1. BD Aplicación Destrezas'!$E$4:$E$119", 'lo marcado lleva su hoja');

const cache = { getAscRange(t) {
    const col = (s) => [...s].reduce((a, ch) => a * 26 + ch.charCodeAt(0) - 64, 0) - 1;
    let m = /^([A-Z]+)(\d+):([A-Z]+)(\d+)$/.exec(t);
    if (m) return { r1: +m[2] - 1, c1: col(m[1]), r2: +m[4] - 1, c2: col(m[3]) };
    m = /^([A-Z]+)(\d+)$/.exec(t);
    return m ? { r1: +m[2] - 1, c1: col(m[1]), r2: +m[2] - 1, c2: col(m[1]) } : null;
} };
const v2 = { AscCommonExcel: { g_oRangeCache: cache } };
const H = window.MaquitaProtegerHoja;
bien(H._piezas(v2, []).join() === 'A1:XFD1048576', 'hoja entera: una pieza');
bien(H._piezas(v2, ['B5:D9']).join() === 'A1:XFD4,A10:XFD1048576,A5:A9,E5:XFD9',
     'excepto B5:D9: cuatro piezas que la rodean');
const grupos = H.agrupar([
    { nombre: 'Hoja «X»', soloAvisar: false, personas: [{ id: 1, permiso: 'editar' }] },
    { nombre: 'Hoja «X»', soloAvisar: false, personas: [{ id: 1, permiso: 'editar' }] },
    { nombre: 'Otra', soloAvisar: false, personas: [] }]);
bien(grupos.length === 2 && grupos[0].miembros.length === 2, 'las piezas de una hoja se ven como una');

const C = window.MaquitaCalendarioFecha;
bien(C._serie(new Date(2025, 6, 14)) === 45852, 'el 14/07/2025 se escribe como 45852 (serie de Excel)');
bien(C._fechaDeTexto('14/07/2025').getMonth() === 6, 'se lee la fecha de la celda en día/mes/año');
bien(C._fechaDeTexto('texto') === null, 'si la celda no tiene fecha, se abre en el mes actual');

// 27/11/2026 (2): OnlyOffice 10 no expone `api.wb` ni `g_oRangeCache`.
bien(H._piezas({}, ["'1. BD Aplicación Destrezas'!$B$5:$D$9"]).join() === 'A1:XFD4,A10:XFD1048576,A5:A9,E5:XFD9',
     'excepciones sin g_oRangeCache (analizador propio, con hoja y $)');
bien(H._piezas({}, ['C:C']).join() === 'A1:B1048576,D1:XFD1048576', 'excepción de una columna entera');
const hecho = [];
const vCal = { Asc: { c_oAscPopUpSelectorType: { None: 'ninguno' }, editor: {
    asc_closeCellEditor: (c) => hecho.push('cerrar:' + c),
    asc_insertInCell: (t, tipo, auto) => hecho.push('escribir:' + t + ':' + tipo + ':' + auto) } } };
bien(C._escribir(vCal, new Date(2025, 6, 14)) === true
     && hecho.join() === 'cerrar:true,escribir:45852:ninguno:false',
     'el calendario cierra la celda y escribe con la API pública (asc_insertInCell), sin api.wb');
bien(C._escribir({ Asc: { editor: {} } }, new Date()) === false, 'sin esa API, avisa en vez de romperse');

// 27/11/2026 (2): «Hasta la fila 8 / Hasta la columna V» con la API pública (sin api.wb).
require(B + 'editor-inmovilizar.js');
// En OnlyOffice 10 sale de asc_getActiveRangeStr (la información de la celda ya no trae asc_getName).
const celdaCon = (n) => window.MaquitaInmovilizar.celdaActiva({ Asc: { referenceType: { A: 'A' }, editor: {
    asc_getCellInfo: () => ({}), asc_getActiveRangeStr: () => n } } });
bien(JSON.stringify(celdaCon('V8')) === '{"fila":7,"col":21}', 'la celda activa V8 se lee sin api.wb (fila 8, columna V)');
bien(JSON.stringify(celdaCon('$AB$120')) === '{"fila":119,"col":27}', 'también con $ y dos letras');
bien(JSON.stringify(celdaCon('$H$9:$J$12')) === '{"fila":8,"col":7}', 'con varias celdas marcadas, la primera');
