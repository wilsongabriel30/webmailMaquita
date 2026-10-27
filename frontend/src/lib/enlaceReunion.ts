// Enlace de la reunión que llega con un recordatorio (WebSocket type=reminder, campo `link`).
// Solo se aceptan http(s): el valor sale del lugar o la descripción del evento, que puede
// venir de una invitación externa, y un `javascript:` en un botón sería una puerta abierta.
export function enlaceReunionSeguro(valor: unknown): string {
  if (typeof valor !== 'string' || !valor) return '';
  try {
    const u = new URL(valor);
    return u.protocol === 'https:' || u.protocol === 'http:' ? u.href : '';
  } catch {
    return '';
  }
}

export function abrirReunion(enlace: string): void {
  window.open(enlace, '_blank', 'noopener,noreferrer');
}

// El texto del recordatorio ya trae «Entrar a la reunión: <enlace>»; con el botón sobra.
export function quitarLineaEnlace(mensaje: string, enlace: string): string {
  if (!enlace) return mensaje;
  return mensaje.split('\n').filter((l) => !l.includes(enlace)).join('\n');
}
