// Pide la propuesta al asistente de IA (VM 170) y la va entregando mientras se genera (SSE).
import type { ModoRedaccion } from './modos';

type Avisos = {
  alAvanzar: (html: string) => void;
  alTerminar: (html: string) => void;
  alFallar: (mensaje: string) => void;
};

export async function pedirRedaccion(
  datos: { text: string; modo: ModoRedaccion; fragmento: boolean; asunto?: string },
  avisos: Avisos,
  senal: AbortSignal,
) {
  let res: Response;
  try {
    res = await fetch('/api/ia/redactar/stream', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(datos),
      signal: senal,
    });
  } catch {
    if (!senal.aborted) avisos.alFallar('No se pudo conectar con el asistente de IA.');
    return;
  }
  if (!res.ok || !res.body) {
    avisos.alFallar(res.status === 413 ? 'El texto es muy largo: selecciona una parte.' : 'El asistente de IA no respondió. Intente de nuevo.');
    return;
  }

  const lector = res.body.getReader();
  const decodificador = new TextDecoder();
  let pendiente = '';
  let terminado = false;
  try {
    for (;;) {
      const { value, done } = await lector.read();
      if (done) break;
      pendiente += decodificador.decode(value, { stream: true });
      const eventos = pendiente.split('\n\n');
      pendiente = eventos.pop() || '';
      for (const ev of eventos) {
        const linea = ev.trim();
        if (!linea.startsWith('data: ')) continue;
        let d: { type: string; html?: string; message?: string };
        try { d = JSON.parse(linea.slice(6)); } catch { continue; }
        if (d.type === 'delta') avisos.alAvanzar(d.html || '');
        else if (d.type === 'done') { terminado = true; avisos.alTerminar(d.html || ''); }
        else if (d.type === 'error') { terminado = true; avisos.alFallar(d.message || 'El asistente de IA no está disponible.'); }
      }
    }
  } catch {
    if (senal.aborted) return;
  }
  if (!terminado && !senal.aborted) avisos.alFallar('La respuesta se cortó. Intente de nuevo.');
}
