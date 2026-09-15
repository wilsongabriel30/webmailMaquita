/* «Personas con acceso»: la lista de personas se escribe en una hoja OCULTA
   («Personas con acceso», nombres de A2 hacia abajo) y la celda recibe una
   lista por intervalo hacia esa hoja; se vuelve a la hoja en la que se estaba;
   al reaplicar se reescribe (y se limpian sobrantes); el panel rellena las
   filas con la gente de la API, con un color cada una, y reconoce la lista al
   reabrir. */

// ── un editor de mentira con hojas, celdas y las funciones del SDK que se usan ──
const hojas = [{ nombre: 'Hoja1', oculta: false, celdas: {} }, { nombre: 'Datos', oculta: false, celdas: {} }];
let activa = 1;
const seleccionadas = [];
function vista(i) {
    const h = hojas[i];
    let sel = { c: 0, r: 0 };
    return {
        setSelection: (rg) => { sel = { c: rg.c1, r: rg.r1 }; seleccionadas.push(h.nombre + ':' + rg.c1 + ',' + rg.r1); },
        setSelectionInfo: (que, valor) => { if (que === 'value') h.celdas[sel.c + ',' + sel.r] = valor; },
        model: { getCell3: (r, c) => ({ getValueWithFormat: () => h.celdas[c + ',' + r] || '' }) }
    };
}
const api = {
    asc_getWorksheetsCount: () => hojas.length,
    asc_getWorksheetName: (i) => hojas[i].nombre,
    asc_getActiveWorksheetIndex: () => activa,
    asc_addWorksheet: (n) => { hojas.push({ nombre: n, oculta: false, celdas: {} }); activa = hojas.length - 1; },
    asc_showWorksheet: (i) => { hojas[i].oculta = false; activa = i; },
    asc_hideWorksheet: () => { hojas[activa].oculta = true; activa = 0; },
    wb: { getWorksheet: (i) => vista(i) }
};
function Range(c1, r1, c2, r2) { this.c1 = c1; this.r1 = r1; this.c2 = c2; this.r2 = r2; }
const ventana = { Asc: { editor: api, Range: Range } };

global.window = global;
global.document = { querySelectorAll: () => [] };
global.setInterval = () => 1;
const buzon = [];
window.MaquitaDiagnostico = { contar: (m, d) => buzon.push([m, d]) };
const aplicadas = [];
window.MaquitaListas = { aplicar: (v, elementos, ajustes) => { aplicadas.push({ elementos, ajustes }); return { ok: true, criterio: ajustes.criterio }; } };

const B = process.env.MODULOS || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';
require(B + 'editor-lista-personas.js');
require(B + 'editor-lista-panel-personas.js');

const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
console.log();
const LP = window.MaquitaListaPersonas;
bien(window.MaquitaListas.aplicar.__personas === true, 'envuelve MaquitaListas.aplicar');

// ── aplicar con criterio «personas» ──
let r = window.MaquitaListas.aplicar(ventana, [{ valor: 'Ana Pérez', color: '#f4c7c3' }, { valor: 'Luis Mora', color: '#ffd7b5' }, { valor: 'Rosa Vega', color: '#fce8b2' }], { criterio: 'personas', rango: 'Datos!C2:C50' });
const hoja = hojas.find(h => h.nombre === 'Personas con acceso');
bien(r.ok && !!hoja, 'crea la hoja «Personas con acceso»');
bien(hoja && hoja.oculta === true, 'y la deja OCULTA');
bien(hoja && hoja.celdas['0,0'] === 'Nombre' && hoja.celdas['0,1'] === 'Ana Pérez' && hoja.celdas['0,3'] === 'Rosa Vega', 'con la cabecera en A1 y los nombres de A2 hacia abajo');
bien(activa === 1 && hojas[activa].nombre === 'Datos', 'la persona sigue en la hoja en la que estaba (Datos)');
bien(aplicadas.length === 1 && aplicadas[0].ajustes.criterio === 'lista-rango' && aplicadas[0].ajustes.uno === "='Personas con acceso'!$A$2:$A$4", 'la lista se aplica como intervalo hacia esa hoja: ' + (aplicadas[0] && aplicadas[0].ajustes.uno));
bien(aplicadas[0].ajustes.rango === 'Datos!C2:C50' && aplicadas[0].elementos.length === 3 && aplicadas[0].elementos[1].color === '#ffd7b5', 'y conserva el intervalo destino y los colores por persona');
bien(buzon.some(b => b[0] === 'lista de personas' && b[1].personas === '3'), 'lo cuenta en el buzón');

