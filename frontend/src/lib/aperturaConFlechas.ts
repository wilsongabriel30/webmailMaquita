/**
 * Apertura de correos con las flechas del teclado sin desbordar al servidor (05/11/2026).
 *
 * Con la flecha mantenida pulsada, el teclado repite el evento unas 30 veces por segundo y cada
 * repetición pedía el correo completo (más la consulta del remitente): una sola persona llegó a
 * 600 peticiones en 12 segundos y el servidor la frenó con 429 (gagricola, 05/11/2026 12:28).
 *
 * - Una pulsación suelta abre el correo al instante, como siempre.
 * - Mientras la tecla se repite, solo se mueve el resaltado; el correo se pide al soltar (o al
 *   cabo de una pausa corta), y solo el último.
 * - Si llega la respuesta de un correo que ya no es el pedido más reciente, se descarta.
 */

const PAUSA_MS = 180;

let temporizador: ReturnType<typeof setTimeout> | null = null;
let ultimoPedido = 0;

/** Marca `uid` como el último correo pedido y dice si la respuesta de `uid` sigue siendo la esperada. */
export function pedido(uid: number): void {
  ultimoPedido = uid;
}

export function sigueVigente(uid: number): boolean {
  return ultimoPedido === uid;
}

/**
 * Pide abrir `uid`. Con `repetido` (e.repeat) se espera a que la tecla deje de repetirse y se abre
 * solo el último; sin él, se abre en el acto.
 */
export function abrirConFlecha(uid: number, repetido: boolean, abrir: (uid: number) => void): void {
  if (temporizador) {
    clearTimeout(temporizador);
    temporizador = null;
  }
  if (!repetido) {
    abrir(uid);
    return;
  }
  temporizador = setTimeout(() => {
    temporizador = null;
    abrir(uid);
  }, PAUSA_MS);
}
