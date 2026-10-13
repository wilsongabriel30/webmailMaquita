/**
 * Guardado del borrador y conservación de lo escrito cuando la ventana de redacción se minimiza.
 *
 * Al abrir otro correo o cambiar de carpeta, el panel de redacción se desmonta. Este hook:
 *  - guarda una copia en memoria de lo que hay en pantalla (estadoRedaccion.ts) para retomarlo al volver;
 *  - manda el borrador al servidor en ese momento, sin esperar al guardado automático de 30 s;
 *  - ofrece `saveDraft` para el guardado automático, el botón y el cierre, con CC, CCO y adjuntos;
 *  - anota en la pestaña lo que hay en pantalla (redaccionesRecuperables.ts) para reabrirlo si la
 *    página se recarga, y guarda el borrador en cuanto cambian los adjuntos (13/10/2026).
 */
import { useCallback, useEffect, useRef } from 'react';
import type { Editor } from '@tiptap/react';
import { useMailStore, type DraftWindow } from '../../store/mailStore';
import {
  enColaDeGuardado, guardarBorradorEnServidor, guardarEstadoRedaccion, leerEstadoRedaccion, type EstadoRedaccion,
} from '../../lib/estadoRedaccion';
import { huellaAdjuntos } from '../../lib/adjuntosBorrador';
import { anotarRedaccion, registrarFuente, type RedaccionGuardada } from '../../lib/redaccionesRecuperables';

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

  // Lo que se anota en la pestaña para reabrir la ventana tras una recarga.
  const uidActual = useCallback(
    () => useMailStore.getState().composeWindows.find(w => w.id === win.id)?.draftUid ?? win.draftUid,
    [win.id, win.draftUid]);
  const paraRecuperar = useCallback((estado: EstadoRedaccion, draftUid: number | null): RedaccionGuardada => ({
    id: win.id,
    draftUid,
    to: estado.to,
    cc: estado.cc,
    bcc: estado.bcc,
    subject: estado.subject,
    html: estado.cuerpoHtml + (estado.quotedHtml || ''),
    inReplyTo: win.data.in_reply_to || '',
    references: win.data.references || '',
    actualizado: Date.now(),
  }), [win.id, win.data.in_reply_to, win.data.references]);
  const sigueAbierta = useCallback(
    () => useMailStore.getState().composeWindows.some(w => w.id === win.id), [win.id]);

  const guardarDesdeInstantanea = useCallback((estado: EstadoRedaccion) => enColaDeGuardado(win.id, async () => {
    // El UID se lee al empezar, no al encolar: el guardado anterior puede haberlo creado.
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
    if (sigueAbierta()) anotarRedaccion(paraRecuperar(estado, res.draftUid ?? uidActual()));
  }), [win.id, win.draftUid, win.data.in_reply_to, win.data.references, updateDraftUid, sigueAbierta, paraRecuperar, uidActual]);

  const saveDraft = useCallback(async () => {
    try {
      if (editor && !editor.isDestroyed) cuerpoRef.current = editor.getHTML();
      await guardarDesdeInstantanea(instantaneaRef.current());
    } catch {
      /* el guardado automatico es de cortesia: si falla, el texto sigue en pantalla y se
         reintenta en el siguiente cambio, sin interrumpir a quien escribe */
    }
  }, [editor, guardarDesdeInstantanea]);

  // Foto al momento para la pestaña: la piden la anotación periódica y la salida de la página.
  const fotoRef = useRef<() => RedaccionGuardada | null>(() => null);
  fotoRef.current = () => {
    if (!sigueAbierta()) return null;
    if (editor && !editor.isDestroyed) cuerpoRef.current = editor.getHTML();
    return paraRecuperar(instantaneaRef.current(), uidActual());
  };
  useEffect(() => registrarFuente(win.id, () => fotoRef.current()), [win.id]);

  // Anotar al escribir (texto, destinatarios, asunto), sin esperar al guardado de 30 s.
  const anotarPronto = useRef<ReturnType<typeof setTimeout> | null>(null);
  const programarAnotacion = useCallback(() => {
    if (anotarPronto.current) clearTimeout(anotarPronto.current);
    anotarPronto.current = setTimeout(() => {
      const r = fotoRef.current();
      if (r) anotarRedaccion(r);
    }, 1500);
  }, []);
  useEffect(() => {
    if (!editor) return;
    editor.on('update', programarAnotacion);
    return () => { editor.off('update', programarAnotacion); };
  }, [editor, programarAnotacion]);
  useEffect(programarAnotacion, [campos.to, campos.cc, campos.bcc, campos.subject, programarAnotacion]);
  useEffect(() => () => { if (anotarPronto.current) clearTimeout(anotarPronto.current); }, []);

  // Un adjunto nuevo se guarda en el borrador del servidor enseguida: si la página se recarga,
  // la ventana se reabre desde ese borrador y el archivo tiene que estar ahí.
  const huellaEnPantalla = huellaAdjuntos(campos.attachments);
  useEffect(() => {
    if (!campos.attachments.length || huellaEnPantalla === huellaGuardadaRef.current) return;
    const t = setTimeout(() => { saveDraft(); }, 1000);
    return () => clearTimeout(t);
  }, [huellaEnPantalla, campos.attachments.length, saveDraft]);

  // Al desmontar: conservar lo que hay en pantalla y guardar el borrador ya.
  // Si la ventana se cerró o se envió, ya no está en el store y no hay nada que conservar.
  useEffect(() => () => {
    if (!useMailStore.getState().composeWindows.some(w => w.id === win.id)) return;
    const estado = instantaneaRef.current();
    guardarEstadoRedaccion(win.id, estado);
    anotarRedaccion(paraRecuperar(estado, uidActual()));
    guardarDesdeInstantanea(estado).catch(() => { /* queda la copia en memoria */ });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { saveDraft, cuerpoRef, huellaGuardadaRef };
}
