/**
 * Barra «Cancelar y volver al correo» de la ventana emergente (/mensaje), 09/11/2026.
 *
 * Cuando en la ventana emergente se pulsa Responder / Reenviar, el editor ocupa toda la
 * ventana y el correo deja de verse. Si la persona lo pulsó por error o decide no responder,
 * necesita un botón claro para volver a leer el correo: la X y la papelera del editor son
 * iconos pequeños y no se entiende que «cierran la respuesta». Esta barra lo dice con palabras.
 *
 * Al pulsar se cierra la redacción igual que la X del editor: si ya había algo escrito se
 * guarda en Borradores; si no, simplemente desaparece.
 */
export function BarraVolverAlCorreo({ asunto, onVolver }: { asunto: string; onVolver: () => void }) {
  return (
    <div className="shrink-0 flex items-center gap-3 px-3 py-1.5 bg-[#f3f2f1] border-b border-[#edebe9] text-[12px] text-[#605e5c]">
      <span className="min-w-0 truncate">
        Respondiendo a <span className="text-[#323130] font-medium">«{asunto || '(sin asunto)'}»</span>
      </span>
      <div className="flex-1" />
      <button
        type="button"
        onClick={onVolver}
        title="Cancelar la respuesta y volver a leer el correo (si escribió algo queda en Borradores)"
        className="shrink-0 h-[28px] px-3 rounded-[4px] border border-[#8a8886] bg-white text-[12px] font-medium text-[#323130] hover:bg-[#e1dfdd] flex items-center gap-1.5"
      >
        <svg className="w-[14px] h-[14px]" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
        </svg>
        Cancelar y volver al correo
      </button>
    </div>
  );
}
