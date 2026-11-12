/**
 * Enlaces del cuerpo de un correo: lo que la persona COPIA es siempre el destino real (12/11/2026).
 *
 * El servidor envuelve los enlaces de los correos recibidos en el «enlace seguro»
 * (`/api/safelink?u=<destino>&s=<firma>`) para revisarlos al abrirlos. El problema: al copiar el enlace
 * («Copiar dirección de enlace», o seleccionar y copiar) y pegarlo en WhatsApp u otro programa, lo que
 * viajaba era la envoltura, que solo abre desde los países permitidos por el servidor de correo.
 *
 * Aquí, al pintar el correo, cada enlace envuelto queda con su destino real en `href` (y en el texto, si el
 * texto era la propia envoltura) y la envoltura se guarda aparte: el clic sigue pasando por el enlace
 * seguro, pero lo que se copia o se arrastra es el destino verdadero.
 */

const RUTA_PASARELA = '/api/safelink';
const MAX_ANIDADAS = 5;

function decodificar(u: string): string | null {
  try {
    const b64 = u.replace(/-/g, '+').replace(/_/g, '/');
    const bytes = Uint8Array.from(atob(b64 + '='.repeat((4 - (b64.length % 4)) % 4)), c => c.charCodeAt(0));
    return new TextDecoder('utf-8', { fatal: false }).decode(bytes);
  } catch {
    return null;
  }
}

/** Destino real de un enlace de la pasarela (también anidada); null si `href` no es de la pasarela. */
export function destinoReal(href: string): string | null {
  let actual = href;
  let cambio = false;
  for (let i = 0; i < MAX_ANIDADAS; i++) {
    let url: URL;
    try { url = new URL(actual); } catch { break; }
    const u = url.searchParams.get('u');
    if (url.pathname !== RUTA_PASARELA || !u || !url.searchParams.get('s')) break;
    const destino = decodificar(u);
    if (!destino || !/^https?:\/\//i.test(destino)) break;
    actual = destino;
    cambio = true;
  }
  return cambio ? actual : null;
}

/**
 * Deja cada enlace envuelto del documento con su destino real y devuelve el registro de envolturas,
 * para que el clic pueda seguir pasando por el enlace seguro.
 */
export function mostrarDestinosReales(doc: Document): WeakMap<HTMLAnchorElement, string> {
  const envolturas = new WeakMap<HTMLAnchorElement, string>();
  doc.querySelectorAll<HTMLAnchorElement>('a[href]').forEach(a => {
    const envoltura = a.getAttribute('href') || '';
    const real = destinoReal(envoltura);
    if (!real) return;
    envolturas.set(a, envoltura);
    a.setAttribute('href', real);
    // Si el texto visible era la propia envoltura, también se muestra (y se copia) el destino real.
    if (a.childElementCount === 0 && destinoReal((a.textContent || '').trim())) a.textContent = real;
  });
  return envolturas;
}

/** Clic (o clic central) sobre un enlace envuelto: se abre por el enlace seguro. */
export function abrirPorEnlaceSeguro(e: MouseEvent, envolturas: WeakMap<HTMLAnchorElement, string>): boolean {
  if (e.defaultPrevented || e.button > 1) return false;
  const a = (e.target as Element | null)?.closest?.('a[href]') as HTMLAnchorElement | null;
  const envoltura = a ? envolturas.get(a) : undefined;
  if (!envoltura) return false;
  e.preventDefault();
  window.open(envoltura, '_blank', 'noopener,noreferrer');
  return true;
}
