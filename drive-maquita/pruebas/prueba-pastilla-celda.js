/* La celda con lista desplegable tiene que verse como en el vídeo de Google:
   una píldora plomo MÁS PEQUEÑA que la celda, con el triangulito dentro y
   pegado a la derecha. Se comprueba la forma y que no estorbe al editor. */

let repasar = null;
let alCambiarSeleccion = null;
const creados = [];
const abierto = [];
let valoresDeLaCelda = [];

let hayLista = true;
let coord = { x: 100, y: 60, w: 90, h: 20 };

function Elemento() {
    this.style = {};
    this.className = '';
    this.parentNode = null;
    this.hijos = [];
    this.appendChild = function (h) { this.hijos.push(h); h.parentNode = this; };
    creados.push(this);
}

const tableroEl = {
    appendChild: function (hijo) { hijo.parentNode = tableroEl; },
    removeChild: function (hijo) { hijo.parentNode = null; }
};

const TIPOS = { List: 'lista', Custom: 'personalizada' };
let tipoDeValidacion = TIPOS.List;

const ventanaEditor = {
    document: {
        body: { dispatchEvent: (e) => { abierto.push('tecla:' + e.opciones.key); return true; } },
        querySelectorAll: () => [],
        createElement: () => new Elemento()
    },
    getComputedStyle: () => ({ backgroundColor: 'rgb(255, 255, 255)' }),
    matchMedia: () => ({ matches: false }),
    Asc: {
        c_oAscEDataValidationType: TIPOS,
        editor: {
            asc_registerCallback: function (nombre, fn) {
                if (nombre === 'asc_onSelectionChanged') alCambiarSeleccion = fn;
            },
            asc_getCellInfo: function () {
                return {
                    asc_getDataValidation: function () {
                        return hayLista ? { asc_getType: () => tipoDeValidacion } : null;
                    }
                };
            },
            asc_getActiveCellCoord: function () {
                return {
                    asc_getX: () => coord.x, asc_getY: () => coord.y,
                    asc_getWidth: () => coord.w, asc_getHeight: () => coord.h
                };
            }
        }
    },
    KeyboardEvent: function (tipo, opciones) {
        this.tipo = tipo; this.opciones = opciones; abierto.push('atajo');
    },
    SSE: {
        getController: () => ({
            documentHolder: { cmpEl: [tableroEl] },
            onEntriesListMenu: function (validation, textos) {
                abierto.push('lista:' + validation + ':' + (textos || []).join(','));
            }
        })
    }
};

global.window = global;
global.document = {
    body: { appendChild() { }, removeChild() { } },
    head: { appendChild() { } },
    createElement: () => ({ style: {}, setAttribute() { }, appendChild() { },
                            querySelector: () => null, querySelectorAll: () => [] }),
    querySelectorAll: (s) => (s === 'iframe' ? [{ contentWindow: ventanaEditor }] : []),
    addEventListener() { }
};
let repasosDelReloj = 0;
global.setInterval = (fn, ms) => {
    if (ms === 1000) { repasar = fn; return 1; }      // el de editor-ventanas
    repasosDelReloj++;
    return 2;
};
global.console = console;

global.window.MaquitaListas = { leerActual: () => valoresDeLaCelda };
const B = process.env.MAQ_JS
    || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';
require(B + 'editor-ventanas.js');
require(B + 'editor-pastilla-celda.js');

const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
console.log('\n[Drive Maquita] la pastilla dentro de la celda\n');

repasar();

// La capa es la primera que se creó; la segunda es el triangulito.
const capa = creados[0];
const flecha = capa.hijos[0];

// ── La forma, medida contra el video de Google ───────────────────────────
bien(capa.className === 'maq-pastilla-celda', 'se pone la capa');
bien(capa.parentNode === tableroEl,
     'y cuelga de donde el editor cuelga lo suyo: mismas coordenadas');
bien(capa.style.background === '#e0e0e0', 'es plomo, para que se vea');
bien(capa.style.mixBlendMode === 'multiply',
     'en multiply: el texto de la celda se sigue leyendo debajo');

/* La celda mide 90x20 en 100,60. La pastilla NO la llena: deja aire a los
   lados (4) y arriba y abajo (3), como en el video. */
bien(capa.style.width === '82px', 'no llena la celda a lo ancho: ' + capa.style.width);
bien(capa.style.height === '14px', 'ni a lo alto: ' + capa.style.height);
bien(capa.style.left === '104px' && capa.style.top === '63px',
     'y queda centrada en la celda: ' + capa.style.left + ',' + capa.style.top);
bien(capa.style.borderRadius === '7px',
     'el redondeo es la MITAD del alto: es una pildora, no una esquina suave');

// ── El triangulito ───────────────────────────────────────────────────────
/* Medido contra el video del 02/09/2026: en Google es un triangulito PEQUEÑO,
   gris y CENTRADO dentro de la pastilla. El nuestro salia grande y asomando por
   ARRIBA, porque tres margenes se pisaban entre si. */
