/** Marca en la lista de correos: este correo tiene reacciones (se ven cuáles y cuántas). */
export function MarcaReacciones({ r }: { r?: { total: number; emojis: string[] } | null }) {
  if (!r || !r.total) return null;
  const texto = `${r.total} ${r.total === 1 ? 'reacción' : 'reacciones'}: ábralo para ver quién`;
  return (
    <span title={texto} aria-label={texto}
      className="shrink-0 inline-flex items-center gap-0.5 px-1 rounded-full border border-[#d2d0ce] bg-white text-[11px] leading-[16px] text-[#323130] dark:bg-[#2b2b2b] dark:border-[#444] dark:text-[#e0e0e0]">
      <span aria-hidden="true">{r.emojis.slice(0, 3).join('')}</span>
      {r.total > 1 && <span className="tabular-nums">{r.total}</span>}
    </span>
  );
}
