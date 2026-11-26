/* En el resultado de un buscador, la barra muestra el dato (12/10/2026).
   Lo que se comprueba: que solo se reconocen las fórmulas de `buscador_vivo.py`
   (cualquier otra se sigue viendo), y qué texto va a la barra según el dato. */

global.window = global;
global.console = console;

require('/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/editor-barra-resultado-buscador.js');

const B = window.MaquitaBarraBuscador;
const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
console.log('\n[Drive Maquita] la barra en el resultado de un buscador\n');

// ── Qué fórmulas son del buscador ────────────────────────────────────────
bien(B.esDelBuscador('IF($AX5="","",IF(INDEX(ConsolidadoT!$O$4:$O$5485,$AX5)="","",INDEX(ConsolidadoT!$O$4:$O$5485,$AX5)))'),
     'una celda del resultado es del buscador');
bien(B.esDelBuscador('=IF($AX5="","",IF(INDEX(ConsolidadoT!$O$4:$O$5485,$AX5)="","",INDEX(ConsolidadoT!$O$4:$O$5485,$AX5)))'),
     'también con «=» delante');
bien(B.esDelBuscador('IF($AX$3=0,NA(),IF($AX4="","",IF(INDEX(ConsolidadoT!$G$4:$G$5485,$AX4)="","",INDEX(ConsolidadoT!$G$4:$G$5485,$AX4))))'),
     'la primera celda (con el #N/A) también');
bien(B.esDelBuscador("IF($AX5=\"\",\"\",IF(INDEX('Hoja con espacios'!$O$4:$O$90,$AX5)=\"\",\"\",INDEX('Hoja con espacios'!$O$4:$O$90,$AX5)))"),
     'con una hoja de nombre entre comillas');
bien(!B.esDelBuscador('IF(2>$AX$3,"",SMALL($AY$4:$AY$5485,2))'), 'la columna auxiliar NO (se ve su fórmula)');
bien(!B.esDelBuscador('SUM(A1:A9)'), 'una fórmula cualquiera NO');
bien(!B.esDelBuscador('IF(A1="","",B1)'), 'un IF cualquiera NO');
bien(!B.esDelBuscador(''), 'una celda sin fórmula NO');
bien(!B.esDelBuscador(null), 'sin nada no revienta');

// ── Qué texto va a la barra ──────────────────────────────────────────────
const celda = (crudo, conFormato) => ({
    getValueWithoutFormat: () => crudo,
    getValueWithFormat: () => (conFormato === undefined ? crudo : conFormato)
});
bien(B.textoParaLaBarra(celda('Talleres\n (5 x 3 zonas)')) === 'Talleres\n (5 x 3 zonas)', 'un texto, tal cual (con su salto de línea)');
bien(B.textoParaLaBarra(celda('1', '1,00')) === '1', 'un número con formato 0,00: el número («1»), como Google');
bien(B.textoParaLaBarra(celda('0.6666666667', '66,67%')) === '66,67%', 'un porcentaje, como se ve');
bien(B.textoParaLaBarra(celda('45.5', '45,50')) === '45,5', 'un decimal, con coma');
bien(B.textoParaLaBarra(celda('', '')) === '', 'vacía: barra vacía');
bien(B.textoParaLaBarra(celda('#N/A')) === '#N/A', 'el #N/A sin coincidencias');
const rota = { getValueWithoutFormat: () => { throw new Error('x'); }, getValueWithFormat: () => { throw new Error('x'); } };
bien(B.textoParaLaBarra(rota) === '', 'si el editor falla, barra vacía (no revienta)');
