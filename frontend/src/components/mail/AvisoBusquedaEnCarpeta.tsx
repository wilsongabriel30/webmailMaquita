/**
 * Aviso sobre la lista mientras se busca.
 *
 * - Buscando dentro de una carpeta: dice en cuál y ofrece buscar en todas. Si en la carpeta no hay
 *   ningún resultado, pregunta al resto del correo y, si ahí sí hay, pasa sola a todas las carpetas
 *   (13/11/2026): nadie tiene que saber en qué carpeta quedó el correo.
 * - Tras esa ampliación automática: lo explica y ofrece volver a la carpeta.
 * No se muestra cuando la persona eligió buscar en todo el correo.
 */
import { useEffect } from 'react';
import { useMailStore } from '../../store/mailStore';
import { getFolderDisplayName } from '../../folders';
import {
  CARPETA_TODO, ampliadaDesde, ampliarPorFaltaDeResultados, cambiarAmbito, volverALaCarpeta,
} from '../../lib/busquedaGlobal';
import { useTotalEnTodoElCorreo } from '../../hooks/useTotalEnTodoElCorreo';

const CAJA = 'shrink-0 flex items-center gap-2 px-4 py-1.5 text-[12px] bg-[#eff6fc] text-[#323130] border-b border-[#c7e0f4] dark:bg-[#1f2a36] dark:text-[#e0e0e0] dark:border-[#2d3b4b]';
const BOTON = 'ml-auto shrink-0 text-[#0078d4] hover:underline whitespace-nowrap';

function Icono() {
  return (
    <svg className="w-3.5 h-3.5 shrink-0 text-[#0078d4]" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

export function AvisoBusquedaEnCarpeta() {
  const searchQuery = useMailStore(s => s.searchQuery);
  const buscada = useMailStore(s => s.debouncedSearchQuery);
  const currentFolder = useMailStore(s => s.currentFolder);
  const totalAqui = useMailStore(s => s.totalMessages);
  const cargando = useMailStore(s => s.loadingMessages);
  const filtro = useMailStore(s => s.filter);
  const enCarpeta = currentFolder !== CARPETA_TODO;
  // Solo se pregunta cuando la carpeta ya respondió a ESTA búsqueda, no hay un filtro puesto y la carpeta
  // NO tiene ningún resultado. Preguntar en cada búsqueda (como se publicó el 13/11 por la mañana) lanzaba una
  // búsqueda en todo el correo por cada búsqueda normal: con el disco de buzones cargado tardaban 30 s de
  // mediana y se acumulaban. Buscar en todas las carpetas sigue a un clic.
  const listo = enCarpeta && !cargando && filtro === 'all' && buscada.trim() !== '' && buscada === searchQuery && totalAqui === 0;
  const totalTodo = useTotalEnTodoElCorreo(buscada, listo);
  const enOtras = totalTodo === null ? null : Math.max(0, totalTodo - totalAqui);

  useEffect(() => {
    if (listo && totalAqui === 0 && totalTodo !== null && totalTodo > 0) ampliarPorFaltaDeResultados(buscada);
  }, [listo, totalAqui, totalTodo, buscada]);

  if (!searchQuery.trim()) return null;

  if (!enCarpeta) {
    const origen = ampliadaDesde();
    if (!origen) return null;
    return (
      <div role="status" aria-live="polite" className={CAJA}>
        <Icono />
        <span className="min-w-0 truncate">
          En <strong>{getFolderDisplayName(origen)}</strong> no había ninguno: estos resultados son de <strong>todas las carpetas</strong>.
        </span>
        <button type="button" onClick={volverALaCarpeta} className={BOTON}>
          Volver a {getFolderDisplayName(origen)}
        </button>
      </div>
    );
  }

  const carpeta = getFolderDisplayName(currentFolder);
  return (
    <div role="status" aria-live="polite" className={CAJA}>
      <Icono />
      <span className="min-w-0 truncate">
        {enOtras
          ? <>Buscando en <strong>{carpeta}</strong>. Hay <strong>{enOtras.toLocaleString('es')}</strong> {enOtras === 1 ? 'resultado más' : 'resultados más'} en otras carpetas.</>
          : <>La búsqueda se realizará únicamente en la carpeta <strong>{carpeta}</strong>.</>}
      </span>
      <button type="button" onClick={() => cambiarAmbito(true)} className={BOTON}>
        {enOtras ? 'Ver todos' : 'Buscar en todas las carpetas'}
      </button>
    </div>
  );
}
