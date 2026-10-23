import { api } from '../../api/client';
import { showToast } from '../common/Toast';
import { motivoDestinoInvalido, rutaDestino } from './rutasEspacio';

/* Mover o copiar UN elemento a una carpeta. Es la única puerta: la usan el diálogo
   «Mover a…» / «Copiar a…» y el arrastre de la vista dividida, con los mismos avisos.
   Entre espacios distintos (propio ↔ unidad) hace lo mismo que el diálogo: lo que el
   servidor decida para esa operación. Devuelve true si se hizo. */

export type AccionDestino = 'mover' | 'copiar';

export async function moverOCopiar(
  accion: AccionDestino, item: { ruta: string; nombre: string }, carpeta: string,
): Promise<boolean> {
  const motivo = motivoDestinoInvalido(item.ruta, carpeta, item.nombre);
  if (motivo) { showToast(motivo); return false; }
  try {
    await api.post(`/almacen/archivos/${accion}`, { origen: item.ruta, destino: rutaDestino(carpeta, item.nombre) });
    showToast(accion === 'mover' ? 'Movido' : 'Copiado');
    return true;
  } catch {
    showToast(`No se pudo ${accion}`);
    return false;
  }
}
