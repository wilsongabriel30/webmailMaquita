/**
 * Muestra pequeña de cómo queda el correo con el aspecto elegido: botón principal, enlace,
 * pestaña activa y un correo seleccionado. No hace nada al pulsarla; es solo para ver los colores.
 */
export function VistaPreviaAspecto() {
  return (
    <section aria-label="Muestra del aspecto elegido">
      <h2 className="text-sm font-semibold text-[#323130]">Así se ve</h2>
      <div aria-hidden="true" className="mt-2 rounded border border-[#edebe9] overflow-hidden select-none">
        <div className="bg-[#0078d4] text-white text-sm px-3 py-2">Correo</div>
        <div className="bg-white p-3 space-y-3">
          <div className="flex flex-wrap items-center gap-4">
            <span className="px-4 py-1.5 bg-[#0078d4] text-white text-sm rounded">Nuevo correo</span>
            <span className="text-sm text-[#0078d4] underline">Un enlace</span>
            <span className="text-sm text-[#0078d4] border-b-2 border-[#0078d4] font-medium pb-0.5">Pestaña activa</span>
          </div>
          <div className="border border-[#edebe9] rounded text-sm">
            <div className="px-3 py-2 bg-[#deecf9] border-l-[3px] border-[#0078d4] text-[#323130]">
              <span className="font-semibold">Correo seleccionado</span>
              <span className="block text-xs text-[#605e5c]">Así se resalta el correo que usted está leyendo</span>
            </div>
            <div className="px-3 py-2 border-l-[3px] border-transparent text-[#323130]">
              <span>Otro correo</span>
              <span className="block text-xs text-[#605e5c]">Los demás correos de la lista</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
