// Aviso de correo nuevo en una cuenta asignada que NO está abierta en esta pestaña.
// La barra ya muestra el contador por cuenta; esto añade un aviso emergente (y, si el
// navegador lo permite, una notificación del sistema) cuando sube el número de no leídos
// de otra cuenta. Se puede apagar desde la propia barra; la preferencia queda en el equipo.
import { showToast } from '../components/common/Toast';
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
    const texto = `${nuevos === 1 ? 'Correo nuevo' : `${nuevos} correos nuevos`} en ${c.email}`;
    showToast(texto, { label: 'Ver', onClick: () => elegirCuenta(c.email, propia) });
    notificarSistema(c.nombre || c.email, texto);
    avisadas.push(c.email);
  }
  return avisadas;
}
