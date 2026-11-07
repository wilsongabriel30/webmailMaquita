// Correos de una etiqueta para la vista «Etiqueta: X» de la barra lateral (05/11/2026).
//
// El servidor devuelve en /mail/labels/{id}/messages solo pares carpeta+uid. Si existe el endpoint
// con resúmenes (/mail/labels/{id}/mensajes, propuesto) se usa; si no, se pide el resumen de cada
// correo (sin marcarlo como leído), de a pocos a la vez. Se recuerda 40 s por página para que el
// sondeo de la lista no repita todo el trabajo.
import { api } from '../api/client';
import type { MessageFull, MessageSummary } from '../types';

interface Ref { folder: string; uid: number }
interface RespuestaRefs { label: { id: number; name: string; color: string }; total: number; messages: Ref[] }
export interface PaginaEtiqueta { messages: MessageSummary[]; total: number; page: number }

const VIGENCIA_MS = 40000;
const PARALELO = 4;
const cache = new Map<string, { t: number; datos: PaginaEtiqueta }>();

export function olvidarCorreosDeEtiqueta(): void {
  cache.clear();
}

function resumenDe(m: MessageFull, folder: string): MessageSummary {
  const texto = (m.snippet || m.text_body || '').replace(/\s+/g, ' ').trim().slice(0, 160);
  return { ...m, folder, snippet: texto };
}

async function resumenesUnoAUno(refs: Ref[]): Promise<MessageSummary[]> {
  const salida: (MessageSummary | null)[] = new Array(refs.length).fill(null);
  let i = 0;
  const trabajador = async () => {
    while (i < refs.length) {
      const idx = i++;
      const r = refs[idx];
      try {
        const m = await api.get<MessageFull>(`/mail/message/${encodeURIComponent(r.folder)}/${r.uid}?marcar_leido=false`);
        salida[idx] = resumenDe(m, r.folder);
      } catch {
        salida[idx] = null; // el correo ya no está (movido o borrado): no se muestra
      }
    }
  };
  await Promise.all(Array.from({ length: Math.min(PARALELO, refs.length) }, trabajador));
  return salida.filter((m): m is MessageSummary => m !== null);
}

export async function cargarCorreosDeEtiqueta(labelId: number, page: number, perPage: number): Promise<PaginaEtiqueta> {
  const clave = `${labelId}:${page}:${perPage}`;
  const guardado = cache.get(clave);
  if (guardado && Date.now() - guardado.t < VIGENCIA_MS) return guardado.datos;

  let datos: PaginaEtiqueta | null = null;
  try {
    const r = await api.get<{ messages?: MessageSummary[]; total?: number }>(`/mail/labels/${labelId}/mensajes?page=${page}&per_page=${perPage}`);
    if (r && Array.isArray(r.messages)) datos = { messages: r.messages, total: r.total ?? r.messages.length, page };
  } catch {
    datos = null; // el endpoint con resúmenes aún no existe: se arma aquí
  }
  if (!datos) {
    const refs = await api.get<RespuestaRefs>(`/mail/labels/${labelId}/messages?page=${page}&per_page=${perPage}`);
    datos = { messages: await resumenesUnoAUno(refs.messages || []), total: refs.total || 0, page };
  }
  cache.set(clave, { t: Date.now(), datos });
  return datos;
}
