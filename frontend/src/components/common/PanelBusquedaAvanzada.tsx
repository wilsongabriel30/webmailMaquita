// Encontrar un correo deprisa sin tener que saberse los operadores.
//
// La caja de búsqueda acepta «de:», «asunto:», «entre:»… pero eso lo usa quien ya lo conoce. Este
// panel pone lo mismo en campos, y compone la consulta por debajo.
//
// Todo lo que hay aquí va por cabecera, que es lo que Dovecot tiene indexado: en un buzón de
// 10.000 mensajes responde en decenas de milisegundos. La única casilla que cuesta es «buscar
// también dentro del texto», y por eso avisa de lo que va a tardar: sin índice de texto hay que
// abrir y descifrar los mensajes uno a uno, y eso son minuto y medio.

import { useState } from 'react';

interface Props {
  /** Se llama con la consulta compuesta, lista para buscar. */
  onBuscar: (consulta: string, buscarEnContenido: boolean) => void;
  onCerrar: () => void;
}

const ATAJOS = [
  { etiqueta: 'Hoy', valor: 'hoy' },
  { etiqueta: 'Ayer', valor: 'ayer' },
  { etiqueta: 'Esta semana', valor: 'semana' },
  { etiqueta: 'Este mes', valor: 'mes' },
  { etiqueta: 'Últimos 3 meses', valor: 'trimestre' },
];

