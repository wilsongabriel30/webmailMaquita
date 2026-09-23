/**
 * Imágenes adjuntas vistas dentro del correo, debajo del texto, sin abrirlas ni descargarlas.
 * Cada una conserva su botón «Descargar» por si la persona quiere bajarla.
 * Clic en la imagen: se abre en el visor de adjuntos (zoom, siguiente, anterior).
 */
import type { AttachmentInfo } from '../../types';

const TIPOS_VISIBLES = /^image\/(png|jpe?g|gif|webp|bmp)$/i;
const EXTENSIONES_VISIBLES = /\.(png|jpe?g|gif|webp|bmp)$/i;
// Una foto de celular pesa 3–8 MB; más allá de esto se deja solo como adjunto.
const BYTES_MAX = 15 * 1024 * 1024;
const MAXIMO = 20;

function esImagenVisible(a: AttachmentInfo): boolean {
  if (a.is_inline || a.size > BYTES_MAX) return false;
  return TIPOS_VISIBLES.test(a.content_type || '') || EXTENSIONES_VISIBLES.test(a.filename || '');
}

function ruta(tipo: 'preview' | 'attachment', folder: string, uid: number, a: AttachmentInfo): string {
  return `/api/mail/${tipo}/${encodeURIComponent(folder)}/${uid}/${a.part_number}/${encodeURIComponent(a.filename)}`;
}

export function ImagenesEnCuerpo({ folder, uid, attachments, onAbrir }: {
  folder: string;
  uid: number;
  attachments: AttachmentInfo[];
  onAbrir?: (indice: number) => void;
}) {
  const imagenes = (attachments || [])
    .map((a, indice) => ({ a, indice }))
    .filter(({ a }) => esImagenVisible(a))
    .slice(0, MAXIMO);
  if (!imagenes.length) return null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 16 }}>
      {imagenes.map(({ a, indice }) => (
        <figure key={`${a.part_number}-${a.filename}`} style={{ margin: 0 }}>
          <img
            src={ruta('preview', folder, uid, a)}
            alt={a.filename}
            loading="lazy"
            onClick={() => onAbrir?.(indice)}
            style={{ display: 'block', maxWidth: '100%', maxHeight: 900, height: 'auto', borderRadius: 4, border: '1px solid #edebe9', cursor: onAbrir ? 'zoom-in' : 'default' }}
          />
          <figcaption style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 4, fontSize: 11, color: '#605e5c' }}>
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 320 }} title={a.filename}>{a.filename}</span>
            <a href={ruta('attachment', folder, uid, a)} download={a.filename} style={{ color: '#0078d4', textDecoration: 'none', fontWeight: 600 }}>
              Descargar
            </a>
          </figcaption>
        </figure>
      ))}
    </div>
  );
}
