// «¿Con quién fue el correo?»: la correspondencia con UNA persona (17/11/2026).
//
// Pedido de los usuarios: ver solo lo que una persona les envió a ellos o lo que ellos le
// enviaron, sin lo que llegó en copia. «¿Quién lo envió?» no alcanza: trae también lo que esa
// persona envió a otros con copia a uno. Aquí se escribe el nombre una sola vez y se elige, con
// palabras de todos los días, qué parte de esa correspondencia se quiere ver.

import { ALCANCES, type AlcancePersona } from '../../lib/resumenBusqueda';

interface Props {
  persona: string;
  alcance: AlcancePersona;
  onPersona: (v: string) => void;
  onAlcance: (v: AlcancePersona) => void;
  claseCampo: string;
  claseRotulo: string;
}

export function PersonaBusqueda({ persona, alcance, onPersona, onAlcance, claseCampo, claseRotulo }: Props) {
  const hayPersona = persona.trim().length > 0;
  return (
    <div className="mb-3 rounded-md border border-[#c7e0f4] bg-[#f3f9fd] p-3">
      <label className={claseRotulo} htmlFor="ba-persona">¿Con quién fue el correo?</label>
      <input id="ba-persona" className={claseCampo} value={persona} onChange={(e) => onPersona(e.target.value)}
        placeholder="Nombre o correo de la persona. Ej.: Mariana" autoFocus />
      <div role="radiogroup" aria-label="Qué correos de esa persona quiere ver"
        className={`mt-2 grid grid-cols-2 gap-1.5 max-[520px]:grid-cols-1 ${hayPersona ? '' : 'opacity-60'}`}>
        {ALCANCES.map((a) => {
          const elegido = alcance === a.valor;
          return (
            <button key={a.valor} type="button" role="radio" aria-checked={elegido}
              onClick={() => onAlcance(a.valor)}
              className={`text-left px-2.5 py-1.5 rounded border transition-colors ${
                elegido
                  ? 'bg-white border-[#0078d4] ring-1 ring-[#0078d4]'
                  : 'bg-white border-[#e1dfdd] hover:border-[#0078d4]'
              }`}>
              <span className="flex items-start gap-2">
                <span aria-hidden="true"
                  className={`mt-[3px] h-3 w-3 shrink-0 rounded-full border ${
                    elegido ? 'border-[#0078d4] bg-[#0078d4] shadow-[inset_0_0_0_2px_white]' : 'border-[#8a8886]'
                  }`} />
                <span>
                  <span className="block text-[12.5px] font-semibold text-[#323130]">{a.titulo}</span>
                  <span className="block text-[11px] text-[#605e5c]">{a.detalle}</span>
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
