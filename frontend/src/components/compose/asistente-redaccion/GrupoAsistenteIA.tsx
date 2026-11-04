// Grupo «Asistente de IA» de la pestaña Mensaje, junto a «Párrafo»: los dos botones abren la vista
// previa en el redactor (la selección o todo el mensaje); los demás modos se eligen allí mismo.
import type { ReactNode } from 'react';
import { abrirRedaccionIA } from './modos';

const ICONO_CHISPA = 'M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z';
const ICONO_ORTOGRAFIA = 'M4 17l4-10 4 10M5.5 13.5h5M14 14l2.5 2.5L21 11';

function Boton({ icono, etiqueta, titulo, alPulsar }: { icono: ReactNode; etiqueta: string; titulo: string; alPulsar: () => void }) {
  return (
    <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={alPulsar} title={titulo}
      className="flex flex-col items-center justify-center min-w-[44px] px-[4px] rounded-[3px] transition-colors h-[62px] hover:bg-[#e1dfdd]">
      <div className="h-[24px] flex items-center justify-center">{icono}</div>
      <span className="mt-[1px] text-[10px] leading-[12px] text-[#323130] text-center whitespace-pre-line">{etiqueta}</span>
    </button>
  );
}

const Svg = ({ d }: { d: string }) => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#0078d4" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d={d} />
  </svg>
);

export function GrupoAsistenteIA({ alMejorar }: { alMejorar?: () => void }) {
  return (
    <div className="flex items-center gap-[2px]">
      <Boton icono={<Svg d={ICONO_ORTOGRAFIA} />} etiqueta={'Corregir\nortografía'}
        titulo="Corrige ortografía, tildes y puntuación, y ordena en párrafos y viñetas (el texto seleccionado o todo el mensaje)"
        alPulsar={() => abrirRedaccionIA('ortografia')} />
      <Boton icono={<Svg d={ICONO_CHISPA} />} etiqueta={'Mejorar\nredacción'}
        titulo="Propone una redacción más clara; también más formal o más breve"
        alPulsar={() => (alMejorar ? alMejorar() : abrirRedaccionIA('redaccion'))} />
    </div>
  );
}
