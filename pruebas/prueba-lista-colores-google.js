/* Paleta ampliada de las listas con los colores de Google y «Personalizado» (14/10/2026).
   Se comprueba: los 10 tonos de siempre no se mueven; se añaden los de Google
   (#11734b, #b10202, #ffff00…) sin repetir; y los códigos que se escriben se normalizan. */
const MODULOS = process.env.MODULOS || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen';
global.window = global;
const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
const COLORES = [{ nombre: 'Sin color', color: '#e6e6e6' }, { nombre: 'Rojo claro', color: '#f4c7c3' }, { nombre: 'Amarillo', color: '#ffff00' }];
window.MaquitaListaPanel = { COLORES: COLORES };
global.document = { head: { appendChild() {} }, body: {}, createElement: () => ({}), addEventListener() {} };
global.MutationObserver = function () { this.observe = function () {}; };
require(MODULOS + '/editor-lista-colores-google.js');
const G = window.MaquitaListaColoresGoogle;
console.log();
bien(!!G && G.DE_GOOGLE.length === 27, 'el módulo trae 27 colores: 16 de opciones de lista de Google, 10 puros y el piel del POA');
bien(COLORES[0].color === '#e6e6e6' && COLORES[1].color === '#f4c7c3', 'los tonos de siempre siguen en su sitio (de ellos sale el reparto automático)');
const todos = COLORES.map(c => c.color);
bien(['#11734b', '#b10202', '#ffff00', '#fbe4d4', '#d4edbc', '#ffcfc9', '#ffe5a0'].every(c => todos.indexOf(c) !== -1), 'están el verde #11734b, el rojo #b10202, el amarillo #ffff00, el piel #fbe4d4 y los claros de Google');
bien(todos.filter(c => c === '#ffff00').length === 1, 'sin repetir un color que ya estaba');
bien(G.ampliar() === true && COLORES.length === todos.length, 'ampliar dos veces no duplica nada');
bien(G.normalizar('#11734B') === '#11734b' && G.normalizar('b10202') === '#b10202' && G.normalizar('#ff0') === '#ffff00', 'el código escrito se normaliza (#11734B, b10202, #ff0)');
bien(G.normalizar('verde') === '' && G.normalizar('#12345') === '', 'y uno que no es un color se rechaza');
