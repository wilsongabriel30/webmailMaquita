/** Utilidades de los enlaces del cuerpo del mensaje que se redacta. */

const ESQUEMAS_SEGUROS = /^(https?:|mailto:|tel:)/i;
/** Completa el enlace que se escribió sin protocolo («www.example.org» → «https://…»). */
export function normalizarEnlace(valor: string): string {
  const url = valor.trim();
  if (!url) return '';
  if (/^[a-z][a-z0-9+.-]*:/i.test(url)) return url;
  if (/^[^\s@/]+@[^\s@/]+\.[^\s@/]+$/.test(url)) return `mailto:${url}`;
  return `https://${url.replace(/^\/+/, '')}`;
}

/** Abre el enlace en otra pestaña; solo direcciones web, de correo o de teléfono. */
export function abrirEnlace(href: string) {
  const url = normalizarEnlace(href);
  if (ESQUEMAS_SEGUROS.test(url)) window.open(url, '_blank', 'noopener,noreferrer');
}
