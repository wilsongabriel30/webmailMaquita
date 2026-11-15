/**
 * reabrirRedaccion.ts — Volver a abrir un correo que no llegó a salir, SIN perder sus adjuntos (13/11/2026).
 *
 * Se usa cuando la persona pulsa «Deshacer» tras enviar o cuando el envío falla. Antes la ventana
 * se reabría con el texto pero sin los archivos adjuntados desde el equipo. Aquí los archivos que
 * ya estaban en el redactor se entregan a la ventana nueva (lib/archivosParaRedaccion.ts) y se
 * quitan de los datos las fuentes desde las que esa ventana los volvería a descargar, para que no
 * salgan repetidos.
 */
import { useMailStore, type DraftWindow } from '../../store/mailStore';
import { dejarArchivosParaRedaccion } from '../../lib/archivosParaRedaccion';
import { borradorVigente } from '../../lib/estadoRedaccion';
import type { ComposeData } from '../../types';

/**
 * `ventanaAnterior`: la ventana que se cerró al pulsar «Enviar». La reabierta hereda su borrador
 * (el vigente, esperando a un guardado que siguiera en curso): sin eso guardaba un borrador
 * nuevo y el anterior se quedaba repetido en Borradores (13/11/2026).
 */
export function reabrirRedaccion(modo: DraftWindow['mode'], datos: ComposeData, adjuntos: { file?: File }[], ventanaAnterior?: string): void {
  if (ventanaAnterior) {
    void borradorVigente(ventanaAnterior, datos.draft_uid, 5000)
      .then(uid => reabrirRedaccion(modo, { ...datos, draft_uid: uid }, adjuntos));
    return;
  }
  const archivos = adjuntos.map(a => a.file).filter((f): f is File => !!f);
  if (!archivos.length) {
    useMailStore.getState().openCompose(modo, datos);
    return;
  }
  dejarArchivosParaRedaccion(archivos);
  useMailStore.getState().openCompose(modo, {
    ...datos, reenvio_de: undefined, adjuntos_almacen: undefined, correos_adjuntos: undefined, adjuntos_borrador: undefined,
  });
}
