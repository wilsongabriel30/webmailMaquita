/* Selector de color personalizado (14/10/2026): las conversiones entre hexadecimal, R V A y
   tono/saturación/brillo, que son las que mueven el cuadro y los campos entre sí. */
const MODULOS = process.env.MODULOS || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen';
global.window = global;
global.document = { head: null };
const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
require(MODULOS + '/editor-selector-color.js');
const S = window.MaquitaSelectorColor;
console.log();
bien(!!S && typeof S.abrir === 'function' && typeof S.cerrar === 'function', 'el módulo publica MaquitaSelectorColor.abrir / cerrar');
bien(JSON.stringify(S._hexARgb('#11734b')) === '[17,115,75]' && JSON.stringify(S._hexARgb('B10202')) === '[177,2,2]', 'hexadecimal → R, V, A (#11734b = 17, 115, 75)');
bien(S._hexARgb('#12') === null && S._hexARgb('verde') === null, 'un código mal escrito no es un color');
bien(S._rgbAHex(251, 228, 212) === '#fbe4d4' && S._rgbAHex(300, -4, 0) === '#ff0000', 'R, V, A → hexadecimal (y fuera de 0-255 se recorta)');
const ida = ['#11734b', '#b10202', '#ffff00', '#fbe4d4', '#000000', '#ffffff', '#4a86e8'].every(function (h) {
    const rgb = S._hexARgb(h), hsv = S._rgbAHsv(rgb[0], rgb[1], rgb[2]), vuelta = S._hsvARgb(hsv[0], hsv[1], hsv[2]);
    return S._rgbAHex(vuelta[0], vuelta[1], vuelta[2]) === h;
});
bien(ida, 'ida y vuelta por el cuadro (tono, saturación, brillo) devuelve el mismo color en 7 casos');
const am = S._rgbAHsv(255, 255, 0);
bien(Math.round(am[0]) === 60 && am[1] === 1 && am[2] === 1, 'el amarillo puro está en el tono 60°, arriba a la derecha del cuadro');
