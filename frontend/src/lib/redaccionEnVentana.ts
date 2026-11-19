/**
 * Redacción en ventana aparte (opción estilo Outlook).
 *
 * La app «Teams Maquita» activa esta opción y la señaliza de dos formas (basta una):
 *   - Cookie:      mail_redactar=1   (0 = apagado)
 *   - Variable JS: window.__maquitaRedactarVentana === true
 *
 * Con la señal activa, al redactar (nuevo, responder, responder a todos o reenviar) la
 * redacción se abre en una ventana emergente propia cuyo nombre empieza por «mq-redactar»:
 * así la app la reconoce y la pone en una ventana independiente, minimizable a la barra de
 * tareas, conservando window.opener.
 *
 * Todo pasa por store/mailStore.openCompose (único punto de entrada), por eso basta
 * interceptar ahí. Si el navegador bloquea la ventana, se vuelve al comportamiento normal
 * (redacción dentro de la página).
 *
 * Los datos de la redacción (modo + ComposeData, todo serializable) se entregan a la ventana
 * por localStorage del mismo origen, con una clave de un solo uso; la ventana los lee y los
 * borra. ComposeData solo lleva metadatos (los adjuntos del original se descargan en la
 * ventana por carpeta + uid), así que el traspaso no pierde nada.
 */
import type { ComposeData } from '../types';
import { cuentaActiva } from './cuentaActiva';

const PREFIJO_VENTANA = 'mq-redactar';

type ModoRedaccion = 'new' | 'reply' | 'replyAll' | 'forward';

/** ¿El usuario (vía la app) pidió redactar en ventana aparte? */
export function redaccionEnVentanaActiva(): boolean {
  try {
    const w = window as unknown as { __maquitaRedactarVentana?: boolean };
    if (typeof window !== 'undefined' && w.__maquitaRedactarVentana === true) return true;
    return /(?:^|;\s*)mail_redactar=1(?:\s*;|\s*$)/.test(document.cookie || '');
  } catch {
    return false;
  }
}

/** ¿Estamos YA dentro de una ventana de redacción? (evita abrir otra en cascada) */
export function esVentanaDeRedaccion(): boolean {
  try {
    if (typeof window !== 'undefined' && (window.name || '').startsWith(PREFIJO_VENTANA)) return true;
    return typeof location !== 'undefined' && location.pathname.endsWith('/compose');
  } catch {
    return false;
  }
}

/** Solo en la ventana principal y con la señal activa. */
export function debeAbrirRedaccionEnVentana(): boolean {
  return redaccionEnVentanaActiva() && !esVentanaDeRedaccion();
}

/**
 * Abre la redacción en una ventana emergente propia. Devuelve true si se abrió; false si el
 * navegador la bloqueó (para que quien llama vuelva al comportamiento dentro de la página).
 */
export function abrirRedaccionEnVentana(mode: ModoRedaccion, data: ComposeData | null): boolean {
  let clave = '';
  try {
    clave = `${PREFIJO_VENTANA}-datos-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    localStorage.setItem(clave, JSON.stringify({ mode, data, t: Date.now() }));
  } catch {
    clave = '';   // sin localStorage: la ventana abrirá una redacción nueva vacía
  }
  const base = (import.meta.env.BASE_URL || '/').replace(/\/?$/, '/');
  // La cuenta activa viaja en la URL: la ventana nueva (contexto propio) no hereda sessionStorage,
  // así redacta/envía con la cuenta correcta y no con la primaria (mismo motivo que /mensaje).
  const cuenta = cuentaActiva();
  const params = new URLSearchParams();
  if (clave) params.set('handoff', clave);
  if (cuenta) params.set('cuenta', cuenta);
  const consulta = params.toString();
  const url = `${base}compose${consulta ? `?${consulta}` : ''}`;
  const nombre = `${PREFIJO_VENTANA}-${Date.now()}`;
  let ventana: Window | null = null;
  try {
    ventana = window.open(url, nombre, 'width=900,height=680,menubar=no,toolbar=no,location=no');
  } catch {
    ventana = null;
  }
  if (!ventana) {
    if (clave) { try { localStorage.removeItem(clave); } catch { /* vacío */ } }
    return false;
  }
  try { ventana.focus(); } catch { /* vacío */ }
  return true;
}

/** Lee (y borra) los datos de redacción entregados a esta ventana por la clave «handoff». */
export function tomarDatosDeRedaccion(): { mode: ModoRedaccion; data: ComposeData | null } | null {
  try {
    const clave = new URLSearchParams(window.location.search).get('handoff');
    if (!clave) return null;
    const crudo = localStorage.getItem(clave);
    try { localStorage.removeItem(clave); } catch { /* vacío */ }
    if (!crudo) return null;
    const obj = JSON.parse(crudo) as { mode?: string; data?: ComposeData | null };
    if (obj && typeof obj.mode === 'string') {
      return { mode: obj.mode as ModoRedaccion, data: obj.data ?? null };
    }
    return null;
  } catch {
    return null;
  }
}
