/**
 * explorador-cuota.js  -  Módulo: lectura y rótulos del espacio usado
 * Responsabilidad ÚNICA: entender la respuesta de GET /cuota y redactar el texto del lateral.
 *
 * El Almacén responde PLANO ({usado_humano, total_humano, total, libre, porcentaje, cuota: <bytes>});
 * la Nube anterior respondía ANIDADO ({cuota: {usado_humano, total_humano, porcentaje_usado, ...}}).
 * El explorador leía solo la forma anidada: con el Almacén mostraba siempre «0 B de Sin límite».
 * Sin dependencias. Cargar ANTES de explorador-interactions.js.
 */

function _bytesLegiblesCuota(bytes) {
    let n = Number(bytes);
    if (!isFinite(n) || n < 0) return '';
    const unidades = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    while (n >= 1024 && i < unidades.length - 1) { n /= 1024; i++; }
    return (i === 0 ? String(Math.round(n)) : n.toFixed(1)) + ' ' + unidades[i];
}

/** Devuelve {porcentaje_usado, usado_humano, total_humano, libre_humano, sin_limite} o null
 *  si la respuesta no trae cuota. total_humano queda vacío cuando no hay límite. */
function normalizarCuota(data) {
    if (!data || !data.success) return null;
    const anidada = data.cuota && typeof data.cuota === 'object';
    const c = anidada ? data.cuota : data;
    if (!anidada && c.usado_humano === undefined && c.usado === undefined) return null;
    const sinLimite = (c.total !== undefined && c.total !== null) ? !(Number(c.total) > 0) : !c.total_humano;
    const porcentaje = Number(c.porcentaje_usado !== undefined ? c.porcentaje_usado : c.porcentaje) || 0;
    return {
        porcentaje_usado: porcentaje,
        usado_humano: c.usado_humano || _bytesLegiblesCuota(c.usado) || '0 B',
        total_humano: sinLimite ? '' : (c.total_humano || _bytesLegiblesCuota(c.total)),
        libre_humano: sinLimite ? 'Sin límite' : (c.libre_humano || _bytesLegiblesCuota(c.libre) || '-'),
        sin_limite: sinLimite
    };
}

/** «Archivos: 1.2 GB de 5.0 GB usados» o, sin límite, «Archivos: 1.2 GB usados (sin límite)». */
function textoEspacioUsado(etiqueta, usado, total) {
    return total ? `${etiqueta}: ${usado} de ${total} usados` : `${etiqueta}: ${usado} usados (sin límite)`;
}
