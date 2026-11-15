/**
 * Grupo de opciones excluyentes (como botones de radio) para la pestaña Apariencia.
 * Teclado: Tab entra al grupo; las flechas cambian de opción; Inicio y Fin van a los extremos.
 */
import { useId, useRef } from 'react';

export interface Opcion<T extends string | number> {
  valor: T;
  etiqueta: string;
  /** Color de muestra (círculo) para las opciones de color. */
  muestra?: string;
}

interface Props<T extends string | number> {
  titulo: string;
  ayuda?: string;
  opciones: Opcion<T>[];
  valor: T | null;
  alElegir: (valor: T) => void;
}

export function GrupoOpciones<T extends string | number>({ titulo, ayuda, opciones, valor, alElegir }: Props<T>) {
  const id = useId();
  const botones = useRef<(HTMLButtonElement | null)[]>([]);
  const elegida = opciones.findIndex((o) => o.valor === valor);

  const irA = (i: number) => {
    const n = (i + opciones.length) % opciones.length;
    alElegir(opciones[n].valor);
    botones.current[n]?.focus();
  };

  const alTeclear = (e: React.KeyboardEvent, i: number) => {
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') { e.preventDefault(); irA(i + 1); }
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') { e.preventDefault(); irA(i - 1); }
    else if (e.key === 'Home') { e.preventDefault(); irA(0); }
    else if (e.key === 'End') { e.preventDefault(); irA(opciones.length - 1); }
  };

  return (
    <section>
      <h2 id={`${id}-titulo`} className="text-sm font-semibold text-[#323130]">{titulo}</h2>
      {ayuda && <p id={`${id}-ayuda`} className="mt-0.5 text-xs text-[#605e5c]">{ayuda}</p>}
      <div role="radiogroup" aria-labelledby={`${id}-titulo`} aria-describedby={ayuda ? `${id}-ayuda` : undefined}
        className="mt-2 flex flex-wrap gap-2">
        {opciones.map((o, i) => {
          const activa = i === elegida;
          return (
            <button key={String(o.valor)} type="button" role="radio" aria-checked={activa}
              ref={(el) => { botones.current[i] = el; }}
              tabIndex={activa || (elegida < 0 && i === 0) ? 0 : -1}
              onClick={() => alElegir(o.valor)} onKeyDown={(e) => alTeclear(e, i)}
              className={`aspecto-opcion flex items-center gap-2 px-3 py-2 rounded border text-sm transition-colors ${
                activa
                  ? 'border-[#0078d4] bg-[#eff6fc] text-[#323130] font-medium'
                  : 'border-[#8a8886] text-[#323130] hover:bg-[#f3f2f1]'
              }`}>
              {o.muestra && (
                <span aria-hidden="true" className="w-5 h-5 rounded-full shrink-0 flex items-center justify-center" style={{ backgroundColor: o.muestra }}>
                  {activa && (
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth={3.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </span>
              )}
              {!o.muestra && activa && (
                <svg aria-hidden="true" className="shrink-0 text-[#0078d4]" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              )}
              {o.etiqueta}
            </button>
          );
        })}
      </div>
    </section>
  );
}
