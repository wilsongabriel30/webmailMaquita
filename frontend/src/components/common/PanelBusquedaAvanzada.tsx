// Encontrar un correo deprisa, sin saber de operadores ni de términos técnicos.
//
// La caja de búsqueda acepta «de:», «asunto:», «entre:»… pero eso lo usa quien ya lo conoce. Este
// panel pregunta en lenguaje llano («¿Quién lo envió?»), deja a la vista solo lo que casi todos
// usan, guarda lo raro en «Más opciones» y dice en una frase lo que va a buscar (12/11/2026: los
// usuarios no son técnicos; antes mostraba la consulta con operadores y rótulos como «Dominio»).
//
// Lo que hay aquí va por cabecera, que es lo que Dovecot tiene indexado. La única casilla que
// cuesta es «buscar también dentro del texto»: sin índice de texto hay que abrir los mensajes uno
// a uno, y por eso se acota a tres meses si no se eligió fecha. Las cuentas con índice de texto
// (lo dice /mail/search/capacidades) buscan en el buzón entero en segundos; si el índice incluye
// los adjuntos, la misma casilla busca también dentro de PDF, Office y comprimidos.

import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { ATAJOS_FECHA, TAMANOS, resumirBusqueda, type CamposBusqueda } from '../../lib/resumenBusqueda';

interface Props {
  /** Se llama con la consulta compuesta, lista para buscar. */
  onBuscar: (consulta: string, buscarEnContenido: boolean) => void;
  onCerrar: () => void;
}

const VACIO: CamposBusqueda = {
  de: '', para: '', asunto: '', texto: '', dominio: '', desde: '', hasta: '', atajo: '',
  conAdjunto: false, adjuntoNombre: '', soloNoLeidos: false, soloMarcados: false, tamMin: '', enContenido: false,
};

