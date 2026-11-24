/**
 * ListaBandejaSalida.tsx — La lista de la bandeja de salida en el panel central (24/11/2026).
 *
 * Es la vista de «carpeta» de la bandeja de salida: una fila por correo en cola o sin entregar,
 * con su estado, antigüedad e intentos. Al pulsar una fila se abre el correo en el panel de lectura
 * (como cualquier carpeta), no en una ventana emergente.
 */
import { type OutboxEmail } from '../../../lib/offlineStore';
import { TEXTO_ESTADO } from '../../../lib/syncQueue';
import { esIlegible } from '../../../lib/colaSalidaLegible';
import { antiguedadCorta } from './formatoSalida';

interface Props {
  lista: OutboxEmail[];
  cargando: boolean;
  seleccionadoId: string | null;
  onSelect: (e: OutboxEmail) => void;
}

export function ListaBandejaSalida({ lista, cargando, seleccionadoId, onSelect }: Props) {
  return (
    <div className="message-list-container flex flex-col h-full min-h-0 w-full bg-white dark:bg-[#1f1f1f]">
      <div className="shrink-0 flex items-center gap-2 px-4 py-2.5 border-b border-[#edebe9] dark:border-[#3a3a3a]">
        <svg className="w-[16px] h-[16px] text-[#605e5c]" fill="none" stroke="currentColor" strokeWidth={1.6} viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 10l18-7-7 18-2.5-7.5L3 10z" />
        </svg>
        <h2 className="text-[15px] font-semibold text-[#323130] dark:text-[#e0e0e0]">Bandeja de salida</h2>
        <span className="text-[12px] text-[#605e5c]">
          {cargando ? 'cargando…' : `${lista.length} ${lista.length === 1 ? 'correo' : 'correos'}`}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto">
        {lista.length === 0 && !cargando && (
          <p className="px-5 py-10 text-[13px] text-[#605e5c] text-center">
            No hay correos en cola. Lo que escriba sin conexión aparecerá aquí y saldrá solo al volver la red.
          </p>
        )}
        {lista.map((e) => {
          const ilegible = esIlegible(e);
          const activo = e.id === seleccionadoId;
          return (
            <button
              type="button"
              key={e.id}
              onClick={() => onSelect(e)}
              className={`w-full text-left px-4 py-2.5 border-b border-[#f3f2f1] dark:border-[#333] transition-colors
                ${activo ? 'bg-[#eaf3fb] dark:bg-[#243447]' : 'hover:bg-[#f5f9fd] dark:hover:bg-[#2a2a2a]'}`}
            >
              <div className="flex items-baseline gap-2">
                <span className="text-[14px] font-semibold text-[#323130] dark:text-[#e0e0e0] truncate flex-1">
                  {e.subject || '(sin asunto)'}
                </span>
                <span className="shrink-0 text-[11px] text-[#605e5c] tabular-nums">{antiguedadCorta(e.createdAt)}</span>
              </div>
              <div className="text-[12px] text-[#605e5c] truncate">Para: {(e.to || []).join(', ') || '—'}</div>
              <div className="mt-1 flex items-center gap-2">
                {ilegible ? (
                  <span className="text-[11px] font-semibold text-[#a4262c]">No se puede leer</span>
                ) : e.status === 'failed' ? (
                  <span className="text-[11px] font-bold text-[#a4262c]">{TEXTO_ESTADO.failed}</span>
                ) : e.status === 'sending' ? (
                  <span className="text-[11px] text-[#605e5c]">{TEXTO_ESTADO.sending}</span>
                ) : (
                  <span className="text-[11px] text-[#005a9e]">{TEXTO_ESTADO[e.status]}</span>
                )}
                {!ilegible && (e.retries || 0) > 0 && (
                  <span className="text-[11px] text-[#605e5c]">· {e.retries} {e.retries === 1 ? 'intento' : 'intentos'}</span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
