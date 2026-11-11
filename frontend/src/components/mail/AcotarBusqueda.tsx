/**
 * Barra «Acotar» sobre los resultados de una búsqueda con muchos resultados (lib/acotarBusqueda.ts):
 * dice cuántos hay y ofrece, con un clic, quedarse con el remitente, el asunto, lo reciente o lo que
 * trae adjuntos. Cada opción reescribe la búsqueda con el operador correspondiente, que queda a la vista
 * en la caja de buscar (así se aprende y se puede editar).
 */
import { useMailStore } from '../../store/mailStore';
import { opcionesParaAcotar, sinOperadores, UMBRAL_ACOTAR } from '../../lib/acotarBusqueda';

export function AcotarBusqueda() {
  const searchQuery = useMailStore(s => s.searchQuery);
  const consultaAplicada = useMailStore(s => s.debouncedSearchQuery);
  const total = useMailStore(s => s.totalMessages);
  const setSearchQuery = useMailStore(s => s.setSearchQuery);
  const consulta = searchQuery.trim();
  // Solo cuando el número mostrado corresponde a lo que está escrito (la búsqueda ya terminó).
  if (!consulta || consulta !== consultaAplicada.trim()) return null;
  const limpia = sinOperadores(consulta);
  if (total < UMBRAL_ACOTAR && !limpia) return null;
  const opciones = total >= UMBRAL_ACOTAR ? opcionesParaAcotar(consulta) : [];
  if (opciones.length === 0 && !limpia) return null;
  const estilo = 'shrink-0 px-2.5 py-[3px] rounded-full border border-[#c7e0f4] bg-white text-[#0078d4] hover:bg-[#deecf9] whitespace-nowrap dark:bg-[#2b2b2b] dark:border-[#3a4a5a]';
  return (
    <div role="region" aria-label="Acotar la búsqueda"
      className="shrink-0 flex items-center gap-2 px-4 py-1.5 text-[12px] bg-[#faf9f8] text-[#323130] border-b border-[#edebe9] overflow-x-auto dark:bg-[#252525] dark:text-[#e0e0e0] dark:border-[#3a3a3a]">
      <span className="shrink-0">
        <strong>{total.toLocaleString('es-EC')}</strong> {total === 1 ? 'resultado' : 'resultados'}
        {opciones.length > 0 ? '. Acotar:' : '.'}
      </span>
      {opciones.map((o) => (
        <button key={o.clave} type="button" className={estilo} title={`Buscar: ${o.consulta}`} onClick={() => setSearchQuery(o.consulta)}>
          {o.texto}
        </button>
      ))}
      {limpia && (
        <button type="button" className="shrink-0 ml-auto text-[#605e5c] hover:underline whitespace-nowrap dark:text-[#c8c8c8]"
          title={`Buscar: ${limpia}`} onClick={() => setSearchQuery(limpia)}>
          Quitar filtros
        </button>
      )}
    </div>
  );
}
