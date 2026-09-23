/**
 * Imágenes pegadas en el redactor: entran DENTRO del texto (como en Word), no como adjunto.
 *
 * - Ctrl+V de una captura o de una imagen copiada la inserta donde está el cursor.
 * - Arrastrar una imagen sobre el texto la inserta donde se suelta.
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

/** Inserta las imágenes en `pos` (o donde está el cursor), una tras otra. */
function insertarImagenes(view: EditorView, archivos: File[], pos?: number): void {
  const tipoImagen = view.state.schema.nodes.image;
  if (!tipoImagen) return;
  (async () => {
    for (const archivo of archivos) {
      try {
        const attrs = await prepararImagen(archivo);
        const nodo = tipoImagen.create(attrs);
        const { tr } = view.state;
        if (pos === undefined) tr.replaceSelectionWith(nodo);
        else { tr.insert(Math.min(pos, tr.doc.content.size), nodo); pos += nodo.nodeSize; }
        view.dispatch(tr.scrollIntoView());
      } catch { /* una imagen ilegible no impide insertar las demás */ }
    }
  })();
}

/** Imágenes del portapapeles: por `files` y, si algún navegador lo deja vacío, por `items`. */
function imagenesDelPortapapeles(datos: DataTransfer | null): File[] {
  if (!datos) return [];
  const archivos = Array.from(datos.files || []).filter(f => f.type.startsWith('image/'));
  if (archivos.length) return archivos;
  return Array.from(datos.items || [])
    .filter(i => i.kind === 'file' && i.type.startsWith('image/'))
    .map(i => i.getAsFile())
    .filter((f): f is File => !!f);
}

/** `editorProps.handlePaste`: si el portapapeles trae imágenes, se insertan en el texto. */
export function pegarImagenes(view: EditorView, evento: ClipboardEvent): boolean {
  const archivos = imagenesDelPortapapeles(evento.clipboardData);
  if (!archivos.length || !view.state.schema.nodes.image) return false;
  // Si además viene HTML con imágenes de la web (copiado de una página), ese pegado normal ya las trae.
  const html = evento.clipboardData?.getData('text/html') || '';
  if (/<img\s[^>]*src=["']https?:/i.test(html)) return false;
  evento.preventDefault();
  insertarImagenes(view, archivos);
  return true;
}

/**
 * Pegado con el foco FUERA del texto (en la firma, en el hueco bajo la primera línea…): la
 * imagen va igual al cuerpo, donde quedó el cursor. Antes el Ctrl+V «no hacía nada».
 */
export function pegarImagenesFueraDelTexto(view: EditorView | undefined, evento: ClipboardEvent): void {
  if (!view || view.dom.contains(evento.target as Node)) return; // dentro del texto: lo hace handlePaste
  const archivos = imagenesDelPortapapeles(evento.clipboardData);
  if (!archivos.length || !view.state.schema.nodes.image) return;
  evento.preventDefault();
  view.focus();
  insertarImagenes(view, archivos);
}

/**
 * `editorProps.transformPastedHTML`: Word pone sus imágenes como `file:///…/clip_image001.png`,
 * que el navegador no puede leer (salían rotas). Se quitan y se explica cómo pegarlas.
 */
export function quitarImagenesLocales(html: string, avisar: (texto: string) => void): string {
  if (!/<img\b[^>]*\ssrc=["']?file:/i.test(html)) return html;
  avisar('Las imágenes copiadas junto con texto de Word no se pueden pegar así: cópialas solas (clic derecho sobre la imagen → Copiar) y pégalas.');
  return html.replace(/<img\b[^>]*\ssrc=["']?file:[^>]*>/gi, '');
}

/** Marca en el evento: el editor ya insertó las imágenes soltadas; el panel adjunta solo el resto. */
export const IMAGENES_SOLTADAS_EN_TEXTO = '__imagenesEnTexto';

/**
 * `editorProps.handleDrop`: las imágenes arrastradas sobre el texto entran donde se sueltan.
 * Los demás archivos (PDF, Excel…) siguen como adjuntos: los agrega el `onDrop` del panel.
 */
export function soltarImagenes(view: EditorView, evento: DragEvent, _slice: unknown, moved: boolean): boolean {
  if (moved) return false; // mover una imagen ya puesta dentro del texto: lo hace el editor
  const archivos = imagenesDelPortapapeles(evento.dataTransfer);
  if (!archivos.length || !view.state.schema.nodes.image) return false;
  const destino = view.posAtCoords({ left: evento.clientX, top: evento.clientY });
  (evento as unknown as Record<string, boolean>)[IMAGENES_SOLTADAS_EN_TEXTO] = true;
  insertarImagenes(view, archivos, destino?.pos);
  // true evita que el editor pegue además la ruta del archivo como texto; el evento sigue
  // subiendo hasta el panel, que adjunta lo que no es imagen.
  return true;
}
