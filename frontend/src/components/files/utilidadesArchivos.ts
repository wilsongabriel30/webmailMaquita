import type { Item, Unidad } from './tipos';

/* Iconos, fechas y nombres que comparten el listado, la vista dividida y los diálogos. */

export const ICONOS: Record<string, string> = {
  docx: '📄', doc: '📄', odt: '📄', xlsx: '📊', xls: '📊', ods: '📊', csv: '📊',
  pptx: '📽️', ppt: '📽️', odp: '📽️', pdf: '📕', txt: '📃', md: '📃',
  jpg: '🖼️', jpeg: '🖼️', png: '🖼️', gif: '🖼️', svg: '🖼️', webp: '🖼️',
  mp4: '🎬', avi: '🎬', mkv: '🎬', mp3: '🎵', wav: '🎵', zip: '🗜️', rar: '🗜️', '7z': '🗜️',
};

export function iconoDe(item: Item): string {
  if (item.es_carpeta) return '📁';
  return ICONOS[(item.extension || '').toLowerCase()] || '📎';
}

export function fechaCorta(iso?: string): string {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString('es-EC', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
  } catch { return ''; }
}

export function carpetaDe(ruta: string): string {
  const i = ruta.lastIndexOf('/');
  return i <= 0 ? '/' : ruta.slice(0, i);
}

/** Nombre visible de la raíz de un espacio: «Mis archivos» o el nombre de la unidad. */
export function nombreRaizEspacio(unidadId: string | undefined, unidades: Unidad[]): string {
  if (!unidadId) return 'Mis archivos';
  return unidades.find(u => String(u.id) === unidadId)?.nombre || `Unidad ${unidadId}`;
}
