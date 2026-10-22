/**
 * Modo app (cliente de escritorio Teams Maquita).
 * Solo se activa dentro del cliente: su navegador se identifica con "MaquitaTeams" en el
 * User-Agent (identificador interno del cliente, no lo ve nadie; a diferencia de la app Android,
 * que ya tiene el agente neutro «CorreoApp», el cliente de escritorio no tiene otro todavía).
 * Ahí, ?app=1 deja la cookie mail_app para las cargas siguientes y ?app=0 la borra.
 * Efecto: clase `modo-app` en <html> → se oculta la cabecera (el cliente ya tiene riel, perfil,
 * soporte y chat propios) y la burbuja de chat flotante.
 *
 * En un navegador normal ?app=1 se IGNORA y, si quedó una cookie mail_app de antes, se borra.
 * Motivo (19/10/2026): el chat del cliente genera enlaces con ?app=1 y, si el navegador
 * predeterminado es Chrome, se abrían ahí; la cookie de un año dejaba ese Chrome sin cabecera
 * ni buscador «para siempre», y la persona lo veía como un fallo de Chrome.
 */
const COOKIE_BORRAR = "mail_app=; path=/; max-age=0; secure; samesite=lax";

function detectar(): boolean {
  try {
    const esCliente = /MaquitaTeams/i.test(navigator.userAgent);
    const q = new URLSearchParams(window.location.search).get("app");
    const cookie = /(^|; )mail_app=1/.test(document.cookie);
    if (!esCliente) {
      if (cookie) document.cookie = COOKIE_BORRAR;
      return false;
    }
    if (q === "1") document.cookie = "mail_app=1; path=/; max-age=31536000; secure; samesite=lax";
    if (q === "0") document.cookie = COOKIE_BORRAR;
    return q !== "0";
  } catch {
    return false;
  }
}

const activo = detectar();
if (activo) document.documentElement.classList.add("modo-app");

export function esModoApp(): boolean {
  return activo;
}
