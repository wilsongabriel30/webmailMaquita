/**
 * Guardado del borrador y conservación de lo escrito cuando la ventana de redacción se minimiza.
 *
 * Al abrir otro correo o cambiar de carpeta, el panel de redacción se desmonta. Este hook:
 *  - guarda una copia en memoria de lo que hay en pantalla (estadoRedaccion.ts) para retomarlo al volver;
 *  - manda el borrador al servidor en ese momento, sin esperar al guardado automático de 30 s;
 *  - ofrece `saveDraft` para el guardado automático, el botón y el cierre, con CC, CCO y adjuntos.
 */
import { useCallback, useEffect, useRef } from 'react';
import type { Editor } from '@tiptap/react';
import { useMailStore, type DraftWindow } from '../../store/mailStore';
import {
  guardarBorradorEnServidor, guardarEstadoRedaccion, leerEstadoRedaccion, type EstadoRedaccion,
} from '../../lib/estadoRedaccion';

/** Lo que el panel tiene en su estado; el cuerpo y la huella los lleva el hook. */
export type CamposRedaccion = Omit<EstadoRedaccion, 'cuerpoHtml' | 'huellaGuardada'>;

export function useRedaccionPersistente(
  win: DraftWindow,
  editor: Editor | null,
  estadoPrevio: EstadoRedaccion | undefined,
  campos: CamposRedaccion,
) {
  const updateDraftUid = useMailStore(s => s.updateDraftUid);

  // Huella de los adjuntos tal como quedaron en el último borrador guardado:
  // si no cambió, el guardado pide al servidor conservar los archivos en vez de resubirlos.
  const huellaGuardadaRef = useRef<string>(estadoPrevio?.huellaGuardada ?? '');

  // Último HTML del editor. Se lleva aparte porque al desmontar el panel el editor ya puede
  // estar destruido y no se le puede pedir el contenido.
  const cuerpoRef = useRef<string>(estadoPrevio?.cuerpoHtml ?? '');
  useEffect(() => {
    if (!editor) return;
    const alCambiar = () => { cuerpoRef.current = editor.getHTML(); };
    editor.on('update', alCambiar);
    return () => { editor.off('update', alCambiar); };
  }, [editor]);

  // Foto de lo que hay en pantalla (se renueva en cada render para no leer valores viejos).
  const instantaneaRef = useRef<() => EstadoRedaccion>(() => ({ ...campos, cuerpoHtml: '', huellaGuardada: '' }));
  instantaneaRef.current = () => ({
    ...campos,
    cuerpoHtml: cuerpoRef.current,
    huellaGuardada: huellaGuardadaRef.current,
  });

  const guardarDesdeInstantanea = useCallback(async (estado: EstadoRedaccion) => {
    const actual = useMailStore.getState().composeWindows.find(w => w.id === win.id);
    const res = await guardarBorradorEnServidor(estado, {
      draftUid: actual?.draftUid ?? win.draftUid,
      inReplyTo: win.data.in_reply_to,
      references: win.data.references,
    });
    if (!res) return;
    huellaGuardadaRef.current = res.huella;
    const enMemoria = leerEstadoRedaccion(win.id);
    if (enMemoria) enMemoria.huellaGuardada = res.huella;
    if (res.draftUid) updateDraftUid(win.id, res.draftUid);
  }, [win.id, win.draftUid, win.data.in_reply_to, win.data.references, updateDraftUid]);

  const saveDraft = useCallback(async () => {
    try {
      if (editor && !editor.isDestroyed) cuerpoRef.current = editor.getHTML();
      await guardarDesdeInstantanea(instantaneaRef.current());
    } catch {
      /* el guardado automatico es de cortesia: si falla, el texto sigue en pantalla y se
         reintenta en el siguiente cambio, sin interrumpir a quien escribe */
    }
  }, [editor, guardarDesdeInstantanea]);

  // Al desmontar: conservar lo que hay en pantalla y guardar el borrador ya.
  // Si la ventana se cerró o se envió, ya no está en el store y no hay nada que conservar.
  useEffect(() => () => {
    if (!useMailStore.getState().composeWindows.some(w => w.id === win.id)) return;
    const estado = instantaneaRef.current();
    guardarEstadoRedaccion(win.id, estado);
    guardarDesdeInstantanea(estado).catch(() => { /* queda la copia en memoria */ });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { saveDraft, cuerpoRef, huellaGuardadaRef };
}
