/**
 * Imágenes pegadas en el redactor: entran DENTRO del texto (como en Word), no como adjunto.
 *
 * - Ctrl+V de una captura o de una imagen copiada la inserta donde está el cursor.
 * - Se puede redimensionar arrastrando las esquinas (extensión Image con `resize`).
 * - Las muy grandes se reducen a ANCHO_MAX para que el correo no pese de más.
 * - Al enviar, el servidor la convierte en imagen incrustada (cid), que todos los clientes muestran.
 */
import type { EditorView } from '@tiptap/pm/view';

const ANCHO_MAX = 1600;
// Ancho con que aparece en el cuerpo; la persona la agranda o achica desde las esquinas.
const ANCHO_INICIAL = 600;

export const OPCIONES_RESIZE = {
  enabled: true,
  directions: ['top-left', 'top-right', 'bottom-left', 'bottom-right'] as ('top-left' | 'top-right' | 'bottom-left' | 'bottom-right')[],
  minWidth: 40,
  minHeight: 40,
  alwaysPreserveAspectRatio: true,
};

function leerComoDataUrl(archivo: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const lector = new FileReader();
    lector.onload = () => resolve(String(lector.result || ''));
    lector.onerror = () => reject(lector.error);
    lector.readAsDataURL(archivo);
  });
}

function cargarImagen(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

/** Devuelve la imagen como data URL, reducida si es enorme, con su ancho y alto de presentación. */
async function prepararImagen(archivo: File): Promise<{ src: string; width: number; height: number }> {
  let src = await leerComoDataUrl(archivo);
  const img = await cargarImagen(src);
  let { naturalWidth: ancho, naturalHeight: alto } = img;
  if (ancho > ANCHO_MAX) {
    const escala = ANCHO_MAX / ancho;
    const lienzo = document.createElement('canvas');
    lienzo.width = Math.round(ancho * escala);
    lienzo.height = Math.round(alto * escala);
    lienzo.getContext('2d')?.drawImage(img, 0, 0, lienzo.width, lienzo.height);
    const tipo = archivo.type === 'image/png' ? 'image/png' : 'image/jpeg';
    src = lienzo.toDataURL(tipo, 0.85);
    ancho = lienzo.width;
    alto = lienzo.height;
  }
  const mostrar = Math.min(ancho, ANCHO_INICIAL);
  return { src, width: mostrar, height: Math.round(alto * (mostrar / ancho)) };
}

/** `editorProps.handlePaste`: si el portapapeles trae imágenes, se insertan en el texto. */
export function pegarImagenes(view: EditorView, evento: ClipboardEvent): boolean {
  const archivos = Array.from(evento.clipboardData?.files || []).filter(f => f.type.startsWith('image/'));
  if (!archivos.length) return false;
  // Si además viene HTML con imágenes de la web (copiado de una página), ese pegado normal ya las trae.
  const html = evento.clipboardData?.getData('text/html') || '';
  if (/<img\s[^>]*src=["']https?:/i.test(html)) return false;
  evento.preventDefault();
  const tipoImagen = view.state.schema.nodes.image;
  if (!tipoImagen) return false;
  (async () => {
    for (const archivo of archivos) {
      try {
        const attrs = await prepararImagen(archivo);
        const { tr } = view.state;
        view.dispatch(tr.replaceSelectionWith(tipoImagen.create(attrs)).scrollIntoView());
      } catch { /* una imagen ilegible no impide pegar las demás */ }
    }
  })();
  return true;
}
