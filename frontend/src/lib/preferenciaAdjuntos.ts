/**
 * Cómo se abre un adjunto al hacer clic en él (13/11/2026).
 *
 * Parte del personal prefiere la vista previa dentro del correo; otra parte la encuentra pequeña,
 * porque tapa el mensaje y no se puede mover, y quiere cada documento en su propia pestaña. Cada
 * persona elige; por defecto sigue la vista previa de siempre.
 */
const CLAVE = 'maquita_adjuntos_en_pestana';

export function abreAdjuntosEnPestana(): boolean {
  try { return localStorage.getItem(CLAVE) === '1'; } catch { return false; }
}

export function guardarAdjuntosEnPestana(v: boolean): void {
  try { localStorage.setItem(CLAVE, v ? '1' : '0'); } catch { /* sin almacenamiento: vale para esta vez */ }
  window.dispatchEvent(new CustomEvent('adjuntos-en-pestana-cambio'));
}
