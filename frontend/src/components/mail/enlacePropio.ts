// Enlaces de un correo que llevan al propio webmail (p. ej. «Abrir la tarea» del aviso de asignación).
// El visor abre los enlaces del correo en una pestaña nueva; estos deben abrirse en la MISMA pestaña,
// como en Outlook, para no acabar con el webmail abierto dos veces (05/11/2026).

/** Si `href` es una página del propio webmail (mismo origen y bajo su base), la devuelve; si no, null. */
export function enlacePropio(href: string, origen = window.location.origin): string | null {
  const base = (import.meta.env.BASE_URL || '/').replace(/\/?$/, '/');
  try {
    const url = new URL(href, origen);
    if (url.origin !== origen) return null;
    if (url.pathname !== base.slice(0, -1) && !url.pathname.startsWith(base)) return null;
    return url.href;
  } catch {
    return null;
  }
}

/** Clic en un enlace del cuerpo: si va al propio webmail y es un clic normal, se abre aquí mismo. */
export function abrirEnlacePropio(e: MouseEvent): boolean {
  if (e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return false;
  const a = (e.target as Element | null)?.closest?.('a[href]') as HTMLAnchorElement | null;
  if (!a) return false;
  const destino = enlacePropio(a.href);
  if (!destino) return false;
  e.preventDefault();
  window.location.assign(destino);
  return true;
}
