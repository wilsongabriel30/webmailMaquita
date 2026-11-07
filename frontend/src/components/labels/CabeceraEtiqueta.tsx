/**
 * CabeceraEtiqueta.tsx — franja «Etiqueta: X» sobre la lista cuando se filtra por etiqueta (05/11/2026).
 */
import { useMailStore } from '../../store/mailStore';
import { getFolderDisplayName } from '../../folders';

export function CabeceraEtiqueta() {
  const etiqueta = useMailStore((s) => s.etiquetaFiltro);
  const total = useMailStore((s) => s.totalMessages);
  const carpeta = useMailStore((s) => s.currentFolder);
  const salir = useMailStore((s) => s.setEtiquetaFiltro);
  if (!etiqueta) return null;
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 text-[12px] border-b border-[#edebe9] dark:border-[#333] bg-[#f3f2f1] dark:bg-[#2a2a2a] text-[#323130] dark:text-[#e0e0e0]">
      <span className="w-3 h-3 rounded-sm shrink-0" style={{ backgroundColor: etiqueta.color }} />
      <span className="font-semibold">Etiqueta: {etiqueta.name}</span>
      <span className="text-[#605e5c]">· {total} {total === 1 ? 'correo' : 'correos'} de todas las carpetas</span>
      <button type="button" onClick={() => salir(null)} title={`Volver a ${getFolderDisplayName(carpeta)}`}
        className="ml-auto px-2 py-0.5 rounded text-[#106ebe] hover:bg-[#e1dfdd] dark:hover:bg-[#333]">
        Volver a {getFolderDisplayName(carpeta)} ×
      </button>
    </div>
  );
}
