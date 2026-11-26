/* Colores de una lista «de un intervalo» desde el panel (14/10/2026, POA Social: ✔ / X / ⚠).
   Se simulan el editor (reglas, validación con varios rangos) y las filas del panel, y se
   comprueba: una fila por valor del intervalo, con el color que ya tenía y sin poder
   escribir ni borrar; «Aplicar al intervalo» con TODO el rango; al pulsar «Hecho» se cambia
   la regla que existe (sin duplicarla), se crea la que falta sobre todo el rango —con comas,
   que es como la quiere asc_setLocation— y «Sin color» quita la suya; si se cambió el
   intervalo, se deja al camino de siempre. */

const MODULOS = process.env.MODULOS || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen';
global.window = global;
const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);

// ── El editor, simulado ──
const llamadas = [];
function Regla(id, valor, color) { this.id = id; this.valor = valor; this.color = color; this.loc = 'true,=$AK$8:$AV$15;$AK$19:$AV$23'; }
Regla.prototype.asc_getId = function () { return this.id; };
Regla.prototype.asc_getType = function () { return 2; };
Regla.prototype.asc_getLocation = function () { return this.loc; };
Regla.prototype.asc_getValue1 = function () { return '="' + this.valor + '"'; };
Regla.prototype.asc_setDxf = function (f) { this.color = f.color; this.letra = f.letra || ''; };
Regla.prototype.asc_setType = function () {}; Regla.prototype.asc_setOperator = function () {};
Regla.prototype.asc_setValue1 = function (v) { this.valor = v; };
Regla.prototype.asc_setPriority = function (p) { this.prioridad = p; };
Regla.prototype.asc_setLocation = function (l) { this.loc = l; };
const reglas = [new Regla('7', '✔', '#d4edbc'), new Regla('9', 'X', '#ffcfc9')];
function Xfs() {} Xfs.prototype.asc_setFillColor = function (c) { this.color = c.hex; };
Xfs.prototype.asc_setFontColor = function (c) { this.letra = c.hex; };
function CColor() {} CColor.prototype.put_type = function () {};
CColor.prototype.put_r = function (r) { this.r = r; }; CColor.prototype.put_g = function (g) { this.g = g; };
CColor.prototype.put_b = function (b) { this.b = b; this.hex = '#' + [this.r, this.g, b].map(n => n.toString(16).padStart(2, '0')).join(''); };
const ventana = {
    Asc: {
        c_oAscCFType: { cellIs: 2 }, c_oAscCFOperator: { equal: 3 }, c_oAscColor: { COLOR_TYPE_SRGB: 1 },
        asc_CellXfs: Xfs, asc_CColor: CColor,
        asc_CConditionalFormattingRule: function () { Regla.call(this, null, '', ''); this.nueva = true; },
        editor: {
            asc_getCellInfo: () => ({ asc_getDataValidation: () => ({ ranges: [{ r1: 7, c1: 36, r2: 14, c2: 47 }, { r1: 18, c1: 36, r2: 22, c2: 47 }] }) }),
            asc_setCF: (puestas, borradas) => { llamadas.push([puestas.map(r => [r.id, r.valor, r.color, r.loc, !!r.nueva]), borradas]); }
        }
    }
};
ventana.Asc.asc_CConditionalFormattingRule.prototype = Object.create(Regla.prototype);
window.MaquitaColoresCF = {
    reglasPuestas: () => reglas,
    coloresPorValor: () => { const m = {}; reglas.forEach(r => { m[r.valor] = r.color; }); return m; },
    _valorDe: (r) => String(r.asc_getValue1()).replace(/^=/, '').replace(/^"|"$/g, '')
};
window.MaquitaValoresIntervalo = { valoresDe: () => ['✔', 'X', '⚠'] };

// ── Las filas del panel, simuladas ──
function el(clase) {
    return { className: clase, style: {}, dataset: {}, value: '', readOnly: false, hidden: false, title: '',
             hijos: [], querySelector(s) { return this.hijos.find(h => '.' + h.className === s) || null; } };
}
const filas = { hidden: true, lista: [],
    querySelectorAll() { return this.lista.slice(); }, appendChild(f) { this.lista.push(f); f.remove = () => { this.lista.splice(this.lista.indexOf(f), 1); }; } };
function nuevaFila(valor, color) {
    const f = el('maq-ld-fila');
    const v = el('maq-ld-valor'); v.value = valor;
    const c = el('maq-ld-color'); c.dataset.color = color;
    f.hijos = [el('maq-ld-asa'), c, v, el('maq-ld-papelera')];
    return f;
}
const ctx = { selector: { value: 'lista-rango' }, filas: filas, nuevaFila: nuevaFila, ventana: ventana,
              origen: 'Hoja1!$B$2:$B$4', campoUno: { value: 'Hoja1!$B$2:$B$4', addEventListener() {} },
              campoRango: { value: 'Social!AM9' }, botonAnadir: { hidden: false }, donde: 'Social!AM9' };

