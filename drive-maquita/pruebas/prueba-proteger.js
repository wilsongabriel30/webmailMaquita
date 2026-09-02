/* Simulacro del editor: se comprueba QUÉ se le pide al proteger una hoja o un
   intervalo —el rango, los permisos de cada persona, el desbloqueo de las
   excepciones— y que lo que no debe pasar, no pasa. */

const recibido = {
    anadido: null, cambiado: null, borrados: null,
    hojaProps: null, desbloqueadas: [], celdaBuscada: [], hojaMostrada: null
};

const TIPOS = { edit: 'editar', view: 'ver', notView: 'ni-ve' };

// ── Las piezas del editor que se usan ────────────────────────────────────
function RangoProtegido() { this.usuarios = []; }
RangoProtegido.prototype.asc_setName = function (v) { this.nombre = v; };
RangoProtegido.prototype.asc_getName = function () { return this.nombre; };
RangoProtegido.prototype.asc_setRef = function (v) { this.ref = v; };
RangoProtegido.prototype.asc_getRef = function () { return this.ref; };
RangoProtegido.prototype.asc_setType = function (v) { this.tipo = v; };
RangoProtegido.prototype.asc_getType = function () { return this.tipo; };
RangoProtegido.prototype.asc_setUsers = function (v) { this.usuarios = v; };
RangoProtegido.prototype.asc_getUsers = function () { return this.usuarios; };

function Persona() { }
Persona.prototype.asc_setId = function (v) { this.id = v; };
Persona.prototype.asc_getId = function () { return this.id; };
Persona.prototype.asc_setName = function (v) { this.nombre = v; };
Persona.prototype.asc_getName = function () { return this.nombre; };
Persona.prototype.asc_setType = function (v) { this.tipo = v; };
Persona.prototype.asc_getType = function () { return this.tipo; };

// Las propiedades de protección de hoja: el editor las presta y las recoge.
const propsDeHoja = { asc_setSheet: function (v) { this.valor = v; } };

let yaProtegidos = [];
let hojaCerrada = false;
let seleccionActual = "'Ejec. Tec. 2026'!B2:D20";

