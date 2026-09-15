/* Escribir «@» en una celda ofrece a las personas con acceso: cuándo cuenta el
   «@», cómo se filtra lo escrito, cómo queda el texto al elegir, el flujo con
   teclado (↓ ↑ Enter Esc) sobre un editor de mentira, que salgan TODAS las
   personas (con barra de desplazamiento) y que el cuadro NUNCA se quede
   flotando: respuesta que llega tarde, celda cerrada por otro camino, rueda del
   ratón, y el keyup del propio Esc. */

let textoCelda = '', cursor = 0, abierto = false, cerrado = 0;
const escrito = [];
const cellEditor = {
    get isOpened() { return abierto; },
    getText: () => textoCelda,
    get cursorPos() { return cursor; }
};
const ws = {
    model: { selectionRange: { activeCell: { col: 2, row: 5 } } },
    setSelection: (rg) => escrito.push('selecciona ' + rg.c1 + ',' + rg.r1),
    setSelectionInfo: (que, valor) => escrito.push(que + '=' + valor)
};
function Range(c1, r1, c2, r2) { this.c1 = c1; this.r1 = r1; this.c2 = c2; this.r2 = r2; }
const editor = {
    wb: { cellEditor: cellEditor, getWorksheet: () => ws },
    asc_closeCellEditor: () => { cerrado++; abierto = false; },
    asc_getActiveCellCoord: () => ({ x: 154, y: 114, height: 19 })
};
const oyentes = {};
const elementos = [];
function nuevoElemento() {
    const hijos = [];
    return {
        style: { cssText: '' }, hijos: hijos, childNodes: hijos, className: '',
        scrollTop: 0, clientHeight: 260, offsetTop: 0, offsetHeight: 30,
        set innerHTML(v) { hijos.length = 0; }, get innerHTML() { return ''; },
        appendChild: (h) => { h.offsetTop = hijos.length * 30; hijos.push(h); },
        contains: () => false, parentNode: null, textContent: ''
    };
}
const cuerpo = nuevoElemento();
const ventana = {
    Asc: { editor: editor, Range: Range },
    SSE: { getController: () => ({ documentHolder: { cmpEl: [cuerpo] } }) },
    document: {
        body: cuerpo,
        createElement: () => { const e = nuevoElemento(); elementos.push(e); return e; },
        addEventListener: (tipo, fn) => { (oyentes[tipo] = oyentes[tipo] || []).push(fn); },
        querySelectorAll: () => []
    }
};
global.window = global;
global.document = { querySelectorAll: (s) => (s === 'iframe' ? [{ contentWindow: ventana }] : []) };
const relojReal = { poner: setInterval, quitar: clearInterval };
global.setInterval = () => 1;          // que editor-ventanas no se quede sondeando
const buzon = [];
window.MaquitaDiagnostico = { contar: (m, d) => buzon.push([m, d]) };
const gente = [
    { nombre: 'Ana Pérez Mora', motivo: 'Miembro' },
    { nombre: 'Luis Vega Ruiz', motivo: 'Tú' },
    { nombre: 'Rosa Chávez León', motivo: 'Compartido' },
    { nombre: 'Wilson Argüello', motivo: 'Dueño' }
];
// Una unidad de verdad tiene bastante más gente de la que cabe en el cuadro.
for (let i = 1; i <= 12; i++) gente.push({ nombre: 'Persona Número ' + i, motivo: 'En la unidad como editor' });
window.MaquitaProtegerPersonas = { deArchivo: () => Promise.resolve(gente) };

const B = process.env.MODULOS || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';
require(B + 'editor-ventanas.js');
require(B + 'editor-arroba-personas.js');
// El vigilante del cuadro sí necesita un reloj de verdad.
global.setInterval = relojReal.poner;
global.clearInterval = relojReal.quitar;

