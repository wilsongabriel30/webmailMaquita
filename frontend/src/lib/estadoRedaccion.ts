/**
 * Lo que hay en pantalla en una ventana de redacción, conservado mientras está minimizada.
 *
 * Al abrir otro correo o cambiar de carpeta, la ventana se minimiza y el panel se desmonta:
 * todo lo que vivía en su estado (destinatarios, CC/CCO, adjuntos, texto) se perdía y, al
 * volver, el panel se rearmaba con los datos con que se abrió. Aquí se guarda una copia en
 * memoria al desmontar y se recupera al volver. Además se manda el borrador al servidor en
 * ese momento, sin esperar al guardado automático de 30 s.
 */
import { api } from '../api/client';
import { huellaAdjuntos, type ArchivoAdjunto } from './adjuntosBorrador';

export interface EstadoRedaccion {
  to: string;
  cc: string;
  bcc: string;
  subject: string;
  showCc: boolean;
  showBcc: boolean;
  fromEmail: string;
  /** HTML del editor (sin firma ni texto citado). */
  cuerpoHtml: string;
  quotedHtml: string;
  signatureHtml: string;
  attachments: ArchivoAdjunto[];
  /** Huella de los adjuntos tal como quedaron en el último borrador guardado. */
  huellaGuardada: string;
}

const estados = new Map<string, EstadoRedaccion>();

export function guardarEstadoRedaccion(id: string, estado: EstadoRedaccion): void {
  estados.set(id, estado);
}

export function leerEstadoRedaccion(id: string): EstadoRedaccion | undefined {
  return estados.get(id);
}

export function olvidarEstadoRedaccion(id: string): void {
  estados.delete(id);
}

export function olvidarTodasLasRedacciones(): void {
  estados.clear();
}

const lista = (valor: string) => valor.split(',').map(s => s.trim()).filter(Boolean);

// Un guardado por ventana a la vez. El automático (30 s), el de minimizar y el de cerrar pueden
// coincidir; si dos salen a la vez sin UID de borrador, el servidor crea dos borradores.
const colas = new Map<string, Promise<unknown>>();

/** Encadena `tarea` tras el guardado anterior de la misma ventana (si lo hay). */
export function enColaDeGuardado<T>(id: string, tarea: () => Promise<T>): Promise<T> {
  const previa = colas.get(id) ?? Promise.resolve();
  const propia = previa.catch(() => undefined).then(tarea);
  colas.set(id, propia);
  propia.finally(() => { if (colas.get(id) === propia) colas.delete(id); }).catch(() => undefined);
  return propia;
}

/** Sin destinatarios, asunto, adjuntos ni texto: no vale la pena guardar un borrador. */
export function redaccionVacia(e: Pick<EstadoRedaccion, 'to' | 'cc' | 'bcc' | 'subject' | 'cuerpoHtml' | 'attachments'>): boolean {
  const texto = e.cuerpoHtml.replace(/<img\b/gi, 'x<').replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').trim();
  return !e.to.trim() && !e.cc.trim() && !e.bcc.trim() && !e.subject.trim() && !e.attachments.length && !texto;
}

function archivoABase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1] ?? '');
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

/**
 * Guarda el borrador en el servidor. Los adjuntos solo se suben si cambiaron desde el último
 * guardado; si no, se pide al servidor que conserve los que ya tiene.
 * Devuelve el UID del borrador y la huella de adjuntos guardada, o null si no había nada.
 */
export async function guardarBorradorEnServidor(
  e: EstadoRedaccion,
  contexto: { draftUid: number | null; inReplyTo?: string; references?: string },
): Promise<{ draftUid: number | null; huella: string } | null> {
  if (redaccionVacia(e)) return null;
  const huella = huellaAdjuntos(e.attachments);
  const cambiaron = huella !== e.huellaGuardada;
  const adjuntos = cambiaron
    ? await Promise.all(e.attachments.filter(a => a.file).map(async a => ({
        filename: a.name,
        content_b64: await archivoABase64(a.file!),
        content_type: a.type || 'application/octet-stream',
      })))
    : [];
  const res = await api.post<{ draft_uid: number | null }>('/mail/drafts', {
    to: lista(e.to),
    cc: lista(e.cc),
    bcc: lista(e.bcc),
    subject: e.subject,
    // Cuerpo + cita, SIN la firma: la firma se conserva aparte y se re-aplica al reabrir,
    // para que no quede incrustada en el editor (donde se distorsiona) ni se duplique al enviar.
    html_body: e.cuerpoHtml + (e.quotedHtml || ''),
    text_body: '',
    in_reply_to: contexto.inReplyTo || '',
    references: contexto.references || '',
    existing_draft_uid: contexto.draftUid,
    attachments: adjuntos,
    mantener_adjuntos: !cambiaron && e.attachments.length > 0,
  });
  return { draftUid: res.draft_uid ?? contexto.draftUid, huella };
}
