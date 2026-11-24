/**
 * BandejaSalida.tsx — La fila «Bandeja de salida» del riel de carpetas (24/11/2026).
 *
 * La bandeja de salida es ahora una CARPETA más (components/mail/salida/): esta fila solo navega a
 * ella y muestra cuántos correos hay en cola. Antes abría una ventana emergente que tapaba el correo.
 * El motor de la cola sigue en lib/syncQueue.ts + lib/offlineStore.ts (un correo escrito sin conexión
 * se guarda y se reintenta al reconectar).
 *
 * En la app (modo Teams) la fila está siempre visible, como en Outlook; en la web solo aparece si hay
 * algo en cola (en la web basta el aviso de la franja de conexión).
 */
import { useColaSalida } from './salida/useColaSalida';
import { useMailStore } from '../../store/mailStore';
import { esClienteEscritorio } from '../../lib/clienteEscritorio';
import { CARPETA_SALIDA } from '../../lib/carpetaSalida';

/** Fila «Bandeja de salida» del panel de carpetas. */
export function EntradaBandejaSalida() {
  const enApp = esClienteEscritorio();
  const { lista } = useColaSalida(true);
  const currentFolder = useMailStore(s => s.currentFolder);
  const setCurrentFolder = useMailStore(s => s.setCurrentFolder);

  // En la app siempre visible; en la web solo si hay correos en cola.
  if (!enApp && lista.length === 0) return null;

  const activo = currentFolder === CARPETA_SALIDA;
  const fallidos = lista.filter((e) => e.status === 'failed').length;
  const enCola = lista.length - fallidos;
  return (
    <button type="button" onClick={() => setCurrentFolder(CARPETA_SALIDA)}
      title={fallidos > 0 ? 'Hay correos que no se pudieron enviar: ábralos para corregirlos' : 'Correos escritos sin conexión que saldrán al volver la red'}
      className={`w-full flex items-center gap-1.5 px-2 py-[4px] rounded text-[13px] ${activo
        ? 'bg-[#e1effb] text-[#005a9e] font-semibold dark:bg-[#243447] dark:text-[#4aa3e0]'
        : 'text-[#323130] hover:bg-[#edebe9] dark:text-[#e0e0e0] dark:hover:bg-[#333]'}`}>
      <span className="w-[12px] shrink-0" />
      <svg className={`w-[15px] h-[15px] shrink-0 ${activo ? 'text-[#005a9e] dark:text-[#4aa3e0]' : 'text-[#605e5c]'}`} fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 10l18-7-7 18-2.5-7.5L3 10z" />
      </svg>
      <span className="truncate flex-1 text-left">Bandeja de salida</span>
      {fallidos > 0 && <span className="text-[11px] font-bold text-[#a4262c]" title="Envíos que fallaron">!</span>}
      {enCola > 0 && <span className="text-[11px] font-bold text-[#005a9e] tabular-nums">{enCola}</span>}
    </button>
  );
}