const A = window.MaquitaArrobaPersonas;
let rojo = 0;
const bien = (r, q) => { if (!r) rojo++; console.log((r ? 'OK  ' : 'MAL ') + q); };
const esperar = (ms) => new Promise((r) => setTimeout(r, ms || 0));
const keyup = () => oyentes.keyup[0]();
const keydown = (key) => {
    const e = { key: key, preventDefault: () => { e.parado = true; }, stopPropagation: () => {} };
    oyentes.keydown[0](e); return e;
};
const elCuadro = () => elementos.find((el) => (el.style.cssText || '').indexOf('overflow-y') !== -1);

console.log();
bien(A._estado.activo === true && !!oyentes.keyup && !!oyentes.keydown, 'se engancha al teclado de la ventana del editor');

// ── cuándo cuenta el «@» ──
let t = A.tokenDe('@', 1);
bien(t && t.desde === 0 && t.busca === '', 'un «@» solo, al principio: cuenta (y aún no filtra nada)');
t = A.tokenDe('Hola @Ro', 8);
bien(t && t.desde === 5 && t.busca === 'Ro', 'después de un espacio: cuenta, y lo escrito es lo que filtra');
bien(A.tokenDe('juan@maquita.org', 16) === null, 'un correo NO dispara nada («@» pegado a una palabra)');
bien(A.tokenDe('sin arroba', 10) === null, 'sin «@», nada');
bien(A.tokenDe('@Ro', 1) && A.tokenDe('@Ro', 1).busca === '', 'con el cursor justo tras el «@», la búsqueda está vacía');
bien(A.tokenDe('@' + 'x'.repeat(60), 61) === null, 'si lo escrito tras el «@» es larguísimo, se deja en paz');

// ── el filtro ──
bien(A.filtrar(gente, '').length === gente.length,
     'sin nada escrito salen TODAS (' + gente.length + '), no las primeras ocho');
let f = A.filtrar(gente, 'ro');
bien(f.length === 1 && f[0].nombre === 'Rosa Chávez León', '«ro» → Rosa (por el principio de una palabra)');
f = A.filtrar(gente, 'PEREZ');
bien(f.length === 1 && f[0].nombre === 'Ana Pérez Mora', 'sin tildes y sin distinguir mayúsculas: «PEREZ» → Ana Pérez Mora');
bien(A.filtrar(gente, 'argüello').length === 1, 'con tilde escrita también');
bien(A.filtrar(gente, 'zzz').length === 0, 'si no casa nadie, ninguna');

// ── cómo queda el texto ──
bien(A.componer('Hola @Ro', 5, 8, 'Rosa Chávez León') === 'Hola Rosa Chávez León', 'al elegir, «@Ro» se cambia por el nombre');
bien(A.componer('@Ro y algo', 0, 3, 'Rosa Chávez León') === 'Rosa Chávez León y algo', 'y lo que hubiera después se conserva');

