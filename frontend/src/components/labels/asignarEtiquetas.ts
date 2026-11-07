// Asignar o quitar una etiqueta a varios correos, cada uno en su carpeta real (05/11/2026).
import { api } from '../../api/client';
import { carpetaEtiquetable } from '../../lib/carpetaReal';

export interface CorreoRef { folder?: string; uid: number }

/** Devuelve cuántos correos se atendieron y cuántos se omitieron (buzón virtual). */
export async function asignarEtiquetaA(
  labelId: number,
  correos: CorreoRef[],
  carpetaActual: string,
  quitar = false,
): Promise<{ hechos: number; omitidos: number }> {
  const porCarpeta = new Map<string, number[]>();
  let omitidos = 0;
  for (const c of correos) {
    const f = carpetaEtiquetable(c, carpetaActual);
    if (!f) { omitidos++; continue; }
    const lote = porCarpeta.get(f) || [];
    lote.push(c.uid);
    porCarpeta.set(f, lote);
  }
  let hechos = 0;
  for (const [folder, uids] of porCarpeta) {
    await api.post(`/mail/labels/${labelId}/${quitar ? 'unassign' : 'assign'}`, { folder, uids });
    hechos += uids.length;
  }
  if (hechos) {
    window.dispatchEvent(new CustomEvent('refresh-message-labels'));
    window.dispatchEvent(new CustomEvent('refresh-labels'));
  }
  return { hechos, omitidos };
}

/** Etiquetas (ids) que tiene UN correo. */
export async function etiquetasDelCorreo(folder: string, uid: number): Promise<number[]> {
  const r = await api.get<{ message_labels?: Record<string, { id: number }[]> }>(
    `/mail/labels/messages/${encodeURIComponent(folder)}?uids=${uid}`,
  );
  return ((r && r.message_labels && r.message_labels[String(uid)]) || []).map((l) => Number(l.id));
}
