// Etiquetas de los mensajes, pedidas por tandas.
//
// Con el scroll infinito la bandeja puede tener miles de correos cargados. Pedir las etiquetas
// de todos en UNA sola URL (?uids=1,2,3...) la hacía enorme y el servidor la rechazaba (503),
// así que las etiquetas dejaban de verse. Aquí se piden de a TAMANO_TANDA y se juntan.

import { api } from '../api/client';

export const TAMANO_TANDA = 150;

export async function cargarEtiquetasPorTandas<T>(
  folder: string,
  uids: number[],
  tamano: number = TAMANO_TANDA,
): Promise<Record<string, T[]>> {
  const resultado: Record<string, T[]> = {};
  for (let i = 0; i < uids.length; i += tamano) {
    const tanda = uids.slice(i, i + tamano);
    try {
      const res = await api.get<{ message_labels?: Record<string, T[]> }>(
        `/mail/labels/messages/${encodeURIComponent(folder)}?uids=${encodeURIComponent(tanda.join(','))}`,
      );
      Object.assign(resultado, (res && res.message_labels) || {});
    } catch {
      // una tanda fallida no debe dejar sin etiquetas a las demás
    }
  }
  return resultado;
}