const ventanaEditor = {
    document: { body: {}, querySelectorAll: () => [] },
    Asc: {
        c_oSerUserProtectedRangeType: TIPOS,
        referenceType: { A: 'absoluta' },
        CUserProtectedRange: RangoProtegido,
        CUserProtectedRangeUserInfo: Persona,
        editor: {
            asc_getActiveRangeStr: () => seleccionActual,
            asc_addUserProtectedRange: (r) => { recibido.anadido = r; },
            asc_changeUserProtectedRange: (viejo, nuevo) => {
                recibido.cambiado = { viejo: viejo, nuevo: nuevo };
            },
            asc_deleteUserProtectedRange: (lista) => { recibido.borrados = lista; },
            asc_getUserProtectedRanges: () => yaProtegidos,
            asc_getProtectedSheet: () => propsDeHoja,
            asc_setProtectedSheet: (p) => { recibido.hojaProps = p; },
            asc_isProtectedSheet: () => hojaCerrada,
            asc_findCell: (r) => { recibido.celdaBuscada.push(r); },
            asc_setCellLocked: (v) => {
                if (v === false) {
                    recibido.desbloqueadas.push(
                        recibido.celdaBuscada[recibido.celdaBuscada.length - 1]);
                }
            },
            asc_showWorksheet: (i) => { recibido.hojaMostrada = i; },
            asc_getWorksheetsCount: () => 3,
            asc_getActiveWorksheetIndex: () => 1,
            asc_isWorksheetHidden: (i) => i === 2,
            asc_getWorksheetName: (i) => ['Buscador', 'Ejec. Tec. 2026', 'Oculta'][i]
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

require('/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/editor-proteger-aplicar.js');

const P = window.MaquitaProteger;
const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
console.log('\n[Drive Maquita] proteger hojas e intervalos\n');

// ── Un intervalo restringido a dos personas ──────────────────────────────
let r = P.intervalo(ventanaEditor, {
    nombre: 'Cifras del cierre',
    rango: "'Ejec. Tec. 2026'!J45:J95",
    personas: [
        { id: '17', nombre: 'Wilson Arguello', permiso: 'editar' },
        { id: '42', nombre: 'Karen Armas', permiso: 'ver' }
    ]
});
bien(r.ok === true, 'el intervalo se protege');
bien(recibido.anadido.nombre === 'Cifras del cierre', 'lleva la descripcion escrita');
bien(recibido.anadido.ref === "'Ejec. Tec. 2026'!J45:J95",
     'el rango va con el nombre de la hoja: ' + recibido.anadido.ref);
bien(recibido.anadido.tipo === TIPOS.notView,
     'los demas no pueden tocarlo (restringido)');
bien(recibido.anadido.usuarios.length === 2, 'viajan las dos personas');
bien(recibido.anadido.usuarios[0].id === '17' && recibido.anadido.usuarios[0].tipo === TIPOS.edit,
     'la primera puede editar, con SU identificador');
bien(recibido.anadido.usuarios[1].tipo === TIPOS.view, 'la segunda solo mira');

// ── «Mostrar una advertencia»: se avisa, pero se deja editar ─────────────
recibido.anadido = null;
P.intervalo(ventanaEditor, { rango: 'A1:B10', soloAvisar: true, personas: [] });
bien(recibido.anadido.tipo === TIPOS.edit, 'con «solo avisar», los demas pueden editar');
bien(recibido.anadido.nombre === 'Protegido A1:B10',
     'sin descripcion, se pone una: ' + recibido.anadido.nombre);

// ── Lo que NO debe pasar ─────────────────────────────────────────────────
recibido.anadido = null;
r = P.intervalo(ventanaEditor, { rango: '  ', personas: [] });
bien(r.ok === false && recibido.anadido === null, 'sin intervalo no se protege nada');
bien(/Falta el intervalo/.test(r.problema), 'y se dice por que');

// ── Cambiar un intervalo ya protegido ────────────────────────────────────
const original = new RangoProtegido();
P.intervalo(ventanaEditor, {
    rango: 'C1:C9', personas: [], anterior: original
});
bien(recibido.cambiado && recibido.cambiado.viejo === original,
     'al cambiar permisos se REEMPLAZA el que habia, no se anade otro');

// ── La hoja entera, con excepciones ──────────────────────────────────────
r = P.hoja(ventanaEditor, { hoja: 0, excepto: ["'Buscador'!A2:B95", '  ', 'D1:D4'] });
bien(r.ok === true, 'la hoja se protege');
bien(recibido.hojaMostrada === 0, 'se protege la hoja elegida en el desplegable');
bien(recibido.desbloqueadas.length === 2,
     'las excepciones se desbloquean, y los huecos vacios se ignoran');
bien(recibido.desbloqueadas[0] === "'Buscador'!A2:B95", 'la primera excepcion es la escrita');
bien(recibido.hojaProps === propsDeHoja && propsDeHoja.valor === true,
     'las propiedades se piden al editor y se le devuelven cerradas');
bien(recibido.celdaBuscada[recibido.celdaBuscada.length - 1] === seleccionActual,
     'al terminar, la seleccion vuelve donde estaba');

// ── Desproteger la hoja ──────────────────────────────────────────────────
propsDeHoja.valor = 'sin tocar';
bien(P.quitarHoja(ventanaEditor) === true && propsDeHoja.valor === undefined,
     'desproteger es dejar la hoja SIN valor, como hace el editor');

// ── Leer lo ya protegido ─────────────────────────────────────────────────
const guardado = new RangoProtegido();
guardado.asc_setName('Cierre');
guardado.asc_setRef('J45:J95');
guardado.asc_setType(TIPOS.notView);
const uno = new Persona();
uno.asc_setId('17'); uno.asc_setName('Wilson'); uno.asc_setType(TIPOS.edit);
guardado.asc_setUsers([uno]);
yaProtegidos = [guardado];

const leidos = P.protegidos(ventanaEditor);
bien(leidos.length === 1 && leidos[0].rango === 'J45:J95', 'se leen los intervalos protegidos');
bien(leidos[0].soloAvisar === false, 'se distingue restringido de solo avisar');
bien(leidos[0].personas[0].permiso === 'editar', 'y el permiso de cada persona');

// ── Quitar la proteccion de un intervalo ─────────────────────────────────
P.quitarIntervalo(ventanaEditor, leidos[0]);
bien(Array.isArray(recibido.borrados) && recibido.borrados[0] === guardado,
     'al borrar se le pasa una LISTA, que es lo que el editor espera');

// ── Las hojas para el desplegable ────────────────────────────────────────
const hojas = P.hojas(ventanaEditor);
bien(hojas.length === 2, 'las hojas ocultas no salen en el desplegable');
bien(hojas[1].nombre === 'Ejec. Tec. 2026' && hojas[1].activa === true,
     'la hoja en la que se esta viene marcada');

// ── Detalles ─────────────────────────────────────────────────────────────
bien(P.soloCeldas("'Ejec. Tec. 2026'!J45") === 'J45', 'se sabe quitar el nombre de la hoja');
bien(P.nombreDeLaHoja(ventanaEditor) === 'Ejec. Tec. 2026', 'se sabe en que hoja se esta');
console.log();