require(MODULOS + '/editor-lista-panel-intervalo.js');
const I = window.MaquitaPanelIntervalo;
console.log();
bien(I && I.CRITERIO === 'lista-rango', 'el módulo publica MaquitaPanelIntervalo para las listas de intervalo');
bien(I._letras(36) === 'AK' && I._letras(0) === 'A' && I._letras(25) === 'Z' && I._letras(26) === 'AA', 'letras de columna (36 → AK)');

bien(I.alAbrir(ctx) === true, 'al abrir el panel sobre una lista de intervalo, se hace cargo');
const vistas = filas.lista.map(f => f.querySelector('.maq-ld-valor').value + ':' + f.querySelector('.maq-ld-color').dataset.color);
bien(vistas.join(' ') === '✔:#d4edbc X:#ffcfc9 ⚠:#e6e6e6', 'una fila por valor del intervalo, con el color que ya tenía (⚠ sin color): ' + vistas.join(' '));
bien(filas.lista.every(f => f.querySelector('.maq-ld-valor').readOnly), 'los valores no se escriben: salen del intervalo');
bien(filas.lista.every(f => f.querySelector('.maq-ld-papelera').style.visibility === 'hidden' && f.querySelector('.maq-ld-asa').style.visibility === 'hidden'), 'ni se borran ni se mueven');
bien(filas.hidden === false && ctx.botonAnadir.hidden === true, 'las filas se ven y «Añade otro elemento» no');
bien(ctx.campoRango.value === 'Social!AK8:AV15,AK19:AV23', '«Aplicar al intervalo» muestra TODO el rango de la lista, como Google: ' + ctx.campoRango.value);

// ✔ → azul, X → sin color, ⚠ → amarillo
filas.lista[0].querySelector('.maq-ld-color').dataset.color = '#c6dafc';
filas.lista[1].querySelector('.maq-ld-color').dataset.color = '#e6e6e6';
filas.lista[2].querySelector('.maq-ld-color').dataset.color = '#fce8b2';
const r = I.alHecho(ctx, { uno: 'Hoja1!$B$2:$B$4', rango: ctx.campoRango.value });
bien(r && r.ok === true && r.cambios === 3, '«Hecho» guarda solo los colores: ' + JSON.stringify(r));
bien(JSON.stringify(llamadas[0]) === JSON.stringify([[['7', '✔', '#c6dafc', 'true,=$AK$8:$AV$15;$AK$19:$AV$23', false]], []]),
     'la regla de ✔ que ya existía se CAMBIA (misma regla, mismas celdas), no se duplica');
bien(JSON.stringify(llamadas[1]) === JSON.stringify([[], ['9']]), '«Sin color» quita la regla de X');
bien(llamadas[2] && llamadas[2][0][0][1] === '⚠' && llamadas[2][0][0][2] === '#fce8b2' && llamadas[2][0][0][4] === true,
     'la de ⚠, que no tenía, se crea con su color');
bien(llamadas[2] && llamadas[2][0][0][3] === 'AK8:AV15,AK19:AV23', 'sobre TODO el rango de la lista y con comas (con «;» se quedaba sin celdas): ' + (llamadas[2] && llamadas[2][0][0][3]));

llamadas.length = 0;
bien(I.alHecho(ctx, { uno: 'Hoja1!$C$2:$C$9', rango: ctx.campoRango.value }) === null && !llamadas.length,
     'si se cambió el intervalo, no se hace cargo: va por el camino de siempre');
bien(I.alHecho(ctx, { uno: 'Hoja1!$B$2:$B$4', rango: 'Social!B2:B9' }) === null, 'y lo mismo si se cambió el rango');
bien(I.alHecho({ selector: { value: 'lista' } }, {}) === null && I.alAbrir({ selector: { value: 'lista' } }) === false,
     'con una lista escrita no hace nada');

// Colores oscuros de Google (#11734b ✔, #b10202 X): el texto va en blanco; sobre #ffff00, no (14/10/2026)
window.MaquitaContraste = { CLARO: '#ffffff', OSCURO: '#000000',
    textoSobre: (h) => (['#11734b', '#b10202'].indexOf(h) !== -1 ? '#ffffff' : '#000000') };
llamadas.length = 0;
I.alAbrir(ctx);
filas.lista[0].querySelector('.maq-ld-color').dataset.color = '#11734b';
filas.lista[1].querySelector('.maq-ld-color').dataset.color = '#b10202';
filas.lista[2].querySelector('.maq-ld-color').dataset.color = '#ffff00';
I.alHecho(ctx, { uno: 'Hoja1!$B$2:$B$4', rango: ctx.campoRango.value });
const letras = reglas.map(r => r.valor + ':' + r.color + ':' + (r.letra || '-')).join(' ');
bien(/✔:#11734b:#ffffff/.test(letras), 'sobre el verde oscuro de Google el ✔ va en blanco: ' + letras);
bien(/⚠:#ffff00:-/.test(letras) || llamadas.some(l => l[0][0] && l[0][0][1] === '⚠' && l[0][0][2] === '#ffff00'), 'y sobre el amarillo, el ⚠ conserva su color de texto');
