/**
 * T-73 · Búsqueda dentro de la copia local (sin conexión).
 *
 * Sin red, la lista cae a lo descargado (offlineStore) y antes se mostraba entera, sin aplicar
 * el texto buscado. Aquí se filtra esa copia por asunto, remitente, destinatarios, vista previa
 * y texto del cuerpo, con los operadores sencillos del buscador: from:, to:, subject: y
 * has:attachment. Lo que no lleva operador debe aparecer en alguno de los campos.
 *
 * «Todas las carpetas» (Virtual.Todo) no tiene copia local: sin red se busca en la carpeta
 * real en la que estaba la persona antes de buscar en todo (carpetaAnterior).
 */
import type { OfflineMessage } from './offlineStore';
import { CARPETA_TODO, carpetaAnterior } from './busquedaGlobal';

interface Consulta {
  libres: string[];
  from: string[];
  to: string[];
  subject: string[];
  conAdjunto: boolean;
}

const normalizar = (t: string | null | undefined) =>
  (t || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');

/** Separa la consulta en palabras, respetando "frases entre comillas" y los operadores. */
function interpretar(q: string): Consulta {
  const c: Consulta = { libres: [], from: [], to: [], subject: [], conAdjunto: false };
  const partes = q.match(/(\w+:)?"[^"]*"|\S+/g) || [];
  for (const parte of partes) {
    const m = /^(\w+):(.*)$/.exec(parte);
    const valor = normalizar((m ? m[2] : parte).replace(/"/g, '')).trim();
    const op = m ? m[1].toLowerCase() : '';
    if (op === 'has' && /^(attachment|adjunto)s?$/.test(valor)) { c.conAdjunto = true; continue; }
    if (!valor) continue;
    if (op === 'from' || op === 'de') c.from.push(valor);
    else if (op === 'to' || op === 'para') c.to.push(valor);
    else if (op === 'subject' || op === 'asunto') c.subject.push(valor);
    else c.libres.push(normalizar(parte.replace(/"/g, '')));
  }
  return c;
}

export function coincide(msg: OfflineMessage, q: string): boolean {
  const c = interpretar(q);
  const de = normalizar(msg.from);
  const para = normalizar(`${msg.to || ''} ${msg.cc || ''}`);
  const asunto = normalizar(msg.subject);
  if (c.conAdjunto && !msg.has_attachments) return false;
  if (!c.from.every((v) => de.includes(v))) return false;
  if (!c.to.every((v) => para.includes(v))) return false;
  if (!c.subject.every((v) => asunto.includes(v))) return false;
  if (c.libres.length === 0) return true;
  const todo = `${asunto} ${de} ${para} ${normalizar(msg.snippet)} ${normalizar(msg.text_body)}`;
  return c.libres.every((v) => todo.includes(v));
}

/** Carpeta de la copia local que corresponde a la abierta (Virtual.Todo no tiene copia). */
export function carpetaLocal(carpeta: string): string {
  return carpeta === CARPETA_TODO ? carpetaAnterior() : carpeta;
}

export function filtrarCopiaLocal(mensajes: OfflineMessage[], q: string): OfflineMessage[] {
  const texto = q.trim();
  return texto ? mensajes.filter((m) => coincide(m, texto)) : mensajes;
}
