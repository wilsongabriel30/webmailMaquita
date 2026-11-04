/**
 * Escala de la interfaz.
 *
 * En laptops de 1366×768 el webmail se veía «grandote»: la cinta, la lista y la cabecera
 * ocupaban demasiado. La escala reduce toda la interfaz como haría Ctrl+Menos, pero se
 * recuerda por persona y se elige desde Vista → Zoom.
 *
 * 04/11/2026: por omisión 100 % en TODAS las pantallas. El 90 % automático en laptops de
 * 1366×768 dejaba los rótulos de la cinta en unos 8 px reales, ilegibles para buena parte del
 * personal que llega desde Zimbra. El 90 % que se guardaba solo (sin que nadie lo eligiera) se
 * ignora; quien quiera la interfaz más pequeña la vuelve a elegir en Vista → Zoom.
 */
const CLAVE = 'maquita_escala_elegida';
/** Clave anterior: la escribía el arranque con el valor automático, no la persona. */
const CLAVE_ANTERIOR = 'maquita_escala';
export const ESCALAS = [80, 90, 100, 110] as const;
export type Escala = typeof ESCALAS[number];

export function escalaRecomendada(): Escala {
  return 100;
}

export function escalaActual(): Escala {
  try {
    const v = Number(localStorage.getItem(CLAVE));
    if ((ESCALAS as readonly number[]).includes(v)) return v as Escala;
    // De la clave anterior solo se respeta un aumento (110 %): una reducción pudo ser automática.
    const anterior = Number(localStorage.getItem(CLAVE_ANTERIOR));
    if (anterior === 110) return 110;
  } catch { /* sin almacenamiento */ }
  return escalaRecomendada();
}

export function aplicarEscala(v: Escala) {
  const raiz = document.getElementById('root') as HTMLElement | null;
  if (!raiz) return;
  // `zoom` reescala también los px de los estilos en línea; funciona en Chrome, Edge, Safari y Firefox 126+.
  (raiz.style as unknown as { zoom: string }).zoom = v === 100 ? '' : `${v}%`;
  // Las alturas «de pantalla completa» (h-screen, 100vh) se compensan en index.css con esta variable:
  // con zoom al 90 %, 100vh solo cubriría el 90 % de la ventana y quedaría una franja vacía abajo.
  raiz.style.setProperty('--escala', String(v / 100));
  try { localStorage.setItem(CLAVE, String(v)); } catch { /* sin almacenamiento */ }
}

/** Siguiente valor al pulsar el botón Zoom (100 → 110 → 80 → 90 → 100): el primer clic
 *  desde el valor normal AGRANDA, que es lo que busca quien no ve bien. */
export function siguienteEscala(v: Escala): Escala {
  const i = ESCALAS.indexOf(v);
  return ESCALAS[(i + 1) % ESCALAS.length];
}