export function PanelBusquedaAvanzada({ onBuscar, onCerrar }: Props) {
  const [texto, setTexto] = useState('');
  const [de, setDe] = useState('');
  const [para, setPara] = useState('');
  const [asunto, setAsunto] = useState('');
  const [dominio, setDominio] = useState('');
  const [desde, setDesde] = useState('');
  const [hasta, setHasta] = useState('');
  const [atajo, setAtajo] = useState('');
  const [conAdjunto, setConAdjunto] = useState(false);
  const [soloNoLeidos, setSoloNoLeidos] = useState(false);
  const [soloMarcados, setSoloMarcados] = useState(false);
  const [tamMin, setTamMin] = useState('');
  const [enContenido, setEnContenido] = useState(false);

  function componer(): string {
    const partes: string[] = [];
    if (de.trim()) partes.push(`de:${de.trim()}`);
    if (para.trim()) partes.push(`para:${para.trim()}`);
    if (asunto.trim()) partes.push(`asunto:${asunto.trim()}`);
    if (dominio.trim()) partes.push(`dominio:${dominio.trim().replace(/^@/, '')}`);
    // Un rango explícito manda sobre el atajo: si alguien escribió las fechas, es lo que quiere.
    if (desde && hasta) partes.push(`entre:${desde}..${hasta}`);
    else if (desde) partes.push(`despues:${desde}`);
    else if (hasta) partes.push(`antes:${hasta}`);
    else if (atajo) partes.push(atajo);
    // Entrar en el texto obliga a descifrar los mensajes uno a uno, asi que lo que decide la
    // espera es cuantos hay. Sin fecha elegida: los ultimos tres meses (4,5 s medidos, frente a
    // 17 s del buzon entero). Quien necesite mas, pone la fecha y lo sabe.
    if (enContenido && !desde && !hasta && !atajo) partes.push('trimestre');
    if (conAdjunto) partes.push('tiene:adjunto');
    if (soloNoLeidos) partes.push('es:noleido');
    if (soloMarcados) partes.push('es:marcado');
    if (tamMin.trim()) partes.push(`mayor:${tamMin.trim()}`);
    if (texto.trim()) partes.push(texto.trim());
    return partes.join(' ');
  }

  const consulta = componer();

  function buscar() {
    if (!consulta) return;
    onBuscar(consulta, enContenido);
    onCerrar();
  }

  const campo = 'w-full px-2 py-1.5 text-[13px] border border-[#e1dfdd] rounded outline-none focus:border-[#0078d4] bg-white text-[#323130]';
  const rotulo = 'block text-[11px] font-semibold text-[#605e5c] mb-1';

  return (
    <div className="absolute left-0 right-0 top-full mt-1 z-50 bg-white rounded-lg shadow-xl border border-[#e1dfdd] p-4 w-[560px] max-w-[92vw]"
      onKeyDown={(e) => { if (e.key === 'Enter') buscar(); if (e.key === 'Escape') onCerrar(); }}>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={rotulo} htmlFor="ba-de">De</label>
          <input id="ba-de" className={campo} value={de} onChange={(e) => setDe(e.target.value)}
            placeholder="nombre o dirección" />
        </div>
        <div>
          <label className={rotulo} htmlFor="ba-para">Para</label>
          <input id="ba-para" className={campo} value={para} onChange={(e) => setPara(e.target.value)}
            placeholder="nombre o dirección" />
        </div>
        <div className="col-span-2">
          <label className={rotulo} htmlFor="ba-asunto">Asunto</label>
          <input id="ba-asunto" className={campo} value={asunto} onChange={(e) => setAsunto(e.target.value)}
            placeholder="palabras del asunto" />
        </div>
        <div className="col-span-2">
          <label className={rotulo} htmlFor="ba-texto">Contiene las palabras</label>
          <input id="ba-texto" className={campo} value={texto} onChange={(e) => setTexto(e.target.value)}
            placeholder="se busca en remitente, destinatario y asunto" />
        </div>
        <div className="col-span-2">
          <label className={rotulo} htmlFor="ba-dominio">Dominio</label>
          <input id="ba-dominio" className={campo} value={dominio} onChange={(e) => setDominio(e.target.value)}
            placeholder="maquita.org — de o para cualquiera de ese dominio" />
        </div>
      </div>

      <div className="mt-3">
        <span className={rotulo}>Fecha</span>
        <div className="flex flex-wrap gap-1.5 mb-2">
          {ATAJOS.map((a) => (
            <button key={a.valor} type="button"
              onClick={() => { setAtajo(atajo === a.valor ? '' : a.valor); setDesde(''); setHasta(''); }}
              className={`px-2.5 py-1 text-[12px] rounded-full border transition-colors ${
                atajo === a.valor
                  ? 'bg-[#0078d4] text-white border-[#0078d4]'
                  : 'bg-white text-[#605e5c] border-[#e1dfdd] hover:bg-[#f3f2f1]'
              }`}>
              {a.etiqueta}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <input type="date" aria-label="Desde" className={campo} value={desde}
            onChange={(e) => { setDesde(e.target.value); setAtajo(''); }} />
          <span className="text-[12px] text-[#605e5c] shrink-0">hasta</span>
          <input type="date" aria-label="Hasta" className={campo} value={hasta}
            onChange={(e) => { setHasta(e.target.value); setAtajo(''); }} />
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-[12px] text-[#323130]">
        <label className="flex items-center gap-1.5">
          <input type="checkbox" checked={conAdjunto} onChange={(e) => setConAdjunto(e.target.checked)} />
          Con adjuntos
        </label>
        <label className="flex items-center gap-1.5">
          <input type="checkbox" checked={soloNoLeidos} onChange={(e) => setSoloNoLeidos(e.target.checked)} />
          Sin leer
        </label>
        <label className="flex items-center gap-1.5">
          <input type="checkbox" checked={soloMarcados} onChange={(e) => setSoloMarcados(e.target.checked)} />
          Marcados
        </label>
        <label className="flex items-center gap-1.5">
          Mayor de
          <input className={`${campo} w-[70px] py-1`} value={tamMin} onChange={(e) => setTamMin(e.target.value)}
            placeholder="5M" aria-label="Tamaño mínimo" />
        </label>
      </div>

      <div className="mt-3 pt-3 border-t border-[#edebe9]">
        <label className="flex items-start gap-2 text-[12px] text-[#323130]">
          <input type="checkbox" className="mt-0.5" checked={enContenido}
            onChange={(e) => setEnContenido(e.target.checked)} />
          <span>
            Buscar también dentro del texto de los mensajes
            <span className="block text-[11px] text-[#a19f9d]">
              Más lento: hay que abrir uno a uno los mensajes, que están cifrados. Lo que marca la
              espera es cuántos: acotar la fecha lo cambia todo.
            </span>
            {enContenido && !desde && !hasta && !atajo && (
              <span className="block mt-1 text-[11px] text-[#8a6d3b] bg-[#fff4ce] rounded px-2 py-1">
                Se buscará en los últimos 3 meses (unos segundos). Para ir más atrás, elige una
                fecha arriba: el buzón entero puede tardar medio minuto.
              </span>
            )}
          </span>
        </label>
      </div>

      {consulta && (
        <div className="mt-3 px-2 py-1.5 bg-[#f3f2f1] rounded text-[11px] text-[#605e5c] font-mono break-all">
          {consulta}
        </div>
      )}

      <div className="mt-3 flex justify-end gap-2">
        <button type="button" onClick={onCerrar}
          className="px-3 py-1.5 text-[13px] text-[#605e5c] hover:bg-[#f3f2f1] rounded transition-colors">
          Cancelar
        </button>
        <button type="button" onClick={buscar} disabled={!consulta}
          className="px-4 py-1.5 text-[13px] bg-[#0078d4] text-white rounded hover:bg-[#106ebe] disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
          Buscar
        </button>
      </div>
    </div>
  );
}
