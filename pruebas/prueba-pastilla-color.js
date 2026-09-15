/* La pastilla DE COLOR dentro de la celda, como en Google: cuando el valor de
   la celda tiene color en las reglas del archivo, se tapa la celda con una capa
   blanca y encima va la pastilla del color con el texto, con la fuente de la
   celda. Sin color, no se hace cargo y se esconde. Editando, se esconde. */

function Elemento(tag) {
    this.tag = tag; this.style = {}; this.children = []; this.textContent = '';
    this.className = '';
}
Elemento.prototype.appendChild = function (h) { this.children.push(h); return h; };

let textoCelda = 'Opción 2';
let colores = { 'Opción 2': '#c6dafc' };
const tablero = new Elemento('tablero');
const registrados = {};

const xfs = {
    asc_getFontName: () => 'Calibri', asc_getFontSize: () => 11,
    asc_getFontColor: () => ({ get_r: () => 32, get_g: () => 33, get_b: () => 36 }),
    asc_getFontBold: () => true, asc_getFontItalic: () => false,
    asc_getHorAlign: () => 'center'
};
const ventanaEditor = {
    document: { createElement: (t) => new Elemento(t), body: {}, querySelectorAll: () => [] },
    Asc: {
        c_oAscCellEditorState: { editStart: 1, editEnd: 0 },
        editor: {
            asc_getCellInfo: () => ({ asc_getText: () => textoCelda, asc_getXfs: () => xfs }),
            asc_getZoom: () => 1.5,
            asc_registerCallback: (n, fn) => { registrados[n] = fn; }
        }
    }
};
global.window = global;
global.document = { querySelectorAll: (s) => (s === 'iframe' ? [{ contentWindow: ventanaEditor }] : []) };
global.setInterval = () => 1;
global.console = console;
window.MaquitaColoresCF = { coloresPorValor: () => colores };

require('/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/editor-ventanas.js');
require('/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/editor-contraste.js');
require('/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/editor-pastilla-color.js');

const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
console.log();
const P = window.MaquitaPastillaColor;
const sitio = { x: 100, y: 50, ancho: 90, alto: 21 };
let abierta = 0;

bien(P.pintar(ventanaEditor, sitio, tablero, () => abierta++) === true,
     'con un valor que tiene color, la capa se hace cargo de la celda');
const capa = tablero.children[0];
bien(capa && capa.className === 'maq-pastilla-color' && capa.style.background === '#ffffff',
     'la capa tapa la celda en blanco (el color ya no llena la celda)');
bien(capa.style.left === '99px' && capa.style.top === '49px' && capa.style.width === '91px' && capa.style.height === '22px',
     'tapa la celda COMPLETA más la cuadrícula compartida, sin dejar filo de color: ' + capa.style.left + ',' + capa.style.top + ',' + capa.style.width + 'x' + capa.style.height);
