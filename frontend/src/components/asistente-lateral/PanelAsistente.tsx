/**
 * Panel lateral del asistente de IA: acciones sobre el correo abierto y conversación con
 * el buzón. En escritorio ocupa una columna a la derecha; en el móvil cubre la pantalla.
 * Se abre y cierra con el botón de la barra superior (BotonAsistente) o con Escape.
 */
import { useEffect } from 'react';
import { useAsistenteStore } from './asistenteStore';
import { AccionesCorreoActual } from './AccionesCorreoActual';
import { ConversacionCorreo } from './ConversacionCorreo';
import { IconoAsistente } from './IconoAsistente';

export function PanelAsistente({ movil }: { movil: boolean }) {
  const abierto = useAsistenteStore((s) => s.abierto);
  const cerrar = useAsistenteStore((s) => s.cerrar);

  useEffect(() => {
    if (!abierto) return;
    const alPulsar = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !document.querySelector('[role="dialog"]')) cerrar();
    };
    window.addEventListener('keydown', alPulsar);
    return () => window.removeEventListener('keydown', alPulsar);
  }, [abierto, cerrar]);

  if (!abierto) return null;

  const contenedor = movil
    ? 'fixed left-0 right-0 bottom-0 top-[40px] z-50 bg-white flex flex-col'
    : 'w-[360px] shrink-0 bg-white border-l border-[#edebe9] flex flex-col min-h-0';

  return (
    <aside role="complementary" aria-label="Asistente de IA" className={contenedor}>
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-[#edebe9]">
        <span className="text-[#0078d4]"><IconoAsistente className="w-5 h-5" /></span>
        <div className="flex-1 min-w-0">
          <p className="text-[14px] font-semibold text-[#323130]">Asistente</p>
          <p className="text-[11px] text-[#605e5c] truncate">IA de Maquita: tus correos no salen de nuestros servidores</p>
        </div>
        <button type="button" onClick={cerrar} title="Cerrar (Esc)" aria-label="Cerrar el asistente"
          className="w-7 h-7 rounded flex items-center justify-center text-[#605e5c] hover:bg-[#f3f2f1]">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <section aria-label="Este correo" className="border-b border-[#edebe9]">
        <h2 className="px-4 pt-3 text-[11px] font-semibold uppercase tracking-wide text-[#605e5c]">Este correo</h2>
        <AccionesCorreoActual />
      </section>

      <section aria-label="Pregúntale a tu correo" className="flex-1 flex flex-col min-h-0">
        <h2 className="px-4 pt-3 text-[11px] font-semibold uppercase tracking-wide text-[#605e5c]">Pregúntale a tu correo</h2>
        <ConversacionCorreo />
      </section>
    </aside>
  );
}
