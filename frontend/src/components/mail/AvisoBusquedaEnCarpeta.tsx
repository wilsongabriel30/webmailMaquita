/**
 * Aviso sobre la lista mientras se busca dentro de una carpeta concreta:
 * «La búsqueda se realizará únicamente en la carpeta X», con la opción de ampliarla
 * a todas las carpetas. No se muestra cuando ya se busca en todo el correo (Virtual.Todo).
 */
import { useMailStore } from '../../store/mailStore';
import { getFolderDisplayName } from '../../folders';
import { CARPETA_TODO, cambiarAmbito } from '../../lib/busquedaGlobal';

export function AvisoBusquedaEnCarpeta() {
  const searchQuery = useMailStore(s => s.searchQuery);
  const currentFolder = useMailStore(s => s.currentFolder);
  if (!searchQuery.trim() || currentFolder === CARPETA_TODO) return null;
  const carpeta = getFolderDisplayName(currentFolder);
  return (
    <div role="status" aria-live="polite"
      className="shrink-0 flex items-center gap-2 px-4 py-1.5 text-[12px] bg-[#eff6fc] text-[#323130] border-b border-[#c7e0f4] dark:bg-[#1f2a36] dark:text-[#e0e0e0] dark:border-[#2d3b4b]">
      <svg className="w-3.5 h-3.5 shrink-0 text-[#0078d4]" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <span className="min-w-0 truncate">
        La búsqueda se realizará únicamente en la carpeta <strong>{carpeta}</strong>.
      </span>
      <button type="button" onClick={() => cambiarAmbito(true)}
        className="ml-auto shrink-0 text-[#0078d4] hover:underline whitespace-nowrap">
        Buscar en todas las carpetas
      </button>
    </div>
  );
}