const punta = flecha.hijos[0];
bien(!!flecha && !!punta, 'lleva el triangulito, dentro de su cuadradito');
bien(flecha.style.right === '4px', 'pegado a la derecha, DENTRO de la pastilla');
bien(flecha.style.width === '14px' && flecha.style.height === '14px',
     'el cuadradito para pulsarlo mide 14x14');
bien(flecha.style.marginTop === '-7px' && flecha.style.top === '50%',
     'y queda CENTRADO en la pastilla: top 50% menos la mitad de su alto');
bien(/solid #5f6368/.test(punta.style.borderTop || ''),
     'el triangulito es gris, como el de Google: ' + punta.style.borderTop);
bien(punta.style.borderLeft === '4px solid transparent'
     && punta.style.borderRight === '4px solid transparent',
     'dibujado con bordes, que es como se hace un triangulo: 8 de ancho por 4 de alto');
bien(punta.style.left === '3px' && punta.style.top === '5px',
     'y centrado dentro del cuadradito: ' + punta.style.left + ',' + punta.style.top);
/* La comprobacion que faltaba y por la que se colo el fallo: el triangulito NO
   puede salirse de la pastilla. La pastilla mide 14 de alto; el cuadradito
   tambien, y va centrado, asi que ni asoma por arriba ni por abajo. */
const altoPastilla = parseInt(capa.style.height, 10);
const arribaDelTriangulo = altoPastilla / 2 + parseInt(flecha.style.marginTop, 10);
bien(arribaDelTriangulo >= 0
     && arribaDelTriangulo + parseInt(flecha.style.height, 10) <= altoPastilla + 1,
     'y NO se sale de la pastilla: empieza en ' + arribaDelTriangulo
     + ' y la pastilla mide ' + altoPastilla);

// ── Y sobre todo: el triangulito ABRE LA LISTA ──────────────────────────
valoresDeLaCelda = ['Opción 1', 'Opción 2'];
abierto.length = 0;
flecha.onclick({ stopPropagation() { } });
bien(abierto[0] === 'lista:true:Opción 1,Opción 2',
     'al pulsarlo se abre la lista con los valores de la celda: ' + abierto[0]);
bien(flecha.style.pointerEvents === 'auto',
     'y se puede pulsar, aunque el resto de la capa no');
bien(flecha.style.cursor === 'pointer', 'con la manita, para que se vea que hace algo');
bien(punta.style.pointerEvents === 'none',
     'el triangulo de dentro no roba el clic: lo recoge su cuadradito');

// Si la lista sale de un intervalo y no de valores escritos, lo abre el editor.
valoresDeLaCelda = [];
abierto.length = 0;
flecha.onclick({ stopPropagation() { } });
bien(abierto[0] === 'atajo' && abierto[1] === 'tecla:ArrowDown',
     'y si los valores salen de un intervalo, se usa el atajo del editor');

// ── Que no estorbe al editor ─────────────────────────────────────────────
bien(capa.style.pointerEvents === 'none',
     'no se puede pulsar: los clics siguen siendo del editor');
bien(parseInt(capa.style.zIndex, 10) > 100,
     'va por encima del lienzo: ' + capa.style.zIndex);
bien(capa.style.clipPath === undefined,
     'sin el recorte de antes, que borraba lo pintado y no se veia nada');

// ── Sigue a la celda ─────────────────────────────────────────────────────
const cuantas = creados.length;
coord = { x: 300, y: 120, w: 60, h: 18 };
alCambiarSeleccion();
bien(capa.style.left === '304px' && capa.style.top === '123px',
     'al cambiar de celda, la pastilla se mueve con ella');
bien(creados.length === cuantas, 'sin crear una capa nueva cada vez');

capa.style.left = 'TOCADO';
alCambiarSeleccion();
bien(capa.style.left === 'TOCADO',
     'si la celda no se movio, no se repinta (el repaso es suave)');

// ── En celdas estrechas no se deforma ────────────────────────────────────
coord = { x: 10, y: 10, w: 12, h: 20 };
alCambiarSeleccion();
bien(parseInt(capa.style.width, 10) >= 24,
     'en una celda estrecha, la pastilla no se encoge hasta tapar el triangulito: '
     + capa.style.width);

// ── Donde NO toca ────────────────────────────────────────────────────────
hayLista = false;
coord = { x: 10, y: 10, w: 50, h: 20 };
alCambiarSeleccion();
bien(capa.parentNode === null, 'en una celda sin lista, la pastilla se quita');

hayLista = true;
tipoDeValidacion = TIPOS.Custom;
alCambiarSeleccion();
bien(capa.parentNode === null,
     'y con otra validacion que no sea lista, tampoco se pinta');

tipoDeValidacion = TIPOS.List;
coord = { x: 10, y: -5, w: 50, h: 20 };
alCambiarSeleccion();
bien(capa.parentNode === null,
     'si la celda quedo fuera de lo que se ve, no se pinta encima de nada');

bien(repasosDelReloj === 1, 'hay un repaso suave para el scroll y el zoom');
console.log();
