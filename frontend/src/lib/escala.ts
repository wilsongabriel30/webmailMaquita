/**
 * Escala de la interfaz.
 *
 * En laptops de 1366×768 el webmail se veía «grandote»: la cinta, la lista y la cabecera
 * ocupaban demasiado. La escala reduce toda la interfaz como haría Ctrl+Menos, pero se
 * recuerda por persona y se elige desde Vista → Zoom. Por omisión: 90 % en pantallas de
 * hasta 1440×900 y 100 % en las demás.
 */
const CLAVE = 'maquita_escala';
export const ESCALAS = [80, 90, 100, 110] as const;
export type Escala = typeof ESCALAS[number];

export function escalaRecomendada(): Escala {
  if (typeof window === 'undefined') return 100;
  return window.screen.width <= 1440 && window.screen.height <= 900 ? 90 : 100;
}

export function escalaActual(): Escala {
  try {
    const v = Number(localStorage.getItem(CLAVE));
    if ((ESCALAS as readonly number[]).includes(v)) return v as Escala;
  } catch { /* sin almacenamiento */ }
  return escalaRecomendada();
}

export function aplicarEscala(v: Escala) {
  const raiz = document.getElementById('root') as HTMLElement | null;
  if (!raiz) return;
  // `zoom` reescala también los px de los estilos en línea; funciona en Chrome, Edge, Safari y Firefox 126+.
  (raiz.style as unknown as { zoom: string }).zoom = v === 100 ? '' : `${v}%`;
  try { localStorage.setItem(CLAVE, String(v)); } catch { /* sin almacenamiento */ }
}

/** Siguiente valor al pulsar el botón Zoom (80 → 90 → 100 → 110 → 80). */
export function siguienteEscala(v: Escala): Escala {
  const i = ESCALAS.indexOf(v);
  return ESCALAS[(i + 1) % ESCALAS.length];
}
