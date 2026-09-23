/**
 * Asistente de redacción IA en el redactor, sin ocupar espacio fijo.
 *
 * Antes era una franja permanente sobre el texto («Asistente de redaccion IA · Autocompletar con
 * IA») que restaba una línea de redacción aunque no se usara. Ahora:
 * - `BotonAutocompletarIA`: botón pequeño en la fila del asunto.
 * - `FranjaSugerenciaIA`: aparece solo mientras la IA genera o cuando hay una sugerencia que
 *   insertar, y se va al insertarla o descartarla.
 */
const Chispa = ({ tam = 14 }: { tam?: number }) => (
  <svg width={tam} height={tam} viewBox="0 0 24 24" fill="none" stroke="#0078d4" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
  </svg>
);

export function BotonAutocompletarIA({ onClick, ocupado }: { onClick: () => void; ocupado: boolean }) {
  return (
    <button onClick={onClick} disabled={ocupado}
      title="Autocompletar el correo con IA"
      className="mr-1 px-2 py-1 text-[11px] text-[#0078d4] hover:bg-[#f3f2f1] rounded flex items-center gap-1 disabled:opacity-50 whitespace-nowrap">
      <Chispa />
      {ocupado ? 'Generando…' : 'Autocompletar'}
    </button>
  );
}

export function FranjaSugerenciaIA({ generando, sugerencia, onInsertar, onDescartar }: {
  generando: boolean;
  sugerencia: string;
  onInsertar: () => void;
  onDescartar: () => void;
}) {
  if (!generando && !sugerencia) return null;
  return (
    <div className="flex items-center gap-2 px-4 py-1 bg-[#f0f6ff] border-b border-[#c7e0f4] shrink-0">
      <Chispa />
      {generando ? (
        <span className="text-[12px] text-[#605e5c] flex-1">Generando sugerencia con IA...</span>
      ) : (
        <>
          <span className="text-[12px] text-[#605e5c] truncate flex-1" title={sugerencia}>
            {sugerencia.length > 80 ? sugerencia.slice(0, 80) + '...' : sugerencia}
          </span>
          <button onClick={onInsertar} className="text-[11px] font-semibold text-[#0078d4] hover:bg-[#deecf9] px-2 py-0.5 rounded">Insertar</button>
          <button onClick={onDescartar} title="Descartar la sugerencia" className="text-[11px] text-[#a19f9d] hover:text-[#605e5c] px-1">{'✕'}</button>
        </>
      )}
    </div>
  );
}
