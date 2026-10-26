// Marca de la organización en la pestaña del navegador (favicon).
// /api/branding es público: se aplica también en la pantalla de entrada, antes de iniciar sesión.
// Sin favicon propio se usa el logo de la organización; sin ninguno queda el ícono neutro de index.html.

export type MarcaPublica = { favicon_url?: string; logo_url?: string; org_name?: string; app_name?: string };

export function aplicarFavicon(marca: MarcaPublica): void {
  const url = marca.favicon_url || marca.logo_url;
  if (!url) return;
  let enlace = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
  if (!enlace) {
    enlace = document.createElement("link");
    enlace.rel = "icon";
    document.head.appendChild(enlace);
  }
  enlace.removeAttribute("integrity");
  enlace.type = "";
  enlace.href = url;
}

export function cargarMarcaPublica(): Promise<MarcaPublica> {
  return fetch("/api/branding")
    .then((r) => (r.ok ? r.json() : {}))
    .catch(() => ({}));
}
