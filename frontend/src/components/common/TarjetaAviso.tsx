// Una tarjeta de aviso (recordatorio) como en Outlook: a la izquierda el círculo para completar la tarea,
// «Aviso: <título>» y debajo el vencimiento (azul) y el recordatorio; a la derecha, en columna y separados
// por líneas, «Posponer» (azul, con menú de tiempos) y «Cerrar» (rojo).
// Para un evento del calendario: ícono de calendario, el texto del aviso y «Entrar» si hay videollamada.
import { useState } from 'react';
import { textoDia } from '../tasks/components/textoBarraAgregar';

export interface DatosTarea {
  titulo: string;
  vence?: string | null;      // ISO
  recordatorio?: string | null; // ISO
}

const POSPONER = [
  { etiqueta: '5 minutos', minutos: 5 },
  { etiqueta: '10 minutos', minutos: 10 },
  { etiqueta: '30 minutos', minutos: 30 },
  { etiqueta: '1 hora', minutos: 60 },
  { etiqueta: 'Mañana', minutos: -1 },
];

function diaDe(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const dia = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return textoDia(dia);
}

const Calendario = ({ className = '' }: { className?: string }) => (
  <svg aria-hidden="true" className={className} width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round">
    <path d="M5 4h14a2 2 0 012 2v13a2 2 0 01-2 2H5a2 2 0 01-2-2V6a2 2 0 012-2zM3 9h18M8 13h.01M12 13h.01M16 13h.01M8 17h.01M12 17h.01" />
  </svg>
);
const Campana = () => (
  <svg aria-hidden="true" width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round">
    <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 01-3.46 0" />
  </svg>
);

const botonColumna = 'flex-1 min-h-[52px] px-5 text-[15px] text-left hover:bg-[#f3f2f1] dark:hover:bg-[#3a3a3a] transition-colors';

interface Props {
  tipo: 'task' | 'event' | string | undefined;
  texto: string;
  tarea?: DatosTarea | null;
  enlace?: string;
  onCompletar?: () => void;
  onPosponer?: (minutos: number) => void;
  onEntrar?: () => void;
  onCerrar: () => void;
}

export function TarjetaAviso({ tipo, texto, tarea, enlace, onCompletar, onPosponer, onEntrar, onCerrar }: Props) {
  const [menu, setMenu] = useState(false);
  const esTarea = tipo === 'task';
  const vence = tarea?.vence ? diaDe(tarea.vence) : '';
  const recuerda = tarea?.recordatorio ? diaDe(tarea.recordatorio) : '';

  return (
    <div role="alertdialog" aria-label={esTarea ? `Aviso: ${tarea?.titulo || texto}` : texto}
      className="relative flex bg-white dark:bg-[#2d2d2d] border border-[#e1dfdd] dark:border-[#444] rounded-md shadow-[0_3px_12px_rgba(0,0,0,0.16)] animate-[fadeIn_0.2s_ease]">
      <div className="flex-1 min-w-0 flex items-center gap-4 px-5 py-4">
        {esTarea ? (
          <button type="button" onClick={onCompletar} aria-label="Marcar como completada" title="Marcar como completada"
            className="group w-[20px] h-[20px] shrink-0 rounded-full border-[1.5px] border-[#0f6cbd] flex items-center justify-center hover:bg-[#ebf3fc]">
            <svg aria-hidden="true" className="opacity-0 group-hover:opacity-100" width={11} height={11} viewBox="0 0 24 24" fill="none" stroke="#0f6cbd" strokeWidth={3}><path d="M5 13l4 4L19 7" /></svg>
          </button>
        ) : (
          <span className="text-[#0f6cbd] shrink-0"><Calendario /></span>
        )}
        <div className="min-w-0">
          <div className="text-[15px] text-[#242424] dark:text-[#e0e0e0] break-words whitespace-pre-line">
            {esTarea ? `Aviso: ${tarea?.titulo || texto}` : texto}
          </div>
          {esTarea && (vence || recuerda) && (
            <div className="flex items-center gap-1.5 mt-0.5 text-[13px]">
              {vence && <span className="inline-flex items-center gap-1 text-[#0f6cbd]"><Calendario />{vence}</span>}
              {vence && recuerda && <span aria-hidden="true" className="text-[#616161]">•</span>}
              {recuerda && <span className="inline-flex items-center gap-1 text-[#616161] dark:text-[#aaa]"><Campana />{recuerda}</span>}
            </div>
          )}
        </div>
      </div>
      <div className="flex flex-col border-l border-[#e1dfdd] dark:border-[#444] w-[156px] shrink-0">
        {esTarea && onPosponer && (
          <button type="button" aria-haspopup="menu" aria-expanded={menu} onClick={() => setMenu(!menu)}
            className={`${botonColumna} font-semibold text-[#0f6cbd] border-b border-[#e1dfdd] dark:border-[#444] rounded-tr-md`}>
            Posponer
          </button>
        )}
        {enlace && onEntrar && (
          <button type="button" onClick={onEntrar} title={enlace}
            className={`${botonColumna} font-semibold text-[#0f6cbd] border-b border-[#e1dfdd] dark:border-[#444] rounded-tr-md`}>
            Entrar
          </button>
        )}
        <button type="button" onClick={onCerrar} className={`${botonColumna} text-[#a4262c] dark:text-[#f1707b] rounded-br-md`}>
          Cerrar
        </button>
      </div>
      {menu && onPosponer && (
        <>
          <div className="fixed inset-0 z-[1]" onClick={() => setMenu(false)} />
          <div role="menu" aria-label="Posponer"
            className="absolute right-0 top-[52px] z-[2] w-[180px] py-1 bg-white dark:bg-[#2d2d2d] border border-[#e1dfdd] dark:border-[#444] rounded-md shadow-lg">
            {POSPONER.map(o => (
              <button key={o.etiqueta} type="button" role="menuitem" onClick={() => { setMenu(false); onPosponer(o.minutos); }}
                className="block w-full text-left px-4 py-2 text-[14px] text-[#242424] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#3a3a3a]">
                {o.etiqueta}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
