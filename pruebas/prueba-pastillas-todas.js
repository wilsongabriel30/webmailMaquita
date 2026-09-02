/* La pastilla en TODAS las celdas visibles con lista.

   Esto se apoya en piezas INTERNAS del editor, que una actualización puede
   cambiar. Por eso lo que más se comprueba aquí no es que pinte, sino que
   cuando algo no encaja NO pinte nada: más vale ninguna pastilla que la hoja
   llena de pastillas descolocadas. */

const TIPOS = { List: 3, Custom: 7 };

// Una hoja de 20 px por fila y 64 por columna, para que las cuentas sean claras.
function hojaCon(opciones) {
    opciones = opciones || {};
    return {
        visibleRange: opciones.visto || { c1: 0, r1: 0, c2: 19, r2: 25 },
        getCellLeftRelative: function (col) { return col * 64 + (opciones.desvioX || 0); },
        getCellTopRelative: function (fila) { return fila * 20 + (opciones.desvioY || 0); }
    };
}

function editorCon(opciones) {
    opciones = opciones || {};
    const hoja = opciones.sinHoja ? null : hojaCon(opciones);
    return {
        wb: { getWorksheet: () => hoja },
        wbModel: {
            getActiveWs: function () {
                const ws = {
                    selectionRange: { activeCell: { col: 2, row: 3 } }
                };
                // Las validaciones no llevan un nombre fijo: van minificadas.
                ws[opciones.claveRara || 'zZ7'] = opciones.validaciones || [];
                return ws;
            }
        },
        // La celda activa (col 2, fila 3) ⇒ 128,60 con las medidas de arriba.
        asc_getActiveCellCoord: () => ({
            asc_getX: () => 128, asc_getY: () => 60,
            asc_getWidth: () => 64, asc_getHeight: () => 20
        })
    };
}

function ventanaCon(editor) {
    return {
        Asc: { editor: editor, c_oAscEDataValidationType: TIPOS },
        document: { querySelectorAll: () => [] }
    };
}

const unaLista = function (c1, r1, c2, r2) {
    return { type: TIPOS.List, formula1: '"A,B"',
             ranges: [{ c1: c1, r1: r1, c2: c2, r2: r2 }] };
};

global.window = global;
global.console = console;

const B = process.env.MAQ_JS
    || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';
require(B + 'editor-pastillas-todas.js');

const T = window.MaquitaPastillasTodas;
const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
console.log('\n[Drive Maquita] la pastilla en todas las celdas\n');

// ── Lo normal ────────────────────────────────────────────────────────────
let v = ventanaCon(editorCon({ validaciones: [unaLista(1, 1, 2, 2)] }));
let celdas = T.celdasConLista(v);

bien(celdas.length === 4, 'un rango de 2x2 da cuatro pastillas: ' + celdas.length);
bien(celdas[0].x === 64 && celdas[0].y === 20,
     'la primera cae donde toca: ' + celdas[0].x + ',' + celdas[0].y);
bien(celdas[0].ancho === 64 && celdas[0].alto === 20,
     'con el tamaño de la celda: ' + celdas[0].ancho + 'x' + celdas[0].alto);

// ── Solo lo que se ve ────────────────────────────────────────────────────
v = ventanaCon(editorCon({
    validaciones: [unaLista(0, 0, 5, 999)],       // una columna larguísima
    visto: { c1: 0, r1: 0, c2: 19, r2: 4 }        // pero solo se ven 5 filas
}));
celdas = T.celdasConLista(v);
bien(celdas.length === 30,
     'de un rango enorme solo se pinta lo que se ve: ' + celdas.length + ' (6x5)');

/* ── El desvío entre las dos formas de medir se CORRIGE ──────────────────
   Las posiciones internas van respecto al área de datos y las públicas incluyen
   los encabezados, así que NUNCA coinciden. Exigir que coincidieran era lo que
   dejaba la hoja sin una sola pastilla («medidas fiables NO» en el diagnóstico
   de Wilson, 02/09/2026). Ahora se mide la diferencia con la celda activa —que
   se sabe de las dos maneras— y se aplica a las demás. */
window.__maqMedidasAvisadas = false;
v = ventanaCon(editorCon({
    validaciones: [unaLista(1, 1, 1, 1)],
    desvioX: 50                                   // como los encabezados
}));
let corregidas = T.celdasConLista(v);
bien(corregidas.length === 1,
     'con las dos medidas desplazadas se sigue pintando');
bien(corregidas[0].x === 64,
     'y la pastilla cae donde el editor la pinta, ya corregida: ' + corregidas[0].x);

// Lo que SÍ es una avería: que el TAMAÑO de la celda no cuadre.
window.__maqMedidasAvisadas = false;
const editorRaro = editorCon({ validaciones: [unaLista(1, 1, 2, 2)] });
editorRaro.asc_getActiveCellCoord = () => ({
    asc_getX: () => 128, asc_getY: () => 60,
    asc_getWidth: () => 200, asc_getHeight: () => 90     // nada que ver
});
v = ventanaCon(editorRaro);
bien(T.medidasFiables(v, T.hojaVisible(v).ws) === false,
     'se nota que el tamaño de la celda ya no cuadra');
bien(T.celdasConLista(v).length === 0,
     'y entonces NO se pinta nada: mejor ninguna que descolocadas');

// ── Solo las listas llevan pastilla ──────────────────────────────────────
window.__maqMedidasAvisadas = false;
v = ventanaCon(editorCon({
    validaciones: [{ type: TIPOS.Custom, ranges: [{ c1: 1, r1: 1, c2: 1, r2: 1 }] }]
}));
bien(T.celdasConLista(v).length === 0,
     'una validacion que no es lista no lleva pastilla');

v = ventanaCon(editorCon({
    validaciones: [{ ranges: [{ c1: 1, r1: 1, c2: 1, r2: 1 }], formula1: '"A"' }]
}));
bien(T.celdasConLista(v).length === 0,
     'y si no se puede saber el tipo, no se inventa: no se pinta');

// ── Se encuentran aunque el nombre este minificado ──────────────────────
v = ventanaCon(editorCon({
    validaciones: [unaLista(1, 1, 1, 1)], claveRara: 'q4'
}));
bien(T.celdasConLista(v).length === 1,
     'las validaciones se buscan por su FORMA, no por el nombre de la propiedad');

// ── Si al editor le falta alguna pieza, no se rompe ─────────────────────
bien(T.celdasConLista(ventanaCon(editorCon({ sinHoja: true }))).length === 0,
     'sin la hoja visible, ninguna pastilla y sin romperse');
bien(T.celdasConLista(ventanaCon({})).length === 0, 'con un editor pelado, tampoco');
bien(T.celdasConLista({}).length === 0, 'y sin editor, tampoco');
bien(T.hojaVisible(ventanaCon(editorCon({ sinHoja: true }))) === null,
     'la hoja visible se pide con cuidado');

// ── Un tope, para no llenar la pantalla de elementos ────────────────────
window.__maqMedidasAvisadas = false;
v = ventanaCon(editorCon({
    validaciones: [unaLista(0, 0, 19, 25)],       // 20x26 = 520 celdas
}));
celdas = T.celdasConLista(v);
bien(celdas.length === 400, 'hay un tope de pastillas a la vez: ' + celdas.length);
console.log();
