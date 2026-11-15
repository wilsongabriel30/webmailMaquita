/**
 * descargarImagen.ts — «Descargar imagen» para las imágenes del cuerpo de un correo (13/11/2026).
 *
 * - Incrustadas (`data:`), temporales (`blob:`) o servidas por el propio webmail: se descargan tal cual.
 * - Remotas (de otro servidor): las normas de seguridad del navegador no dejan leerlas directamente;
 *   se intenta a través de un lienzo y, si el servidor de origen no lo permite, se abren en una
 *   pestaña nueva para guardarlas desde allí.
 * Nombre: el del archivo incrustado si se conoce (ruta del adjunto o texto alternativo con
 * extensión); si no, `imagen.<extensión>`.
 */
export type ResultadoDescarga = 'descargada' | 'pestana' | 'error';

const EXTENSION_POR_TIPO: Record<string, string> = {
  'image/png': 'png', 'image/jpeg': 'jpg', 'image/jpg': 'jpg', 'image/gif': 'gif', 'image/webp': 'webp',
  'image/bmp': 'bmp', 'image/svg+xml': 'svg', 'image/x-icon': 'ico', 'image/tiff': 'tif', 'image/avif': 'avif',
};
const CON_EXTENSION = /\.(png|jpe?g|gif|webp|bmp|svg|ico|tiff?|avif)$/i;
const RUTA_ADJUNTO = /\/api\/mail\/[a-z-]+\/[^/]+\/\d+\/[\d.]+\/([^/?#]+)/i;

function limpiarNombre(nombre: string): string {
  // Sin barras ni caracteres que Windows no admite en nombres de archivo.
  return nombre.replace(/[\\/:*?"<>|]+/g, '_').replace(/\s+/g, ' ').trim().slice(0, 120);
}

function decodificar(texto: string): string {
  try { return decodeURIComponent(texto); } catch { return texto; }
}

/** Nombre con que se guardará la imagen. `tipo` es su tipo MIME, si ya se conoce. */
export function nombreDeImagen(src: string, alt = '', tipo = ''): string {
  const deAdjunto = RUTA_ADJUNTO.exec(src)?.[1];
  if (deAdjunto && CON_EXTENSION.test(decodificar(deAdjunto))) return limpiarNombre(decodificar(deAdjunto));
  if (alt && CON_EXTENSION.test(alt.trim())) return limpiarNombre(alt);
  let extension = EXTENSION_POR_TIPO[tipo.toLowerCase()] || '';
  if (!extension) {
    const deDatos = /^data:([^;,]+)/i.exec(src)?.[1]?.toLowerCase();
    if (deDatos) extension = EXTENSION_POR_TIPO[deDatos] || '';
  }
  if (!extension && /^https?:/i.test(src)) {
    try {
      const ultimo = decodificar(new URL(src).pathname.split('/').pop() || '');
      if (CON_EXTENSION.test(ultimo)) return limpiarNombre(ultimo);
    } catch { /* dirección rara: se usa el nombre genérico */ }
  }
  return `imagen.${extension || 'png'}`;
}

function guardar(url: string, nombre: string): void {
  const enlace = document.createElement('a');
  enlace.href = url;
  enlace.download = nombre;
  enlace.rel = 'noopener';
  enlace.style.display = 'none';
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
}

function guardarBlob(blob: Blob, nombre: string): void {
  const url = URL.createObjectURL(blob);
  guardar(url, nombre);
  window.setTimeout(() => URL.revokeObjectURL(url), 60000);
}

/** `data:image/png;base64,…` → Blob, sin pedir nada a la red. */
function blobDeDatos(src: string): Blob | null {
  const m = /^data:([^;,]*)((?:;[^;,]*)*),(.*)$/s.exec(src);
  if (!m) return null;
  const tipo = m[1] || 'application/octet-stream';
  if (!/;base64/i.test(m[2])) return new Blob([decodificar(m[3])], { type: tipo });
  const binario = atob(m[3].replace(/\s+/g, ''));
  const bytes = new Uint8Array(binario.length);
  for (let i = 0; i < binario.length; i++) bytes[i] = binario.charCodeAt(i);
  return new Blob([bytes], { type: tipo });
}

/** Imagen de otro servidor: solo se puede copiar a un lienzo si ese servidor lo autoriza. */
function blobPorLienzo(src: string): Promise<Blob | null> {
  return new Promise((resolver) => {
    const img = new Image();
    const fin = window.setTimeout(() => resolver(null), 8000);
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      window.clearTimeout(fin);
      try {
        const lienzo = document.createElement('canvas');
        lienzo.width = img.naturalWidth;
        lienzo.height = img.naturalHeight;
        lienzo.getContext('2d')?.drawImage(img, 0, 0);
        lienzo.toBlob((b) => resolver(b), 'image/png');
      } catch { resolver(null); }
    };
    img.onerror = () => { window.clearTimeout(fin); resolver(null); };
    img.src = src;
  });
}

export async function descargarImagen(src: string, alt = ''): Promise<ResultadoDescarga> {
  if (!src) return 'error';
  try {
    if (/^data:/i.test(src)) {
      const blob = blobDeDatos(src);
      if (!blob) return 'error';
      guardarBlob(blob, nombreDeImagen(src, alt, blob.type));
      return 'descargada';
    }
    if (/^blob:/i.test(src)) {
      guardar(src, nombreDeImagen(src, alt));
      return 'descargada';
    }
    if (new URL(src, window.location.href).origin === window.location.origin) {
      const res = await fetch(src, { credentials: 'include' });
      if (!res.ok) return 'error';
      const blob = await res.blob();
      guardarBlob(blob, nombreDeImagen(src, alt, blob.type));
      return 'descargada';
    }
    const blob = await blobPorLienzo(src);
    if (blob) {
      const nombre = nombreDeImagen(src, alt).replace(CON_EXTENSION, '') || 'imagen';
      guardarBlob(blob, `${nombre}.png`);
      return 'descargada';
    }
    window.open(src, '_blank', 'noopener,noreferrer');
    return 'pestana';
  } catch {
    return 'error';
  }
}
