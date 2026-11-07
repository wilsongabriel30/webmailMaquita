// Soltar correos en el ícono Tareas (NavRail): una tarea por correo, con el enlace para abrirlo.
// El arrastre lo arma MessageList en 'application/x-mail-meta'.
import { api } from '../../api/client';
import { showToast } from '../common/Toast';

interface CorreoMeta {
  uid?: number;
  folder?: string;
  subject?: string;
  from?: string;
  message_id?: string;
}

interface MetaArrastre extends CorreoMeta {
  correos?: CorreoMeta[];
}

/** Lo que pide el servidor (app/tasks/desde_correo.py). Máximo 50 por vez. */
export const MAX_CORREOS = 50;

export function correosDelArrastre(meta: MetaArrastre): { carpeta: string; uid: number; asunto: string; remitente: string; message_id: string }[] {
  const lista = Array.isArray(meta.correos) && meta.correos.length ? meta.correos : [meta];
  return lista
    .filter(c => typeof c.uid === 'number' && c.uid > 0 && !!c.folder)
    .slice(0, MAX_CORREOS)
    .map(c => ({
      carpeta: c.folder as string,
      uid: c.uid as number,
      asunto: (c.subject || '').slice(0, 2000),
      remitente: (c.from || '').slice(0, 1000),
      message_id: (c.message_id || '').slice(0, 998),
    }));
}

function aviso(creadas: { title: string }[], repetidas: number, recortados: number): string {
  const partes: string[] = [];
  if (creadas.length === 1) partes.push(`Tarea creada: ${creadas[0].title.slice(0, 60)}`);
  else if (creadas.length > 1) partes.push(`${creadas.length} tareas creadas en «Tareas»`);
  if (repetidas === 1) partes.push('un correo ya tenía su tarea abierta');
  else if (repetidas > 1) partes.push(`${repetidas} correos ya tenían su tarea abierta`);
  if (recortados > 0) partes.push(`se tomaron solo los primeros ${MAX_CORREOS} correos`);
  return partes.join('; ') || 'No se creó ninguna tarea';
}

export async function crearTareasDesdeCorreo(metaTexto: string): Promise<void> {
  let meta: MetaArrastre;
  try {
    meta = JSON.parse(metaTexto);
  } catch {
    return; // lo arrastrado no era un correo legible
  }
  const correos = correosDelArrastre(meta);
  if (!correos.length) {
    showToast('No se pudo leer el correo arrastrado');
    return;
  }
  const total = Array.isArray(meta.correos) ? meta.correos.length : 1;
  try {
    const r = await api.post<{ creadas: { title: string }[]; repetidas: number }>('/tasks/desde-correo', { correos });
    showToast(aviso(r.creadas, r.repetidas, Math.max(0, total - correos.length)));
    window.dispatchEvent(new CustomEvent('refresh-tasks'));
  } catch (e) {
    showToast(`No se pudo crear la tarea: ${e instanceof Error ? e.message : 'error desconocido'}`);
  }
}
