/**
 * Envío de la cola de salida sin repetir correos (13/11/2026).
 *
 * La cola mandaba cada correo a /api/mail/send. Con un adjunto pesado o una conexión lenta la
 * petición se cortaba en el navegador (cambio de página, red que se cae un instante) cuando el
 * servidor YA lo había enviado; la cola lo creía pendiente y lo volvía a mandar: hubo personas a
 * quienes el mismo correo les salió tres veces. Ahora cada correo de la cola viaja con un
 * identificador fijo (el suyo en la cola) por la ruta que no repite: si el servidor ya lo recibió,
 * devuelve cómo va ese envío en vez de enviarlo otra vez.
 */
export type ResultadoEnvio =
  | { tipo: 'enviado' }
  | { tipo: 'rechazado'; mensaje: string }      // el servidor dijo que no: no se reintenta solo
  | { tipo: 'pendiente'; mensaje: string };     // no se sabe todavía: se consulta en la próxima vuelta

const esperar = (ms: number) => new Promise(r => setTimeout(r, ms));
const CONSULTAS = 20;          // ≈ 1 minuto esperando la confirmación en esta vuelta
const PAUSA_MS = 3000;

// Reintento a mano de un correo que el servidor rechazó: necesita un identificador nuevo, porque
// con el mismo el servidor devolvería otra vez el rechazo anterior sin intentar nada.
const sufijos = new Map<string, string>();
export function renovarIdentificador(idCola: string): void {
  sufijos.set(idCola, Date.now().toString(36));
}

function idDeEnvio(idCola: string): string {
  const limpio = idCola.replace(/[^A-Za-z0-9-]/g, '').slice(0, 48) || 'cola';
  const sufijo = sufijos.get(idCola);
  return (sufijo ? `${limpio}-r${sufijo}` : limpio).padEnd(8, '0');
}

function esDefinitivo(status: number): boolean {
  return status >= 400 && status < 500 && ![401, 404, 408, 429].includes(status);
}

interface Estado { estado?: string; mensaje?: string }

function leer(e: Estado | null): ResultadoEnvio | null {
  if (e?.estado === 'enviado') return { tipo: 'enviado' };
  if (e?.estado === 'error') return { tipo: 'rechazado', mensaje: e.mensaje || 'El servidor no pudo enviar el correo' };
  return null;
}

export async function enviarUnaVez(idCola: string, cuenta: string, cuerpo: unknown): Promise<ResultadoEnvio> {
  const id = idDeEnvio(idCola);
  const cabeceras = { 'Content-Type': 'application/json', 'X-Cuenta-Activa': cuenta || 'propia' };
  const res = await fetch(`/api/mail/send-segundo-plano?envio_id=${encodeURIComponent(id)}`, {
    method: 'POST', headers: cabeceras, credentials: 'include', body: JSON.stringify(cuerpo),
  });
  if (!res.ok) {
    if (esDefinitivo(res.status)) {
      const body = await res.json().catch(() => ({}));
      const detalle = typeof body?.detail === 'string' ? body.detail : '';
      return { tipo: 'rechazado', mensaje: detalle || `El servidor rechazó el envío (HTTP ${res.status})` };
    }
    return { tipo: 'pendiente', mensaje: `Servidor ocupado (HTTP ${res.status}); se reintentará` };
  }
  const primero = leer(await res.json().catch(() => null));
  if (primero) return primero;
  for (let i = 0; i < CONSULTAS; i++) {
    await esperar(PAUSA_MS);
    try {
      const r = await fetch(`/api/mail/send-segundo-plano/${encodeURIComponent(id)}?t=${Date.now()}`, {
        headers: { 'X-Cuenta-Activa': cuenta || 'propia' }, credentials: 'include',
      });
      if (!r.ok) continue;
      const fin = leer(await r.json().catch(() => null));
      if (fin) return fin;
    } catch {
      /* un tropiezo al consultar no significa que el envío falle */
    }
  }
  return { tipo: 'pendiente', mensaje: 'El servidor sigue enviándolo; se confirmará en unos minutos' };
}
