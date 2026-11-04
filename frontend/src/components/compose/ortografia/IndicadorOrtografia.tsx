/**
 * Indicador pequeño y claro del idioma del corrector: «Ortografía: Español (Ecuador)».
 * Un clic lo cambia (Español ↔ Inglés). Es un botón real, con texto legible (13 px), foco
 * visible y un aviso para lectores de pantalla cuando el idioma cambia solo.
 */
import { NOMBRE, otro, type IdiomaOrtografia } from './idiomas';

export function IndicadorOrtografia({ idioma, manual, onCambiar }: {
  idioma: IdiomaOrtografia;
  manual: boolean;
  onCambiar: (idioma: IdiomaOrtografia) => void;
}) {
  const siguiente = otro(idioma);
  return (
    <div className="flex items-center justify-end px-4 py-1 border-t border-[#edebe9] shrink-0">
      <button type="button" onClick={() => onCambiar(siguiente)}
        title={`Corrector ortográfico en ${NOMBRE[idioma]}${manual ? ' (elegido por usted)' : ' (automático)'}. Pulse para cambiar a ${NOMBRE[siguiente]}.`}
        aria-label={`Ortografía: ${NOMBRE[idioma]}. Pulse para cambiar a ${NOMBRE[siguiente]}.`}
        className="text-[13px] text-[#323130] border border-[#c8c6c4] rounded px-2.5 py-0.5 bg-white hover:bg-[#f3f2f1] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0078d4]">
        <span className="text-[#605e5c]">Ortografía:</span>{' '}
        <span className="font-semibold">{NOMBRE[idioma]}</span>
      </button>
      <span className="sr-only" aria-live="polite">{`Corrector ortográfico en ${NOMBRE[idioma]}`}</span>
    </div>
  );
}
