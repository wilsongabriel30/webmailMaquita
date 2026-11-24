/**
 * BandejaSalidaCarpeta.tsx — La «Bandeja de salida» como una carpeta más (estilo Outlook, 24/11/2026).
 *
 * Reemplaza la vieja ventana emergente que tapaba el correo. `MailView` muestra este componente
 * cuando la carpeta abierta es `CARPETA_SALIDA`: a la izquierda la lista de correos en cola / sin
 * entregar y, al pulsar uno, su contenido en el panel de lectura. Si la persona elige «Editar y
 * reenviar», el redactor se abre aquí mismo (como en el resto del correo) hasta que lo envíe o cierre.
 */
import { useState } from 'react';
import { useResponsive } from '../../../hooks/useResponsive';
import { useMailStore } from '../../../store/mailStore';
import { ComposePanel } from '../../compose/ComposePanel';
import { useColaSalida } from './useColaSalida';
import { ListaBandejaSalida } from './ListaBandejaSalida';
import { LecturaBandejaSalida } from './LecturaBandejaSalida';

export function BandejaSalidaCarpeta() {
  const { lista, cargando } = useColaSalida(true);
  const [seleccionadoId, setSeleccionadoId] = useState<string | null>(null);
  const { isMobile } = useResponsive();
  const composeWindows = useMailStore(s => s.composeWindows);
  const activeCompose = composeWindows.find(w => !w.minimized);

  // Si el correo abierto salió de la cola (enviado o descartado, aquí o en otra pestaña), `find`
  // devuelve null y el panel de lectura muestra el estado vacío; no hace falta un efecto.
  const seleccionado = lista.find(x => x.id === seleccionadoId) || null;

  const lectura = activeCompose ? (
    <ComposePanel key={activeCompose.id} win={activeCompose} />
  ) : seleccionado ? (
    <LecturaBandejaSalida item={seleccionado} onDescartado={() => setSeleccionadoId(null)} />
  ) : (
    <div className="h-full flex items-center justify-center p-8 text-center">
      <p className="text-[13px] text-[#605e5c] max-w-[320px]">
        Seleccione un correo de la bandeja de salida para verlo. Los correos en cola salen solos al
        volver la conexión.
      </p>
    </div>
  );

  // Celular: una sola columna. Con un correo abierto (o redactándose), se ve la lectura con «Volver».
  if (isMobile) {
    if (activeCompose || seleccionado) {
      return (
        <div className="flex-1 flex flex-col min-h-0 bg-white dark:bg-[#1f1f1f]">
          {!activeCompose && (
            <div className="shrink-0 flex items-center gap-2 px-3 py-1.5 border-b border-[#edebe9] bg-[#faf9f8] dark:bg-[#2a2a2a] dark:border-[#3a3a3a]">
              <button onClick={() => setSeleccionadoId(null)} className="flex items-center gap-1 text-[13px] text-[#0078d4] hover:underline">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M10.5 3L5 8l5.5 5V3z" /></svg>
                Bandeja de salida
              </button>
            </div>
          )}
          <div className="flex-1 overflow-hidden">{lectura}</div>
        </div>
      );
    }
    return (
      <div className="flex-1 flex flex-col min-h-0">
        <ListaBandejaSalida lista={lista} cargando={cargando} seleccionadoId={seleccionadoId} onSelect={(e) => setSeleccionadoId(e.id)} />
      </div>
    );
  }

  // Escritorio: lista a la izquierda + lectura/redacción a la derecha, en tarjetas como el resto del correo.
  return (
    <div className="flex-1 flex overflow-hidden min-h-0 bg-[#f3f2f1] dark:bg-[#141414]">
      <div className="flex min-h-0 my-2 ml-2 rounded-lg overflow-hidden bg-white dark:bg-[#1f1f1f] shadow-[0_1px_4px_rgba(0,0,0,0.13)] w-[360px] shrink-0">
        <ListaBandejaSalida lista={lista} cargando={cargando} seleccionadoId={seleccionadoId} onSelect={(e) => setSeleccionadoId(e.id)} />
      </div>
      <div className="flex-1 min-w-0 flex flex-col my-2 mr-2 rounded-lg overflow-hidden bg-white dark:bg-[#1f1f1f] shadow-[0_1px_4px_rgba(0,0,0,0.13)]">
        {lectura}
      </div>
    </div>
  );
}
