/**
 * marcarCarpetaLeida.ts — «Marcar todo como leído» de una carpeta entera (05/11/2026).
 *
 * Antes se pedía UNA página (`per_page=999`, que el servidor recorta a 300) y se marcaban solo
 * los no leídos que cayeran en esos 300 correos más recientes. En un buzón con 28.000 correos y
 * más de mil sin leer repartidos por el historial, cada clic marcaba unos pocos y el aviso seguía
 * diciendo «1.000+ sin leer» (reporte de Viviana Jines, serviciosgenerales@).
 *
 * Ahora se piden SOLO los no leídos (`is_unread=true`) de 300 en 300 y se marcan por tandas de
 * 500 (límite del servidor) hasta que no quede ninguno, con un tope de seguridad.
 */
import { api } from '../../api/client';

const POR_PAGINA = 300;      // tope del servidor en /mail/messages
const TANDA = 500;           // tope del servidor en /mail/bulk-action
const MAX_VUELTAS = 200;     // 60.000 correos como máximo por clic

interface Pagina { messages: { uid: number; seen: boolean }[]; total: number }

export async function marcarCarpetaLeida(carpeta: string): Promise<number> {
  const c = encodeURIComponent(carpeta);
  let marcados = 0;
  for (let vuelta = 0; vuelta < MAX_VUELTAS; vuelta++) {
    const res = await api.get<Pagina>(`/mail/messages/${c}?per_page=${POR_PAGINA}&is_unread=true`);
    const uids = res.messages.filter(m => !m.seen).map(m => m.uid);
    if (uids.length === 0) break;
    for (let i = 0; i < uids.length; i += TANDA) {
      const tanda = uids.slice(i, i + TANDA);
      await api.post(`/mail/bulk-action/${c}`, { uids: tanda, action: 'mark_read', dest_folder: '' });
      marcados += tanda.length;
    }
    if (uids.length < POR_PAGINA) break;
  }
  return marcados;
}
