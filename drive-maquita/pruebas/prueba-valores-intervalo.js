/* Los valores de una lista por intervalo se leen del modelo (también de una hoja
   oculta), sin repetidos, acotando columnas enteras; y la flechita de la
   pastilla los usa para abrir la lista como las demás, en vez de caer en el
   atajo del editor («No hay selecciones para llenar la celda»). */

const hojas = {
    'Personas con acceso': { '0,0': 'Nombre', '0,1': 'Ana Pérez', '0,2': 'Luis Mora', '0,3': 'Rosa Vega', '0,4': 'Luis Mora' },
    'Hoja1': { '11,1': 'ENERO', '11,2': 'FEBRERO', '11,3': 'ENERO', '11,4': '' }
};
function modeloDe(nombre) {
    const celdas = hojas[nombre];
    return {
        getCell3: (r, c) => ({ getValueWithFormat: () => celdas[c + ',' + r] || '' }),
        getRange3: (r1, c1, r2, c2) => ({
            _foreachNoEmpty: (fn) => {
                for (let r = r1; r <= r2; r++) for (let c = c1; c <= c2; c++) {
                    const v = celdas[c + ',' + r];
                    if (v !== undefined && v !== '') fn({ getValueWithFormat: () => v });
                }
            }
        })
    };
}
const rangos = { 'A2:A5': { r1: 1, c1: 0, r2: 4, c2: 0 }, 'L:L': { r1: 0, c1: 11, r2: 1048575, c2: 11 }, 'A2:A20': { r1: 1, c1: 0, r2: 19, c2: 0 } };
let formulaActual = "='Personas con acceso'!$A$2:$A$5";
const api = {
    wbModel: { getWorksheetByName: (n) => hojas[n] ? modeloDe(n) : null },
    wb: { getWorksheet: () => ({ model: modeloDe('Hoja1') }) },
    asc_getCellInfo: () => ({ asc_getDataValidation: () => ({ asc_getType: () => 4, asc_getFormula1: () => ({ asc_getValue: () => formulaActual }) }) })
};
const ventana = { Asc: { editor: api, c_oAscEDataValidationType: { List: 4 } }, AscCommonExcel: { g_oRangeCache: { getAscRange: (ref) => rangos[ref] || null } } };

global.window = global;
global.document = { querySelectorAll: () => [] };
global.setInterval = () => 1;
const B = process.env.MODULOS || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';
require(B + 'editor-lista-valores-intervalo.js');

const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
console.log();
const M = window.MaquitaValoresIntervalo;
let p = M._parsear("='Personas con acceso'!$A$2:$A$5");
bien(p.hoja === 'Personas con acceso' && p.ref === 'A2:A5', "entiende «='Personas con acceso'!$A$2:$A$5» (hoja con espacios y comillas)");
p = M._parsear('Consolidado!$L:$L');
bien(p.hoja === 'Consolidado' && p.ref === 'L:L', 'y «Consolidado!$L:$L» (columna entera)');
p = M._parsear('A2:A20');
bien(p.hoja === '' && p.ref === 'A2:A20', 'y «A2:A20» (hoja activa)');

let v = M.valoresDe(ventana, "='Personas con acceso'!$A$2:$A$5");
bien(JSON.stringify(v) === JSON.stringify(['Ana Pérez', 'Luis Mora', 'Rosa Vega']), 'lee los nombres de la hoja (oculta) sin la cabecera y sin repetidos: ' + v.join(' | '));
v = M.valoresDe(ventana, 'Hoja1!$L:$L');
bien(JSON.stringify(v) === JSON.stringify(['ENERO', 'FEBRERO']), 'una columna entera: solo los textos que hay, sin repetir: ' + v.join(' | '));
v = M.valoresDe(ventana, 'A2:A20');
bien(Array.isArray(v) && v.length === 0, 'un intervalo vacío de la hoja activa → []');
v = M.valoresDe(ventana, "='No existe'!A1:A3");
bien(v.length === 0, 'una hoja que no existe → [] sin explotar');

v = M.deLaCelda(ventana);
bien(v.length === 3 && v[0] === 'Ana Pérez', 'deLaCelda: con la celda activa en una lista por intervalo, sus valores');
formulaActual = '"Sí,No"';
bien(M.deLaCelda(ventana).length === 0, 'con una lista escrita no se mete (eso ya lo hace leerActual)');
api.asc_getCellInfo = () => { throw new Error('explotó'); };
bien(M.deLaCelda(ventana).length === 0, 'si el editor falla, [] y nada más');