async function main() {
    // ── se abre con todas y con barra de desplazamiento ──
    abierto = true; textoCelda = 'Hola @'; cursor = 6; keyup();
    await esperar();
    bien(A._estado.abierto === true && A._estado.opciones.length === gente.length,
         'al escribir «@» se abre el listado con todas las personas (' + A._estado.opciones.length + ')');
    const css = (elCuadro() || { style: {} }).style.cssText || '';
    bien(/overflow-y:\s*auto/.test(css) && /max-height:\s*\d+px/.test(css),
         'el cuadro lleva barra de desplazamiento y alto máximo: ' + (css.match(/max-height:[^;]*/) || [''])[0]);

    textoCelda = 'Hola @Ro'; cursor = 8; keyup();
    await esperar();
    bien(A._estado.opciones.length === 1 && A._estado.opciones[0].nombre === 'Rosa Chávez León',
         'al seguir escribiendo se filtra: queda Rosa');

    textoCelda = 'Hola @'; cursor = 6; keyup();
    await esperar();
    // ── teclado ──
    let e = keydown('ArrowDown');
    bien(A._estado.marcada === 1 && e.parado, '↓ baja de persona y la tecla no le llega al editor');
    keydown('ArrowUp');
    bien(A._estado.marcada === 0, '↑ sube');
    for (let i = 0; i < 10; i++) keydown('ArrowDown');
    bien(A._estado.marcada === 10 && elCuadro().scrollTop > 0,
         'bajando más allá de lo que cabe, el cuadro se desplaza solo (scrollTop ' + elCuadro().scrollTop + ')');
    for (let i = 0; i < 10; i++) keydown('ArrowUp');
    bien(A._estado.marcada === 0 && elCuadro().scrollTop === 0, 'y al volver arriba, otra vez al principio');

    escrito.length = 0;
    e = keydown('Enter');
    bien(e.parado && cerrado === 1, 'Enter elige: cierra el editor de celda sin guardar lo tecleado');
    bien(escrito.indexOf('selecciona 2,5') !== -1 && escrito.indexOf('value=Hola Ana Pérez Mora') !== -1,
         'y escribe el texto compuesto en la celda que se estaba editando: ' + escrito.join(' | '));
    bien(A._estado.abierto === false, 'el listado se cierra al elegir');
    bien(buzon.some((b) => b[0] === 'arroba personas' && b[1].nombre === 'Ana Pérez Mora'), 'lo cuenta en el buzón');

    // ── Esc: cierra y NO se reabre solo ──
    abierto = true; textoCelda = '@'; cursor = 1; keyup();
    await esperar();
    bien(A._estado.abierto === true, 'se vuelve a abrir con otro «@»');
    e = keydown('Escape');
    bien(A._estado.abierto === false && e.parado, 'Esc cierra el listado (y no cierra la celda)');
    keyup();                       // la tecla al soltarse no debe reabrirlo
    await esperar();
    bien(A._estado.abierto === false, 'tras Esc no se reabre solo mientras no se escriba otra cosa');
    textoCelda = '@L'; cursor = 2; keyup();
    await esperar();
    bien(A._estado.abierto === true, 'y en cuanto se sigue escribiendo, vuelve');

    // ── si se deja de escribir, se va ──
    abierto = false;
    A.revisar(ventana);
    bien(A._estado.abierto === false, 'si se deja de escribir en la celda, el listado desaparece');

    // ── una respuesta que llega TARDE no lo deja flotando ──
    A._olvidar();
    let soltar;
    window.MaquitaProtegerPersonas = { deArchivo: () => new Promise((r) => { soltar = () => r(gente); }) };
    abierto = true; textoCelda = '@'; cursor = 1; keyup();
    abierto = false;                       // la persona ya cerró la celda
    soltar();
    await esperar();
    bien(A._estado.abierto === false, 'si la respuesta llega cuando ya no se escribe, el cuadro NO se pinta');

    // ── el vigilante ──
    A._olvidar();
    window.MaquitaProtegerPersonas = { deArchivo: () => Promise.resolve(gente) };
    abierto = true; textoCelda = '@'; cursor = 1; keyup();
    await esperar();
    bien(A._estado.abierto === true, 'se abre de nuevo');
    abierto = false;                       // se cerró la celda sin tocar el teclado
    await esperar(600);
    bien(A._estado.abierto === false, 'el vigilante lo retira solo: nunca se queda flotando');

    // ── la rueda del ratón ──
    abierto = true; textoCelda = '@'; cursor = 1; keyup();
    await esperar();
    (oyentes.wheel || []).forEach((fn) => fn({ target: {}, preventDefault() {}, stopPropagation() {} }));
    bien(A._estado.abierto === false, 'al desplazar la hoja con la rueda, se cierra');

    // ── sin nadie con acceso ──
    A._olvidar();
    window.MaquitaProtegerPersonas = { deArchivo: () => Promise.resolve([]) };
    abierto = true; textoCelda = '@'; cursor = 1; keyup();
    await esperar();
    bien(A._estado.abierto === false, 'si no hay nadie con acceso, no se abre nada');

    A.cerrar();
    if (rojo) process.exitCode = 1;
}
main();
