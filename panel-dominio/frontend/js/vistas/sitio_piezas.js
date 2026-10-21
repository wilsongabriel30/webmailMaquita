// Piezas pequeñas de las pestañas de la v1.10 (Web, Archivos, Copias, Visitas y registros).
import { el, agregar } from '../ui.js';

/** Bloque plegable dentro de una pestaña (en el teléfono ocupa poco hasta que se abre). */
export const bloque = (titulo, ayuda, ...hijos) => el('details', { clase: 'caja' }, el('summary', null, titulo),
  ayuda ? el('p', { clase: 'ayuda' }, ayuda) : null, ...hijos);

/** Botón con su acción; `fn` recibe el propio botón (para desactivarlo mientras trabaja). */
export const boton = (texto, clase, fn, tipo) => {
  const b = el('button', { clase, type: tipo || 'button' }, texto);
  if (fn) b.addEventListener('click', () => fn(b));
  return b;
};

/** Cambia el contenido de `nodo` saltándose los huecos (null, false): replaceChildren los pintaría como texto. */
export const poner = (nodo, ...hijos) => { nodo.replaceChildren(); return agregar(nodo, ...hijos); };
