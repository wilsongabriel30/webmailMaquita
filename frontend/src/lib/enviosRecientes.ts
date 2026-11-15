/**
 * enviosRecientes.ts — Correos que la persona acaba de enviar y el servidor aún está entregando (13/11/2026).
 *
 * Pedido del personal: al pulsar «Enviar» el correo debe darse por hecho, sin avisos de «enviando».
 * El envío sigue por detrás (lib/envioSegundoPlano.ts); mientras tanto, el correo se anota aquí
 * para que «Enviados» lo muestre desde el primer momento (components/mail/EnviosEnCurso.tsx).
 * Se retira cuando el servidor confirma (ya está en la lista real), si la persona pulsa «Deshacer»
 * o si el envío falla (en ese caso el redactor avisa y vuelve a abrir el correo).
 * Solo vive en memoria de la pestaña: no es una cola ni guarda nada.
 */
export interface EnvioReciente { id: string; asunto: string; para: string; inicio: number }

export const EVENTO_ENVIOS_RECIENTES = 'envios-recientes';

const recientes = new Map<string, EnvioReciente>();
const saliendo = new Set<string>();
let contador = 0;

function avisarCambio(): void {
  window.dispatchEvent(new CustomEvent(EVENTO_ENVIOS_RECIENTES));
}

export function enviosRecientes(): EnvioReciente[] {
  return [...recientes.values()].sort((a, b) => b.inicio - a.inicio);
}

/** Anota un correo recién enviado y devuelve su identificador para retirarlo después. */
export function anotarEnvioReciente(asunto: string, para: string[]): string {
  const id = `reciente-${Date.now()}-${++contador}`;
  recientes.set(id, { id, asunto: asunto.trim() || '(sin asunto)', para: para.join(', '), inicio: Date.now() });
  avisarCambio();
  return id;
}

/**
 * Retira el correo de la lista provisional. Con `esperaMs`, lo deja ese tiempo más para que la
 * lista real de «Enviados» alcance a traerlo y no haya un parpadeo sin el correo a la vista.
 */
export function retirarEnvioReciente(id: string, esperaMs = 0): void {
  if (!recientes.has(id) || saliendo.has(id)) return;
  const quitar = () => { saliendo.delete(id); recientes.delete(id); avisarCambio(); };
  if (esperaMs <= 0) { quitar(); return; }
  saliendo.add(id);
  window.setTimeout(quitar, esperaMs);
}
