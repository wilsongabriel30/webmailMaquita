/**
 * Etiquetas de colores de un correo en la fila de la lista.
 *
 * Antes cada fila pintaba TODAS las etiquetas sin dejarlas encoger: con cinco categorías ocupaban el
 * renglón entero y el asunto, que sí encoge, quedaba en cero píxeles (informe de Andes, 15/11/2026).
 * Ahora se ven como mucho dos, el resto se resume en «+N» (con los nombres al pasar el ratón), los
 * nombres largos se cortan con puntos suspensivos y el grupo nunca pasa del 40 % del renglón.
 */
export interface EtiquetaFila { id: string | number; name: string; color?: string }

/** Las que se pintan; el resto se resume en «+N». */
const MAX_ETIQUETAS_VISIBLES = 2;

const nombreCorto = (nombre: string) => String(nombre).replace(/^Categor[ií]a\s+/i, '') || nombre;

export function EtiquetasFila({ etiquetas }: { etiquetas: EtiquetaFila[] }) {
  if (!etiquetas.length) return null;
  const visibles = etiquetas.slice(0, MAX_ETIQUETAS_VISIBLES);
  const ocultas = etiquetas.slice(MAX_ETIQUETAS_VISIBLES);
  return (
    <span className="flex items-center gap-1 min-w-0 max-w-[40%] shrink-0 overflow-hidden">
      {visibles.map((lbl) => (
        <span key={lbl.id} title={lbl.name}
          className="min-w-0 truncate px-1.5 h-[15px] rounded-[3px] text-[10px] font-medium text-white capitalize leading-[15px]"
          style={{ backgroundColor: lbl.color }}>
          {nombreCorto(lbl.name)}
        </span>
      ))}
      {ocultas.length > 0 && (
        <span title={ocultas.map((l) => l.name).join(', ')}
          className="shrink-0 px-1 h-[15px] rounded-[3px] text-[10px] font-medium leading-[15px] text-[#323130] bg-[#edebe9]">
          +{ocultas.length}
        </span>
      )}
    </span>
  );
}
