/**
 * Errores de la interfaz con su ubicación, a la telemetría del servidor (11/11/2026).
 *
 * Hasta hoy solo la aplicación de escritorio avisaba de los errores de JavaScript, y sin decir dónde
 * ocurrían («Cannot read properties of null (reading 'style')», 16 veces, imposible de localizar). Desde
 * un navegador normal no se registraba nada. Aquí se capturan los errores no controlados y las promesas
 * rechazadas, con el archivo, la línea y las primeras líneas de la pila, y la pantalla donde ocurrieron.
 *
 * No se envía contenido de correos ni lo que la persona escribe: solo el mensaje técnico del error.
 * Como mucho 10 por sesión y el mismo error una vez cada 10 minutos.
 */
const RUTA = '/api/telemetria/app';
const MAX_POR_SESION = 10;
const SILENCIO_MS = 10 * 60 * 1000;
const RUIDO = [
  'Failed to update a ServiceWorker', 'ResizeObserver loop', 'Script error.', 'chrome-extension://', 'moz-extension://',
  'Load failed', 'NetworkError when attempting to fetch', 'The operation was aborted', 'AbortError',
];

let enviados = 0;
const vistos = new Map<string, number>();

function limpiar(texto: string): string {
  // Sin el dominio ni las huellas de compilación: queda «assets/MailView-ab12.js:1:2345».
  return texto.replace(new RegExp(window.location.origin.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), '').slice(0, 1500);
}

function reportar(mensaje: string, pila: string, archivo = '', linea = 0, columna = 0, origen = 'error') {
  if (!mensaje || RUIDO.some((r) => mensaje.includes(r) || pila.includes(r))) return;
  if (enviados >= MAX_POR_SESION) return;
  const clave = `${mensaje}|${archivo}|${linea}`;
  const ahora = Date.now();
  if (ahora - (vistos.get(clave) || 0) < SILENCIO_MS) return;
  vistos.set(clave, ahora);
  enviados += 1;
  const cuerpo = JSON.stringify({
    evento: 'error_js', nivel: 'error', modulo: 'web',
    url: window.location.pathname,
    detalle: mensaje.slice(0, 300),
    extra: {
      origen,
      archivo: limpiar(archivo), linea, columna,
      pila: limpiar(pila).split('\n').slice(0, 8),
      vista: `${window.location.pathname}${window.location.hash.split('?')[0]}`,
      ancho: window.innerWidth, alto: window.innerHeight,
      app: /MaquitaTeams\/[\d.]+/.exec(navigator.userAgent)?.[0] || 'navegador',
    },
  });
  try {
    fetch(RUTA, { method: 'POST', credentials: 'include', keepalive: true, headers: { 'Content-Type': 'application/json' }, body: cuerpo })
      .catch(() => { /* la telemetría nunca molesta */ });
  } catch { /* sin fetch: nada */ }
}

/** Se llama una vez al arrancar la aplicación. */
export function vigilarErroresDeLaInterfaz() {
  window.addEventListener('error', (e: ErrorEvent) => {
    reportar(e.message || String(e.error || ''), e.error?.stack || '', e.filename || '', e.lineno || 0, e.colno || 0);
  });
  window.addEventListener('unhandledrejection', (e: PromiseRejectionEvent) => {
    const motivo = e.reason;
    const mensaje = motivo instanceof Error ? `${motivo.name}: ${motivo.message}` : String(motivo ?? '');
    reportar(mensaje, motivo instanceof Error ? motivo.stack || '' : '', '', 0, 0, 'promesa');
  });
}
