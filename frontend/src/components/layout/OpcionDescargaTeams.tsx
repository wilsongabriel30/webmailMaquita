import { esCelular, megasTeams, useManifiestoTeams } from '../../lib/teamsWindows';

/** Opción del menú del perfil, debajo de la app Android: descarga directa de la app de Windows
 *  (07/11/2026). Un clic y baja la última versión publicada. */
export default function OpcionDescargaTeams({ alPulsar }: { alPulsar?: () => void }) {
  const m = useManifiestoTeams();
  if (!m || esCelular()) return null;
  const nombre = m.nombre || 'Teams';
  const detalle = [m.version, megasTeams(m.tamano)].filter(Boolean).join(' · ');
  return (
    <a
      href={m.url}
      download
      onClick={() => alPulsar?.()}
      title={`${nombre} para Windows · versión ${detalle}`}
      className="w-full text-left px-4 py-2 text-[13px] text-[#323130] hover:bg-[#f3f2f1] flex items-center gap-2 no-underline">
      <svg className="w-4 h-4 text-[#605e5c]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4v12m0 0l-4-4m4 4l4-4M5 20h14" />
      </svg>
      <span>Descargar {nombre} para Windows <span className="text-[11px] text-[#605e5c]">({detalle})</span></span>
    </a>
  );
}
