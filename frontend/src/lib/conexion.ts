// T-35 · Estado REAL de conexión: `navigator.onLine` solo dice si el equipo tiene red; aquí se detecta además si el
// servidor de correo responde (a partir de los fallos y aciertos de la API). Así la interfaz distingue y dice la causa:
//   «sin internet en este equipo»  vs  «el servidor de correo no responde; se reintentará cuando se restablezca».
export type Causa = 'ok' | 'sin_internet' | 'servidor';

let servidorCaido = false;
let ultimoCambio = 0;

function emitir() {
  ultimoCambio = Date.now();
  window.dispatchEvent(new CustomEvent('conexion-cambio', { detail: estadoConexion() }));
}

/** Lo llama el cliente de la API cuando una petición falla por red o por 502/503/504 (incluida la respuesta «offline» del SW). */
export function reportarFallo(): void {
  if (!servidorCaido) { servidorCaido = true; emitir(); }
}
/** Lo llama el cliente de la API cuando una petición al servidor responde (aunque sea 4xx: el servidor está vivo). */
export function reportarExito(): void {
  if (servidorCaido) { servidorCaido = false; emitir(); }
}
export function estadoConexion(): { causa: Causa; hayConexion: boolean; desde: number } {
  const causa: Causa = !navigator.onLine ? 'sin_internet' : servidorCaido ? 'servidor' : 'ok';
  return { causa, hayConexion: causa === 'ok', desde: ultimoCambio };
}
export function textoCausa(): string {
  const c = estadoConexion().causa;
  if (c === 'sin_internet') return 'sin internet en este equipo';
  if (c === 'servidor') return 'el servidor de correo no responde; se reintentará cuando se restablezca';
  return 'conectado';
}

if (typeof window !== 'undefined') {
  window.addEventListener('online', emitir);
  window.addEventListener('offline', emitir);
  // Sondeo ligero cada 30 s mientras el servidor figure caído (para levantar la franja sin esperar a la próxima acción)
  setInterval(() => {
    if (!navigator.onLine || !servidorCaido) return;
    fetch('/api/branding', { credentials: 'include', cache: 'no-store' }).then(r => {
      if (r.status !== 503 && r.status !== 502 && r.status !== 504) reportarExito();
    }).catch(() => { /* sigue caído */ });
  }, 30000);
}
