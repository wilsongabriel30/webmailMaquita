// Cuenta activa: varias cuentas de correo en una misma sesión (estilo Outlook).
//
// La sesión es de la persona; lo único que cambia al elegir otra cuenta en la barra lateral es
// el CORREO (y su firma y filtros). Cada pestaña recuerda su cuenta en sessionStorage, así dos
// pestañas pueden trabajar con cuentas distintas sin pisarse.
//
// - Toda petición a /api/ lleva la cabecera X-Cuenta-Activa (la cuenta, o "propia"). El servidor
//   solo la mira en correo, firmas y filtros (backend: mail/services/cuenta_activa.py).
// - Enlaces de descarga, imágenes y adjuntos (href/src) no pueden llevar cabeceras: para ellos
//   va la cookie `cuenta_activa`, que el servidor solo acepta en consultas, nunca para enviar.
// - Al cambiar de cuenta se recarga el webmail: todas las listas, cachés y paneles abiertos se
//   rehacen con la cuenta nueva y nada de la anterior queda a la vista.

const CLAVE = 'maquita_cuenta_activa';
const COOKIE = 'cuenta_activa';
export const CABECERA = 'X-Cuenta-Activa';

const PALETA = ['#0078d4', '#107c10', '#8661c5', '#d83b01', '#c239b3', '#038387', '#ca5010', '#4f6bed'];

/** Color estable por cuenta (mismo correo, mismo color siempre). */
export function colorDeCuenta(email: string): string {
  let h = 0;
  for (const ch of email.toLowerCase()) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return PALETA[h % PALETA.length];
}

/** Cuenta asignada con la que trabaja esta pestaña, o null si es la propia. */
export function cuentaActiva(): string | null {
  try {
    return sessionStorage.getItem(CLAVE);
  } catch {
    return null;
  }
}

function ponerCookie(cuenta: string | null): void {
  const base = 'Path=/api/; SameSite=Strict; Secure';
  document.cookie = cuenta ? `${COOKIE}=${cuenta}; ${base}` : `${COOKIE}=; Max-Age=0; ${base}`;
}

/** Cambia de cuenta (null o la propia = volver a la suya) y recarga el webmail. */
export function elegirCuenta(email: string | null, propia: string): void {
  const c = email && email.toLowerCase() !== propia.toLowerCase() ? email.toLowerCase() : null;
  try {
    if (c) sessionStorage.setItem(CLAVE, c);
    else sessionStorage.removeItem(CLAVE);
  } catch {
    /* sin sessionStorage la pestaña se queda en la propia */
  }
  ponerCookie(c);
  window.location.assign('/webmail/');
}

function esApiPropia(url: string): boolean {
  return url.startsWith('/api/') || url.startsWith(`${window.location.origin}/api/`);
}

let instalada = false;

/** Se llama una sola vez al arrancar, antes de cualquier petición. */
export function instalarCuentaActiva(): void {
  if (instalada) return;
  instalada = true;
  ponerCookie(cuentaActiva());
  const original = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    if (!esApiPropia(url)) return original(input, init);
    const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined));
    if (!headers.has(CABECERA)) headers.set(CABECERA, cuentaActiva() || 'propia');
    const res = await original(input, { ...init, headers });
    if (res.status === 403 && cuentaActiva()) avisarSiRevocada(res.clone());
    return res;
  };
}

/** Si a la persona le quitaron la cuenta con la que trabaja, vuelve a la suya. */
function avisarSiRevocada(res: Response): void {
  res
    .json()
    .then((b) => {
      const revocada = b?.detail?.cuenta_revocada || b?.cuenta_revocada;
      if (!revocada || revocada !== cuentaActiva()) return;
      window.alert(`Ya no tienes asignada la cuenta ${revocada}. Vuelves a tu cuenta.`);
      try {
        sessionStorage.removeItem(CLAVE);
      } catch {
        /* nada */
      }
      ponerCookie(null);
      window.location.assign('/webmail/');
    })
    .catch(() => {});
}
