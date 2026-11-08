/**
 * Nombres de los adjuntos debajo del extracto, en la lista de la bandeja (07/11/2026, como Outlook).
 * Se ven dos como mucho y «+N» si hay más; el nombre completo queda en la descripción emergente.
 * Los nombres los manda el backend (`adjuntos` del resumen, sacados de la BODYSTRUCTURE).
 */

function etiquetaTipo(nombre: string): { texto: string; color: string } {
  const ext = (nombre.split('.').pop() || '').toLowerCase();
  if (ext === 'pdf') return { texto: 'PDF', color: '#d13438' };
  if (['xml'].includes(ext)) return { texto: 'XML', color: '#605e5c' };
  if (['doc', 'docx', 'odt', 'rtf'].includes(ext)) return { texto: 'DOC', color: '#185abd' };
  if (['xls', 'xlsx', 'ods', 'csv'].includes(ext)) return { texto: 'XLS', color: '#107c41' };
  if (['ppt', 'pptx', 'odp'].includes(ext)) return { texto: 'PPT', color: '#c43e1c' };
  if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'heic'].includes(ext)) return { texto: 'IMG', color: '#8764b8' };
  if (['zip', 'rar', '7z', 'gz', 'tar'].includes(ext)) return { texto: 'ZIP', color: '#ca5010' };
  return { texto: (ext || 'ARCH').slice(0, 4).toUpperCase(), color: '#605e5c' };
}

export function ChipsAdjuntosFila({ nombres }: { nombres?: string[] }) {
  if (!nombres || nombres.length === 0) return null;
  const visibles = nombres.slice(0, 2);
  const resto = nombres.length - visibles.length;
  return (
    <div className="flex items-center gap-1.5 mt-1 min-w-0">
      {visibles.map(n => {
        const t = etiquetaTipo(n);
        return (
          <span key={n} title={n}
            className="inline-flex items-center gap-1 min-w-0 max-w-[48%] h-[22px] px-1.5 border border-[#e1dfdd] rounded bg-white text-[11px] text-[#323130]">
            <span className="shrink-0 px-[3px] rounded-[2px] text-[8px] font-bold leading-[12px] text-white" style={{ backgroundColor: t.color }}>{t.texto}</span>
            <span className="truncate">{n}</span>
          </span>
        );
      })}
      {resto > 0 && <span className="shrink-0 text-[11px] text-[#605e5c]">+{resto}</span>}
    </div>
  );
}