export function PanelBusquedaAvanzada({ onBuscar, onCerrar }: Props) {
  const [c, setC] = useState<CamposBusqueda>(VACIO);
  const [masOpciones, setMasOpciones] = useState(false);
  const [conIndice, setConIndice] = useState(false);
  const [conAdjuntos, setConAdjuntos] = useState(false);
  const poner = (cambio: Partial<CamposBusqueda>) => setC((antes) => ({ ...antes, ...cambio }));

  useEffect(() => {
    let vivo = true;
    api.get<{ indice_texto: boolean; adjuntos?: boolean }>('/mail/search/capacidades')
      .then((r) => {
        if (!vivo) return;
        setConIndice(!!r?.indice_texto);
        setConAdjuntos(!!r?.adjuntos);
      })
      .catch(() => { /* sin respuesta: se acota, que es lo seguro */ });
    return () => { vivo = false; };
  }, []);

  function componer(): string {
    const partes: string[] = [];
    if (c.de.trim()) partes.push(`de:${c.de.trim()}`);
    if (c.para.trim()) partes.push(`para:${c.para.trim()}`);
    if (c.asunto.trim()) partes.push(`asunto:${c.asunto.trim()}`);
    if (c.dominio.trim()) partes.push(`dominio:${c.dominio.trim().replace(/^@/, '')}`);
    // Un rango explícito manda sobre el atajo: si alguien escribió las fechas, es lo que quiere.
    if (c.desde && c.hasta) partes.push(`entre:${c.desde},${c.hasta}`);
    else if (c.desde) partes.push(`despues:${c.desde}`);
    else if (c.hasta) partes.push(`antes:${c.hasta}`);
    else if (c.atajo) partes.push(c.atajo);
    // Entrar en el texto sin índice obliga a abrir los mensajes uno a uno: sin fecha elegida, los
    // últimos tres meses. Con índice de texto no hace falta acotar.
    if (c.enContenido && !conIndice && !c.desde && !c.hasta && !c.atajo) partes.push('trimestre');
    if (c.adjuntoNombre.trim()) partes.push(`adjunto:${c.adjuntoNombre.trim().replace(/\s+/g, '_')}`);
    else if (c.conAdjunto) partes.push('tiene:adjunto');
    if (c.soloNoLeidos) partes.push('es:noleido');
    if (c.soloMarcados) partes.push('es:marcado');
    if (c.tamMin.trim()) partes.push(`mayor:${c.tamMin.trim()}`);
    if (c.texto.trim()) partes.push(c.texto.trim());
    return partes.join(' ');
  }

  const consulta = componer();
  const frase = resumirBusqueda(c, conIndice);
  const acotadaATresMeses = c.enContenido && !conIndice && !c.desde && !c.hasta && !c.atajo;

  function buscar() {
    if (!consulta) return;
    onBuscar(consulta, c.enContenido);
    onCerrar();
  }

  const campo = 'w-full px-2.5 py-2 text-[13px] border border-[#e1dfdd] rounded outline-none focus:border-[#0078d4] bg-white text-[#323130]';
  const rotulo = 'block text-[13px] font-semibold text-[#323130] mb-1';
  const ayuda = 'block text-[11px] text-[#605e5c] mt-1';

  return (
    <div role="dialog" aria-label="Buscar un correo"
      className="absolute left-0 right-0 top-full mt-1 z-50 bg-white rounded-lg shadow-xl border border-[#e1dfdd] p-4 w-[580px] max-w-[92vw] max-h-[80vh] overflow-y-auto"
      onKeyDown={(e) => { if (e.key === 'Enter') buscar(); if (e.key === 'Escape') onCerrar(); }}>

      <div className="mb-3">
        <div className="text-[15px] font-semibold text-[#323130]">Buscar un correo</div>
        <div className="text-[12px] text-[#605e5c]">Llene solo lo que recuerde; no hace falta completar todo.</div>
      </div>

      <div className="grid grid-cols-2 gap-3 max-[520px]:grid-cols-1">
        <div>
          <label className={rotulo} htmlFor="ba-de">¿Quién lo envió?</label>
          <input id="ba-de" className={campo} value={c.de} onChange={(e) => poner({ de: e.target.value })}
            placeholder="Nombre o correo. Ej.: Daniel" autoFocus />
          {conIndice && <span className={ayuda}>También salen los correos suyos que otra persona le reenvió.</span>}
        </div>
        <div>
          <label className={rotulo} htmlFor="ba-para">¿A quién se envió?</label>
          <input id="ba-para" className={campo} value={c.para} onChange={(e) => poner({ para: e.target.value })}
            placeholder="Nombre o correo" />
        </div>
        <div className="col-span-2 max-[520px]:col-span-1">
          <label className={rotulo} htmlFor="ba-asunto">¿Qué decía el asunto?</label>
          <input id="ba-asunto" className={campo} value={c.asunto} onChange={(e) => poner({ asunto: e.target.value })}
            placeholder="Una o dos palabras del título. Ej.: factura" />
        </div>
        <div className="col-span-2 max-[520px]:col-span-1">
          <label className={rotulo} htmlFor="ba-texto">¿Alguna palabra que recuerde?</label>
          <input id="ba-texto" className={campo} value={c.texto} onChange={(e) => poner({ texto: e.target.value })}
            placeholder="Ej.: contrato, pago, reunión" />
          <label className="flex items-start gap-2 text-[12px] text-[#323130] mt-2">
            <input type="checkbox" className="mt-0.5" checked={c.enContenido}
              onChange={(e) => poner({ enContenido: e.target.checked })} />
            <span>
              {conAdjuntos ? 'Buscarla también dentro del mensaje y de sus archivos adjuntos' : 'Buscarla también dentro del mensaje'}
              <span className="block text-[11px] text-[#605e5c]">
                {conIndice
                  ? 'Revisa todo el buzón, también los correos antiguos. Tarda unos segundos.'
                  : 'Tarda más. Si elige una fecha abajo, va mucho más rápido.'}
              </span>
            </span>
          </label>
          {acotadaATresMeses && (
            <span className="block mt-1 text-[11px] text-[#8a6d3b] bg-[#fff4ce] rounded px-2 py-1">
              Se buscará en los últimos 3 meses. Para ir más atrás, elija una fecha abajo.
            </span>
          )}
        </div>
      </div>

      <div className="mt-3">
        <span className={rotulo}>¿De cuándo es?</span>
        <div className="flex flex-wrap gap-1.5 mb-2">
          {ATAJOS_FECHA.map((a) => (
            <button key={a.valor} type="button" aria-pressed={c.atajo === a.valor}
              onClick={() => poner({ atajo: c.atajo === a.valor ? '' : a.valor, desde: '', hasta: '' })}
              className={`px-3 py-1.5 text-[12px] rounded-full border transition-colors ${
                c.atajo === a.valor
                  ? 'bg-[#0078d4] text-white border-[#0078d4]'
                  : 'bg-white text-[#323130] border-[#e1dfdd] hover:bg-[#f3f2f1]'
              }`}>
              {a.etiqueta}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 text-[12px] text-[#605e5c]">
          <span className="shrink-0">o entre el</span>
          <input type="date" aria-label="Desde el día" className={campo} value={c.desde}
            onChange={(e) => poner({ desde: e.target.value, atajo: '' })} />
          <span className="shrink-0">y el</span>
          <input type="date" aria-label="Hasta el día" className={campo} value={c.hasta}
            onChange={(e) => poner({ hasta: e.target.value, atajo: '' })} />
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-[13px] text-[#323130]">
        <label className="flex items-center gap-1.5">
          <input type="checkbox" checked={c.conAdjunto} onChange={(e) => poner({ conAdjunto: e.target.checked })} />
          Tiene archivo adjunto
        </label>
        <label className="flex items-center gap-1.5">
          <input type="checkbox" checked={c.soloNoLeidos} onChange={(e) => poner({ soloNoLeidos: e.target.checked })} />
          Aún no lo he leído
        </label>
        <label className="flex items-center gap-1.5">
          <input type="checkbox" checked={c.soloMarcados} onChange={(e) => poner({ soloMarcados: e.target.checked })} />
          Lo marqué con bandera
        </label>
      </div>

      <button type="button" onClick={() => setMasOpciones(!masOpciones)} aria-expanded={masOpciones}
        className="mt-3 text-[12px] text-[#0078d4] hover:underline">
        {masOpciones ? '▾ Menos opciones' : '▸ Más opciones (empresa, nombre del archivo, tamaño)'}
      </button>
      {masOpciones && (
        <div className="mt-2 grid grid-cols-2 gap-3 max-[520px]:grid-cols-1">
          <div className="col-span-2 max-[520px]:col-span-1">
            <label className={rotulo} htmlFor="ba-dominio">¿De qué empresa o institución?</label>
            <input id="ba-dominio" className={campo} value={c.dominio} onChange={(e) => poner({ dominio: e.target.value })}
              placeholder="Lo que va después de la @. Ej.: banco.com" />
            <span className={ayuda}>Trae lo enviado por cualquier persona de ahí, o lo que usted les envió.</span>
          </div>
          <div>
            <label className={rotulo} htmlFor="ba-adjunto">¿Cómo se llamaba el archivo?</label>
            <input id="ba-adjunto" className={campo} value={c.adjuntoNombre} onChange={(e) => poner({ adjuntoNombre: e.target.value })}
              placeholder="Parte del nombre o el tipo. Ej.: factura, .pdf" />
          </div>
          <div>
            <label className={rotulo} htmlFor="ba-tam">¿Era un correo pesado?</label>
            <select id="ba-tam" className={campo} value={c.tamMin} onChange={(e) => poner({ tamMin: e.target.value })}>
              {TAMANOS.map((t) => <option key={t.valor} value={t.valor}>{t.etiqueta}</option>)}
            </select>
          </div>
        </div>
      )}

      <div role="status" aria-live="polite"
        className={`mt-3 px-3 py-2 rounded text-[12px] ${frase ? 'bg-[#eff6fc] text-[#323130]' : 'bg-[#f3f2f1] text-[#605e5c]'}`}
        title={consulta ? `En la caja de búsqueda se escribiría: ${consulta}` : undefined}>
        {frase ? <><b>Se buscará:</b> {frase[0].toLowerCase() + frase.slice(1)}</> : 'Escriba al menos un dato para buscar.'}
      </div>

      <div className="mt-3 flex justify-between gap-2">
        <button type="button" onClick={() => { setC(VACIO); setMasOpciones(false); }} disabled={!consulta}
          className="px-3 py-1.5 text-[13px] text-[#605e5c] hover:bg-[#f3f2f1] rounded transition-colors disabled:opacity-40">
          Limpiar
        </button>
        <div className="flex gap-2">
          <button type="button" onClick={onCerrar}
            className="px-3 py-1.5 text-[13px] text-[#605e5c] hover:bg-[#f3f2f1] rounded transition-colors">
            Cancelar
          </button>
          <button type="button" onClick={buscar} disabled={!consulta}
            className="px-5 py-1.5 text-[13px] bg-[#0078d4] text-white rounded hover:bg-[#106ebe] disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
            Buscar
          </button>
        </div>
      </div>
    </div>
  );
}
