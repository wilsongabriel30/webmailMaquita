// Aviso de correo nuevo en una cuenta asignada que NO está abierta en esta pestaña.
// La barra ya muestra el contador por cuenta; esto añade un aviso emergente (y, si el
// navegador lo permite, una notificación del sistema) cuando sube el número de no leídos
// de otra cuenta. Se puede apagar desde la propia barra; la preferencia queda en el equipo.
import { showToast } from '../components/common/Toast';
import { api } from '../api/client';
import { textoAvisoCuenta } from './textoAvisoCorreo';   // remitente y asunto (06/11/2026)
import { elegirCuenta } from './cuentaActiva';
import type { Cuenta } from './cuentas';

const CLAVE = 'maquita_aviso_otras_cuentas';

export function avisosActivos(): boolean {
  try {
    return localStorage.getItem(CLAVE) !== '0';
  } catch {
    return true;
  }
}

export function activarAvisos(valor: boolean): void {
  try {
    localStorage.setItem(CLAVE, valor ? '1' : '0');
  } catch {
    /* sin almacenamiento: queda activo */
  }
}

function notificarSistema(titulo: string, cuerpo: string): void {
  try {
    if (typeof Notification === 'undefined' || Notification.permission !== 'granted') return;
    if (document.visibilityState === 'visible') return; // con la pestaña a la vista basta el aviso emergente
    const n = new Notification(titulo, { body: cuerpo, tag: 'otra-cuenta:' + cuerpo });
    n.onclick = () => window.focus();
  } catch {
    /* navegadores sin Notification (p. ej. el WebView de la app) */
  }
}

/** Compara el conteo anterior con el nuevo y avisa de las cuentas (no activas) que subieron. */
export function avisarCorreoNuevo(
  anterior: Record<string, number | null>,
  actual: Record<string, number | null>,
  cuentas: Cuenta[],
  activa: string,
  propia: string,
): string[] {
  if (!avisosActivos() || Object.keys(anterior).length === 0) return [];
  const avisadas: string[] = [];
  for (const c of cuentas) {
    if (c.email.toLowerCase() === activa.toLowerCase()) continue;
    const antes = anterior[c.email];
    const ahora = actual[c.email];
    if (typeof antes !== 'number' || typeof ahora !== 'number' || ahora <= antes) continue;
    const nuevos = ahora - antes;
    avisarConDetalle(c, nuevos, propia);
    avisadas.push(c.email);
  }
  return avisadas;
}

/* 06/11/2026: el aviso dice quién envió el último correo y su asunto (como los avisos en tiempo real).
 * Se pide al servidor solo cuando sube el conteo; si falla, sale el texto de siempre. */
function avisarConDetalle(c: Cuenta, nuevos: number, propia: string): void {
  const mostrar = (de?: string, asunto?: string) => {
    const a = textoAvisoCuenta(nuevos, c.email, de, asunto);
    const texto = de ? `${a.titulo} — ${a.cuerpo}` : a.cuerpo;
    showToast(texto, { label: 'Ver', onClick: () => elegirCuenta(c.email, propia) });
    notificarSistema(de ? a.titulo : (c.nombre || c.email), a.cuerpo);
  };
  api
    .get<{ de?: string; asunto?: string }>(`/mail/cuentas/ultimo-sin-leer?cuenta=${encodeURIComponent(c.email)}`)
    .then((r) => mostrar(r.de, r.asunto))
    .catch(() => mostrar());
}
