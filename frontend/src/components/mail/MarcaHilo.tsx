import { esRespondido, esReenviado } from '../../lib/marcaHilo';

/**
 * MarcaHilo.tsx — Icono de «respondido» (↩) / «reenviado» (↪) en la fila de la lista (25/11/2026).
 *
 * Pedido de Gerencia: que en Enviados y Recibidos se vea el signo, como en Zimbra. Solo presenta;
 * la detección vive en lib/marcaHilo.ts y «mostrar» (limitarlo a Enviados/Recibidos) lo decide
 * quien lo usa (MessageList), según el tipo de carpeta. Colores como Outlook: respuesta en morado,
 * reenvío en azul.
 */
export function MarcaHilo({ flags, mostrar }: { flags?: string[] | null; mostrar: boolean }) {
  if (!mostrar) return null;
  const respondido = esRespondido(flags);
  const reenviado = esReenviado(flags);
  if (!respondido && !reenviado) return null;
  return (
    <>
      {respondido && (
        <svg className="w-[12px] h-[12px] text-[#8764b8] shrink-0" fill="currentColor" viewBox="0 0 24 24">
          <title>Respondido</title>
          <path d="M10 9V5l-7 7 7 7v-4.1c5 0 8.5 1.6 11 5.1-1-5-4-10-11-11z" />
        </svg>
      )}
      {reenviado && (
        <svg className="w-[12px] h-[12px] text-[#0078d4] shrink-0" fill="currentColor" viewBox="0 0 24 24">
          <title>Reenviado</title>
          <path d="M14 9V5l7 7-7 7v-4.1C9 13.8 5.5 15.4 3 18.9c1-5 4-10 11-11z" />
        </svg>
      )}
    </>
  );
}
