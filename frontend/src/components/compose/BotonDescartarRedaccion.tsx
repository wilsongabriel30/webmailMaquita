/**
 * Papelera «Descartar» de la ventana de redacción (07/11/2026, como Outlook).
 * A diferencia de la X (cierra y guarda en Borradores), esto BORRA el mensaje:
 * no queda en Borradores. Si hay algo escrito, pide confirmación antes.
 */
export function BotonDescartarRedaccion({ onDescartar }: { onDescartar: () => void }) {
  return (
    <button type="button" onClick={onDescartar} title="Descartar (no se guarda en Borradores)" aria-label="Descartar"
      className="w-[32px] h-[32px] rounded-[3px] flex items-center justify-center text-[#605e5c] hover:bg-[#fde7e9] hover:text-[#a4262c] transition-colors">
      <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M4 7h16M9.5 7V4.5h5V7M6.5 7l.9 12.5h9.2L17.5 7M10 11v5.5M14 11v5.5" />
      </svg>
    </button>
  );
}
