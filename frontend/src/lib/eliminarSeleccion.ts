/**
 * «Eliminar» de la barra de selección (09/11/2026).
 *
 * En «Todo el correo» y en la vista por etiqueta la lista mezcla carpetas: cada correo debe ir a la
 * papelera DESDE su carpeta real (antes se mandaban todos los uids a la carpeta actual y un uid podía
 * señalar a otro correo). Los que ya están en Papelera se eliminan definitivamente.
 */
import { api } from '../api/client';
import { agruparUidsPorCarpeta } from './carpetaReal';

export const PAPELERA = 'Trash';

/** Lotes por carpeta real con la acción que corresponde a cada una. */
export function lotesDeEliminacion(uids: number[], carpetaActual: string): Array<{ carpeta: string; uids: number[]; accion: 'delete' | 'move' }> {
  return Array.from(agruparUidsPorCarpeta(uids, carpetaActual)).map(([carpeta, lote]) => ({
    carpeta,
    uids: lote,
    accion: carpeta === PAPELERA ? 'delete' : 'move',
  }));
}

/** Devuelve true si algún correo seleccionado se eliminaría de forma definitiva. */
export function hayEliminacionDefinitiva(uids: number[], carpetaActual: string): boolean {
  return lotesDeEliminacion(uids, carpetaActual).some((l) => l.accion === 'delete');
}

export async function eliminarSeleccion(uids: number[], carpetaActual: string): Promise<void> {
  for (const lote of lotesDeEliminacion(uids, carpetaActual)) {
    await api.post(`/mail/bulk-action/${encodeURIComponent(lote.carpeta)}`, { uids: lote.uids, action: lote.accion, dest_folder: PAPELERA });
  }
}
