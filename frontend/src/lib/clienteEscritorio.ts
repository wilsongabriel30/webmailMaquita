/**
 * T-99 (10/11/2026): ¿la página la pidió la app de escritorio Teams Maquita?
 * La app quita «MaquitaTeams» del navigator.userAgent visible en JS (para recuperar el buscador
 * del correo apaga el modo app), pero su cabecera HTTP User-Agent lo sigue llevando. nginx lo mira
 * en la cabecera y, solo en ese caso, añade a index.html <meta name="maquita-cliente" content="teams">
 * (map y sub_filter: ver deploy/webmail/nginx/cliente-escritorio.conf).
 * En un navegador normal la etiqueta no existe y todo sigue igual.
 * Uso: dentro de la app no se pinta la burbuja del mini-chat (la app ya tiene su botón Chat).
 */
let cache: boolean | null = null;

export function esClienteEscritorio(): boolean {
  if (cache === null) {
    try {
      cache = document.querySelector('meta[name="maquita-cliente"]')?.getAttribute('content') === 'teams'
        || /MaquitaTeams/i.test(navigator.userAgent);
    } catch {
      cache = false;
    }
  }
  return cache;
}