bien(/inset 0 0 0 1px #cacaca/.test(capa.style.boxShadow), 'y dibuja ella la cuadrícula por los cuatro lados, con el gris exacto del editor');
const pastilla = capa.children[0];
bien(pastilla.style.background === '#c6dafc' && pastilla.style.borderRadius === '7px',
     'la pastilla va del color del valor y redondeada a la mitad del alto');
const texto = pastilla.children[0];
bien(texto.textContent === 'Opción 2', 'con el texto de la celda encima');
bien(/bold 22px "Calibri"/.test(texto.style.font) && texto.style.color === '#202124'
     && texto.style.textAlign === 'center',
     'con la fuente de la celda, en píxeles y con el zoom: ' + texto.style.font);
const flecha = pastilla.children[1];
flecha.onclick({ stopPropagation() { } });
bien(abierta === 1, 'la flechita abre la lista');

// Sin repintar si nada cambió
const antes = tablero.children.length;
P.pintar(ventanaEditor, sitio, tablero, () => { });
bien(tablero.children.length === antes, 'no crea otra capa si nada cambió');

// Valor sin color → no se hace cargo y se esconde
textoCelda = 'Otro';
bien(P.pintar(ventanaEditor, sitio, tablero, () => { }) === false && capa.style.display === 'none',
     'con un valor SIN color no se hace cargo (queda la pastilla gris) y se esconde');

// Editando → se esconde aunque haya color
textoCelda = 'Opción 2';
registrados['asc_onEditCell'](1);
bien(P.pintar(ventanaEditor, sitio, tablero, () => { }) === false, 'mientras se edita la celda no tapa nada');
registrados['asc_onEditCell'](0);
bien(P.pintar(ventanaEditor, sitio, tablero, () => { }) === true && capa.style.display === '',
     'al terminar de editar vuelve a pintarse');

// Las DEMÁS celdas a la vista con valor de color: una capa por celda
const tablero2 = new Elemento('tablero');
const sitios = [
    { x: 10, y: 10, ancho: 80, alto: 20, col: 1, fila: 3, valor: 'Opción 1', color: '#e06666' },
    { x: 10, y: 30, ancho: 80, alto: 20, col: 1, fila: 4, valor: '', color: '' },          // vacía: gris
    { x: 10, y: 50, ancho: 80, alto: 20, col: 1, fila: 5, valor: 'Opción 2', color: '#6fa8dc',
      fuente: { nombre: 'Calibri', puntos: 12, color: '#111111', negrita: false, cursiva: true, alinear: 'right' } }
];
bien(P.pintarOtras(ventanaEditor, sitios, tablero2, () => { }) === 2, 'pinta una pastilla por cada celda a la vista con valor de color (2 de 3)');
bien(tablero2.children.length === 2 && tablero2.children[1].children[0].style.background === '#6fa8dc',
     'cada una con su color');
bien(tablero2.children[0].style.left === '9px' && tablero2.children[0].style.width === '81px',
     'y SIN margen alrededor: tapan la celda entera y su cuadrícula (nada de marcos de color)');
bien(/italic 24px "Calibri"/.test(tablero2.children[1].children[0].children[0].style.font),
     'y con la fuente de su celda: ' + tablero2.children[1].children[0].children[0].style.font);
P.pintarOtras(ventanaEditor, sitios.slice(0, 1), tablero2, () => { });
bien(tablero2.children.length === 2 && tablero2.children[1].style.display === 'none',
     'si una celda deja de verse, su capa se esconde y se reaprovecha');

// En una columna estrecha el texto se encoge hasta caber, no se recorta.
// (Va después de las «otras»: se reaprovecha la capa 0, que vive en tablero2.)
let tamActual = 22;
Object.defineProperty(Elemento.prototype, 'scrollWidth', { get() { return this.tag === 'span' ? Math.round(parseInt(this.style.fontSize || tamActual, 10) * 3.2) : 0; }, configurable: true });
Object.defineProperty(Elemento.prototype, 'clientWidth', { get() { return this.tag === 'span' ? 40 : 0; }, configurable: true });
P.pintarOtras(ventanaEditor, [{ x: 0, y: 0, ancho: 64, alto: 17, col: 0, fila: 0, valor: 'Opción 2', color: '#c6dafc' }], tablero2, () => { });
const spanEstrecho = tablero2.children[0].children[0].children[0];
bien(parseInt(spanEstrecho.style.fontSize, 10) < 22 && parseInt(spanEstrecho.style.fontSize, 10) >= 8,
     'en 64 px el texto se encoge hasta caber (' + spanEstrecho.style.fontSize + '), entre 8 px y el tamaño de la celda');
delete Elemento.prototype.scrollWidth; delete Elemento.prototype.clientWidth;

// Sobre un color intenso, el texto va en blanco; sobre uno claro, el de la celda
P.pintarOtras(ventanaEditor, [{ x: 0, y: 0, ancho: 90, alto: 21, col: 0, fila: 0, valor: 'Urgente', color: '#d32f2f' }], tablero2, () => { });
bien(tablero2.children[0].children[0].children[0].style.color === '#ffffff', 'sobre rojo intenso el texto va en blanco');
P.pintarOtras(ventanaEditor, [{ x: 0, y: 0, ancho: 90, alto: 21, col: 0, fila: 0, valor: 'Suave', color: '#fce8b2' }], tablero2, () => { });
bien(tablero2.children[0].children[0].children[0].style.color === '#000000', 'sobre amarillo claro se conserva el color de la celda');
bien(window.MaquitaContraste.textoSobre('#1565c0') === '#ffffff' && window.MaquitaContraste.textoSobre('#c6dafc') === '#202124',
     'el contraste decide por luminancia (WCAG): azul intenso → blanco, azul claro → oscuro');

// Sin el módulo de colores → nunca revienta
delete window.MaquitaColoresCF;
bien(P.pintar(ventanaEditor, sitio, tablero, () => { }) === false, 'sin el módulo de colores no se hace cargo, y no revienta');
console.log();
