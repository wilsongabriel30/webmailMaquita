/**
 * Aviso arriba de «Prioritarios» cuando en «Otros» hay correo sin leer (07/11/2026, como Outlook):
 * «Otros: 4 sin leer — Banco Pichincha, Elegant Themes…  Ver». Así lo llegado hoy que la IA puso
 * en «Otros» no pasa inadvertido.
 */
import type { MessageSummary } from '../../types';

function nombreCorto(from: string): string {
  const m = (from || '').match(/^\s*"?([^"<]+?)"?\s*</);
  const nombre = (m ? m[1] : from || '').trim();
  return nombre.includes('@') ? nombre.split('@')[0] : nombre;
}

export function AvisoOtrosSinLeer({ correos, onVer }: { correos: MessageSummary[]; onVer: () => void }) {
  if (correos.length === 0) return null;
  const nombres = [...new Set(correos.map(c => nombreCorto(c.from)).filter(Boolean))].slice(0, 3);
  return (
    <button type="button" onClick={onVer}
      className="w-full flex items-center gap-2 px-4 py-1.5 text-left text-[12px] bg-[#f3f9fd] hover:bg-[#deecf9] border-b border-[#e1dfdd] text-[#323130]">
      <span className="font-semibold text-[#0078d4] shrink-0">Otros: {correos.length} sin leer</span>
      <span className="truncate text-[#605e5c]">{nombres.join(', ')}</span>
      <span className="ml-auto shrink-0 text-[#0078d4] font-medium">Ver</span>
    </button>
  );
}
