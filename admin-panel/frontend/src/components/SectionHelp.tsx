import { useState } from "react";

/*
 * Tarjeta "¿Cómo funciona esta sección?" (mismo patrón que FARO): botón
 * compacto en la cabecera de cada página que despliega al pasar el mouse
 * (o al hacer clic, para táctil) una tarjeta con la explicación de la
 * sección y sus partes. Pensada para que cualquier persona que instale
 * el panel en otro servidor entienda cada pantalla sin manual.
 */

export interface SectionHelpItem {
  titulo: string;
  desc: string;
}

export function SectionHelp({ titulo, items }: { titulo: string; items: (SectionHelpItem | string)[] }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative inline-flex group" onMouseLeave={() => setOpen(false)}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold text-white bg-ms-blue hover:bg-ms-blue-dark shadow-sm"
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        ¿Cómo funciona esta sección?
      </button>
      <div
        className={`absolute right-0 top-full mt-1.5 w-[min(560px,90vw)] bg-white border border-ms-blue/20 rounded-xl shadow-xl p-4 z-50 transition-all duration-150 ${open ? "opacity-100 visible translate-y-0" : "opacity-0 invisible -translate-y-1"} group-hover:opacity-100 group-hover:visible group-hover:translate-y-0 max-h-[70vh] overflow-auto`}
      >
        <div className="font-semibold text-sm text-ms-gray-130 border-b border-ms-gray-30 pb-2 mb-2.5 flex items-center gap-2">
          <svg className="w-4 h-4 text-yellow-500 shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path d="M11 3a1 1 0 10-2 0v1a1 1 0 102 0V3zM15.657 5.757a1 1 0 00-1.414-1.414l-.707.707a1 1 0 001.414 1.414l.707-.707zM18 10a1 1 0 01-1 1h-1a1 1 0 110-2h1a1 1 0 011 1zM5.05 6.464A1 1 0 106.464 5.05l-.707-.707a1 1 0 00-1.414 1.414l.707.707zM5 10a1 1 0 01-1 1H3a1 1 0 110-2h1a1 1 0 011 1zM8 16v-1h4v1a2 2 0 11-4 0zM12 14c.015-.34.208-.646.477-.859a4 4 0 10-4.954 0c.27.213.462.519.476.859h4.002z" />
          </svg>
          {titulo}
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-left">
          {items.map((item, i) =>
            typeof item === "string" ? (
              <div key={i} className="text-xs text-ms-gray-90 leading-relaxed sm:col-span-2">{item}</div>
            ) : (
              <div key={i}>
                <div className="text-xs font-semibold text-ms-gray-130 flex items-start gap-1">
                  <svg className="w-3 h-3 text-ms-green mt-0.5 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  {item.titulo}
                </div>
                <div className="text-xs text-ms-gray-90 leading-relaxed pl-4">{item.desc}</div>
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
}
