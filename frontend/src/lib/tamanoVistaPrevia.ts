/**
 * Tamaño de la vista previa de adjuntos (13/11/2026).
 *
 * La ventana centrada tapa el correo y no se puede mover: quien necesita leer el mensaje mientras
 * mira el documento no podía. Tres tamaños, a elección de la persona y recordados en su equipo:
 * «ventana» (la de siempre), «lado» (acoplada a la derecha, con el correo visible y utilizable a la
 * izquierda) y «completa». Sirve también dentro de la aplicación de escritorio, donde no hay pestañas.
 */
export type TamanoVista = 'ventana' | 'lado' | 'completa';

const CLAVE = 'maquita_vista_previa_tamano';
const ORDEN: TamanoVista[] = ['ventana', 'lado', 'completa'];

/**
 * La vista previa se abre SIEMPRE como ventana centrada (13/11/2026, tarde): al recordarse el
 * último tamaño, quien había probado «pantalla completa» se encontraba después con el documento
 * tapándolo todo y sin saber por qué. El botón cambia el tamaño solo mientras está abierta.
 */
export function leerTamano(): TamanoVista {
  try { localStorage.removeItem(CLAVE); } catch { /* nada que limpiar */ }
  return 'ventana';
}

export function guardarTamano(v: TamanoVista): void {
  void v;
  /* ya no se recuerda: ver leerTamano */
}

export function siguienteTamano(v: TamanoVista): TamanoVista {
  return ORDEN[(ORDEN.indexOf(v) + 1) % ORDEN.length];
}

/** Texto del botón: dice a qué tamaño se pasa al pulsarlo. */
export const ROTULO_SIGUIENTE: Record<TamanoVista, string> = {
  ventana: 'Poner al lado',
  lado: 'Pantalla completa',
  completa: 'Ventana pequeña',
};
