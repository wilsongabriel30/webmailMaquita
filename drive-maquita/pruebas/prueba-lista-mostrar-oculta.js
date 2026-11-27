/* 27/11/2026. Listas con la flecha oculta (ShowDropDown=true): al entrar en
   una de sus celdas, la regla entera pasa a mostrar la lista y la selección
   de la persona vuelve a quedar como estaba. Vale para cualquier archivo. */
const B = process.env.MODULOS || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';
global.window = global;
global.MaquitaEditor = { alAparecer() { } };
require(B + 'editor-lista-mostrar-oculta.js');
const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);

function editor(oculta, tipo) {
    const e = { sel: '$A$5', regla: { oculta: oculta, tipo: tipo === undefined ? 4 : tipo }, llamadas: [] };
    const validacion = () => ({ asc_getType: () => e.regla.tipo, asc_getShowDropDown: () => e.regla.oculta,
        asc_getFormula1: () => ({ asc_getValue: () => 'Datos!$E$4:$E$8' }) });
    e.api = {
        asc_getCellInfo: () => ({ asc_getMultiselect: () => false, asc_getDataValidation: validacion }),
        asc_getActiveRangeStr: () => e.sel,
        asc_findCell: (t) => { e.llamadas.push('volver ' + t); e.sel = t; },
        asc_getDataValidationProps: () => { const p = Object.assign(validacion(), { cambio: null });
            p.asc_setShowDropDown = (x) => { p.cambio = x; }; return p; },
        asc_setDataValidation: (p, similar) => {
            if (similar === true) { e.llamadas.push('ampliar'); e.sel = '$A$2:$A$20'; return true; }
            e.llamadas.push('aplicar ' + e.sel + ' flecha oculta=' + p.cambio); e.regla.oculta = p.cambio; return true;
        }
    };
    e.ventana = { Asc: { editor: e.api, referenceType: { A: 0 }, c_oAscEDataValidationType: { List: 4 } } };
    return e;
}
const M = window.MaquitaListaMostrarOculta;
let e = editor(true);
bien(!!M.listaOculta(e.ventana), 'se reconoce una lista con la flecha oculta');
bien(M.reparar(e.ventana) === '$A$2:$A$20', 'se repara la regla entera (A2:A20)');
bien(e.llamadas.join(' | ') === 'ampliar | aplicar $A$2:$A$20 flecha oculta=false | volver $A$5',
     'amplía a la regla, la deja visible y devuelve la selección: ' + e.llamadas.join(' | '));
bien(!M.listaOculta(e.ventana), 'después ya no hay nada que reparar');
bien(!M.listaOculta(editor(false).ventana), 'una lista visible no se toca');
bien(!M.listaOculta(editor(true, 1).ventana), 'otra validación (número) no se toca');
