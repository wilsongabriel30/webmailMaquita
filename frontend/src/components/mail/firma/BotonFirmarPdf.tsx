/** Botón «Firmar» de la cabecera del visor de adjuntos; solo para PDF (09/11/2026). */
export function BotonFirmarPdf({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} title="Firmar este PDF con su certificado digital (Raíces)"
      className="flex items-center gap-1 px-3 py-1.5 text-[13px] text-[#0078d4] hover:bg-[#f3f2f1] dark:hover:bg-[#383838] rounded">
      <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.6} viewBox="0 0 24 24" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M4 21h16" />
      </svg>
      Firmar
    </button>
  );
}
