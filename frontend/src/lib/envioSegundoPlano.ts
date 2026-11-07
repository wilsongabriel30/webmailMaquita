/**
 * Envío inmediato (06/11/2026): el servidor acepta el correo al instante y lo envía por detrás
 * (backend: mail/routers/envio_segundo_plano.py). Aquí se le entrega, se muestra «Enviando…» en
 * Enviados (EnviosEnCurso.tsx) y se espera el resultado consultando su estado.
 *
 * Devuelve/lanza EXACTAMENTE lo mismo que `api.post('/mail/send', …)`, así el redactor conserva
 * todo su manejo de errores (protección de datos, tamaño, sesión, cola sin conexión).
 * Si la pestaña se cierra, el servidor termina igual y, si falla, avisa en la campanita.
 */
import { api } from '../api/client';

export interface EnvioEnCurso { id: string; asunto: string; para: string; inicio: number }

const enCurso = new Map<string, EnvioEnCurso>();

function avisarCambio() {
  window.dispatchEvent(new CustomEvent('envios-en-curso'));
}

export function enviosEnCurso(): EnvioEnCurso[] {
  return [...enCurso.values()].sort((a, b) => b.inicio - a.inicio);
}

function nuevoId(): string {
  try { return crypto.randomUUID(); } catch { return `${Date.now()}-${Math.random().toString(36).slice(2, 12)}`; }
}

const esperar = (ms: number) => new Promise(r => setTimeout(r, ms));

interface Estado { estado: 'enviando' | 'enviado' | 'error' | 'desconocido'; mensaje?: string; resultado?: unknown }

const SIN_CONFIRMAR = 'No se pudo confirmar si el correo salió. Revisa la carpeta Enviados antes de volver a enviarlo.';

export async function enviarEnSegundoPlano<T = unknown>(
  payload: { subject?: string; to?: string[] } & Record<string, unknown>,
): Promise<T> {
  const id = nuevoId();
  const ruta = `/mail/send-segundo-plano?envio_id=${encodeURIComponent(id)}`;
  // Si esta petición falla (sin red, servidor caído), el error sube tal cual y el redactor lo
  // manda a la cola de salida como siempre.
  await api.post<Estado>(ruta, payload);
  enCurso.set(id, { id, asunto: payload.subject || '(sin asunto)', para: (payload.to || []).join(', '), inicio: Date.now() });
  avisarCambio();
  try {
    let fallosSeguidos = 0;
    for (let intento = 0; ; intento++) {
      await esperar(intento < 10 ? 1500 : 4000);
      let e: Estado;
      try {
        // `t` evita la caché de lecturas del cliente: cada consulta debe ir al servidor.
        e = await api.get<Estado>(`/mail/send-segundo-plano/${encodeURIComponent(id)}?t=${Date.now()}`);
        fallosSeguidos = 0;
      } catch {
        // Un tropiezo de red al CONSULTAR no significa que el envío falle: se sigue esperando.
        if (++fallosSeguidos >= 40) throw new Error(SIN_CONFIRMAR);
        continue;
      }
      if (e.estado === 'enviado') return (e.resultado ?? { status: 'sent' }) as T;
      if (e.estado === 'error') throw new Error(e.mensaje || 'Error al enviar');
      if (e.estado === 'desconocido') throw new Error(SIN_CONFIRMAR);
    }
  } finally {
    enCurso.delete(id);
    avisarCambio();
    window.dispatchEvent(new CustomEvent('refresh-messages'));
  }
}

let activo: Promise<boolean> | null = null;
/** ¿Está activo el envío inmediato para esta cuenta? (interruptor del servidor; se consulta una vez). */
function envioInmediatoActivo(): Promise<boolean> {
  if (!activo) {
    activo = api.get<{ activo: boolean }>(`/mail/envio-inmediato/activo?t=${Date.now()}`)
      .then(r => !!r?.activo).catch(() => false);
  }
  return activo;
}

/** Envía por el camino que corresponda: inmediato (por detrás) o el de siempre (/mail/send). */
export async function enviarCorreo<T = unknown>(payload: { subject?: string; to?: string[] } & Record<string, unknown>): Promise<T> {
  if (await envioInmediatoActivo()) return enviarEnSegundoPlano<T>(payload);
  return api.post<T>('/mail/send', payload);
}
