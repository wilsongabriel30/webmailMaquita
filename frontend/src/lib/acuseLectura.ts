/**
 * Confirmaciones de lectura que nos piden (09/11/2026).
 *
 * Cuando un correo trae «Disposition-Notification-To», el backend lo indica en el detalle
 * (`acuse_lectura`). Según la preferencia de la persona (Configuración → General) se envía
 * solo, se pregunta o nunca se envía. La preferencia vive en el servidor (/api/settings) para
 * que sea la misma en todos sus dispositivos; aquí se guarda en memoria durante la sesión.
 */
import { api } from '../api/client';

export type PreferenciaAcuse = 'preguntar' | 'siempre' | 'nunca';

export interface PedidoAcuse {
  to: string;
  /** false: el acuse iría a otra dirección distinta del remitente; en ese caso siempre se pregunta. */
  mismo_remitente: boolean;
}

interface AjustesServidor { acuse_lectura?: PreferenciaAcuse; [k: string]: unknown }

let cache: Promise<AjustesServidor> | null = null;

function ajustes(): Promise<AjustesServidor> {
  if (!cache) cache = api.get<AjustesServidor>('/settings').catch((): AjustesServidor => ({}));
  return cache;
}

export async function preferenciaAcuse(): Promise<PreferenciaAcuse> {
  const a = await ajustes();
  const v = a.acuse_lectura;
  return v === 'siempre' || v === 'nunca' ? v : 'preguntar';
}

/** Guarda la preferencia en el servidor (envía el resto de ajustes tal como están). */
export async function guardarPreferenciaAcuse(valor: PreferenciaAcuse): Promise<void> {
  const a = await ajustes();
  const nuevos = { ...a, acuse_lectura: valor };
  await api.put('/settings', nuevos);
  cache = Promise.resolve(nuevos);
}

/** Olvida la copia en memoria (tras guardar desde Configuración, por ejemplo). */
export function olvidarPreferenciaAcuse(): void { cache = null; }

export async function responderAcuse(folder: string, uid: number, enviar: boolean): Promise<{ enviado: boolean; destinatario: string | null }> {
  return api.post('/mail/acuse-lectura', { folder, uid, enviar });
}
