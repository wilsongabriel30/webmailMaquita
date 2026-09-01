/**
 * Modo app (cliente de escritorio Teams Maquita).
 * Opcional: solo se activa con ?app=1 (queda en la cookie mail_app para la sesión; ?app=0 la borra)
 * o si el User-Agent contiene "MaquitaTeams". En el navegador normal el webmail no cambia.
 * Efecto: clase `modo-app` en <html> → se oculta la cabecera (el cliente ya tiene riel, perfil,
 * soporte y chat propios) y la burbuja de chat flotante.
 */
function detectar(): boolean {
  try {
    const q = new URLSearchParams(window.location.search).get("app");
    if (q === "1") document.cookie = "mail_app=1; path=/; max-age=31536000; secure; samesite=lax";
    if (q === "0") document.cookie = "mail_app=; path=/; max-age=0; secure; samesite=lax";
    return q === "1" || (q !== "0" && (/(^|; )mail_app=1/.test(document.cookie) || /MaquitaTeams/i.test(navigator.userAgent)));
  } catch {
    return false;
  }
}

const activo = detectar();
if (activo) document.documentElement.classList.add("modo-app");

export function esModoApp(): boolean {
  return activo;
}