// ── reaplicar con menos personas: se reescribe y se limpian sobrantes ──
r = window.MaquitaListas.aplicar(ventana, [{ valor: 'Luis Mora', color: '#ffd7b5' }], { criterio: 'personas' });
bien(hoja.celdas['0,1'] === 'Luis Mora' && hoja.celdas['0,2'] === '' && hoja.celdas['0,3'] === '', 'al reaplicar reescribe los nombres y deja en blanco los sobrantes');
bien(hoja.oculta === true && hojas.length === 3 && aplicadas[1].ajustes.uno === "='Personas con acceso'!$A$2:$A$2", 'no crea otra hoja, la vuelve a ocultar y la fórmula se ajusta al número de personas');
bien(hojas[activa].nombre === 'Datos', 'y sigue en su hoja');

// ── otros criterios ni se enteran ──
r = window.MaquitaListas.aplicar(ventana, [{ valor: 'A' }], { criterio: 'lista' });
bien(aplicadas[2].ajustes.criterio === 'lista' && LP._estado.escrituras === 2, 'una lista normal pasa directa al aplicar de siempre');
r = window.MaquitaListas.aplicar(ventana, [], { criterio: 'personas' });
bien(r.ok === false && /ninguna persona/.test(r.problemas[0]), 'sin personas: avisa y no toca nada');
bien(LP.esNuestra("='Personas con acceso'!$A$2:$A$9") && !LP.esNuestra('Consolidado!$L:$L'), 'reconoce cuándo un origen es nuestra hoja');

// ── el panel: rellenar con la gente de la API ──
const filasDom = { hijos: [], querySelectorAll: function () { return this.hijos.map(h => ({ remove: () => { this.hijos = this.hijos.filter(x => x !== h); } })); }, appendChild: function (f) { this.hijos.push(f); } };
const avisos = [];
const ctx = {
    selector: { value: 'personas', onchange: null }, filas: filasDom,
    nuevaFila: (valor, color) => ({ valor, color }),
    colores: [{ color: '#e6e6e6' }, { color: '#f4c7c3' }, { color: '#ffd7b5' }],
    ventana: ventana, origen: '', avisar: (m) => avisos.push(m)
};
window.MaquitaColoresCelda = { coloresDeLaCelda: () => ({ 'Luis Mora': '#123456' }) };
window.MaquitaProtegerPersonas = { deArchivo: () => Promise.resolve([{ nombre: 'Ana Pérez', motivo: 'Miembro' }, { nombre: 'Luis Mora', motivo: 'Tú' }, { nombre: 'Luis Mora', motivo: 'Dueño' }, { nombre: '', motivo: '' }]) };
const P = window.MaquitaPanelPersonas;
bien(P.alCambiarCriterio(ctx) === true, 'al elegir «Personas con acceso» pide la gente');
setTimeout(function () {
    bien(filasDom.hijos.length === 2 && filasDom.hijos[0].valor === 'Ana Pérez' && filasDom.hijos[1].valor === 'Luis Mora', 'una fila por persona, sin repetidos ni vacíos: ' + filasDom.hijos.map(h => h.valor).join(' | '));
    bien(filasDom.hijos[0].color === '#f4c7c3' && filasDom.hijos[1].color === '#123456', 'color de la paleta (sin el «sin color») y, si la celda ya tenía uno para esa persona, ese');
    bien(avisos[avisos.length - 1] === '', 'quita el aviso de «buscando» al terminar');
    ctx.selector.value = 'lista';
    bien(P.alCambiarCriterio(ctx) === false, 'con otro criterio no hace nada');
    // reabrir sobre una lista nuestra
    let cambiado = false;
    ctx.selector = { value: 'lista-rango', onchange: () => { cambiado = true; } };
    ctx.origen = "='Personas con acceso'!$A$2:$A$4";
    bien(P.alAbrir(ctx) === true && ctx.selector.value === 'personas' && cambiado, 'al reabrir el panel sobre una lista de personas, el criterio sale como «Personas con acceso»');
    ctx.origen = 'Consolidado!$L:$L'; ctx.selector.value = 'lista-rango';
    bien(P.alAbrir(ctx) === false && ctx.selector.value === 'lista-rango', 'sobre una lista de intervalo normal, no');
    window.MaquitaProtegerPersonas = { deArchivo: () => Promise.resolve([]) };
    ctx.selector = { value: 'personas' };
    P.alCambiarCriterio(ctx);
    setTimeout(function () {
        bien(/Nadie más tiene acceso/.test(avisos[avisos.length - 1]), 'si nadie más tiene acceso, lo dice en vez de dejar el panel vacío sin explicación');
    }, 0);
}, 0);
