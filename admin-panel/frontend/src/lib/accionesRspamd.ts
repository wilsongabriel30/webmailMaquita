/**
 * Nombres en español de las acciones de Rspamd, para tarjetas y gráficos del panel.
 * Las claves son las que devuelve Rspamd en su historial y estadísticas.
 */
export const ACCIONES_RSPAMD: Record<string, string> = {
  "no action": "Aceptado",
  greylist: "Lista gris",
  "add header": "Marcado como spam",
  "rewrite subject": "Asunto reescrito",
  "soft reject": "Rechazo temporal",
  reject: "Rechazado",
};

export function nombreAccionRspamd(accion: string): string {
  return ACCIONES_RSPAMD[accion] || accion;
}
