/**
 * «Recuperar elementos eliminados», con el mismo nombre y el mismo sitio que tenía en Zimbra:
 * el menú de la Papelera. La gente ya lo conocía de allí, así que no hay nada nuevo que
 * aprender.
 *
 * Enseña lo borrado en los últimos 30 días, aunque se haya vaciado la papelera, y lo devuelve a
 * la bandeja de entrada. No se puede borrar desde aquí a propósito: esa copia es la garantía de
 * que no se pierde correo. Lo más antiguo sigue guardado y lo recupera sistemas.
 */
import { useEffect, useState } from 'react';

import { api } from '../../api/client';

interface Eliminado {
  uid: string;
  fecha?: string;
  de?: string;
  asunto?: string;
}

interface Detalle {
  de?: string;
  para?: string;
  fecha?: string;
  asunto?: string;
  cuerpo?: string;
}

export function RecuperarEliminados({ onCerrar }: { onCerrar: () => void }) {
  const [texto, setTexto] = useState('');
  const [mensajes, setMensajes] = useState<Eliminado[]>([]);
  const [cargando, setCargando] = useState(true);
  const [dias, setDias] = useState(30);
  const [detalle, setDetalle] = useState<Detalle | null>(null);
  const [abierto, setAbierto] = useState<string | null>(null);
  const [recuperados, setRecuperados] = useState<Set<string>>(new Set());

  const buscar = (consulta = texto) => {
    setCargando(true);
    setDetalle(null);
    api
      .get<{ total: number; dias: number; mensajes: Eliminado[] }>(
        `/mail/borrados?texto=${encodeURIComponent(consulta)}`,
      )
      .then((r) => { setMensajes(r.mensajes || []); setDias(r.dias || 30); })
      .catch(() => setMensajes([]))
      .finally(() => setCargando(false));
  };

  // La primera carga va aqui suelta y no llama a `buscar`: esa funcion pone `cargando` de
  // forma sincrona y eso encadena renders (react-hooks/set-state-in-effect). `cargando` ya
  // empieza en true, asi que no hace falta tocarlo antes de pedir.
  useEffect(() => {
    let vivo = true;
    api
      .get<{ total: number; dias: number; mensajes: Eliminado[] }>('/mail/borrados?texto=')
      .then((r) => { if (vivo) { setMensajes(r.mensajes || []); setDias(r.dias || 30); } })
      .catch(() => { if (vivo) setMensajes([]); })
      .finally(() => { if (vivo) setCargando(false); });
    return () => { vivo = false; };
  }, []);
  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') onCerrar(); };
    document.addEventListener('keydown', esc);
    return () => document.removeEventListener('keydown', esc);
  }, [onCerrar]);

  const ver = (uid: string) => {
    if (abierto === uid) { setAbierto(null); setDetalle(null); return; }
    setAbierto(uid);
    setDetalle(null);
    api.get<Detalle>(`/mail/borrados/${uid}`).then(setDetalle).catch(() => setAbierto(null));
  };

  const recuperar = async (m: Eliminado) => {
    try {
      await api.post(`/mail/borrados/${m.uid}/recuperar`, {});
      setRecuperados((s) => new Set(s).add(m.uid));
      window.dispatchEvent(new CustomEvent('refresh-messages'));
    } catch {
      alert('No se pudo recuperar el correo. Inténtalo de nuevo.');
    }
  };

  return (
    <div className="fixed inset-0 z-[10000] bg-black/30 flex items-start justify-center pt-[6vh] px-4" onClick={onCerrar}>
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-3xl max-h-[85vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="px-5 py-4 border-b border-[#edebe9]">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-[15px] font-semibold text-[#323130]">Recuperar elementos eliminados</h2>
              <p className="text-[12px] text-[#605e5c] mt-1">
                Correo que borraste en los últimos {dias} días, aunque hayas vaciado la papelera.
                Al recuperarlo vuelve a tu Bandeja de entrada.
              </p>
            </div>
            <button onClick={onCerrar} className="text-[#605e5c] hover:text-[#323130] text-[13px] px-2">Cerrar</button>
          </div>
          <div className="flex gap-2 mt-3">
            <input
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && buscar()}
              placeholder="Buscar por asunto o remitente"
              className="flex-1 px-3 py-2 border border-[#d2d0ce] rounded text-[13px] focus:outline-none focus:border-[#0078d4]"
            />
            <button onClick={() => buscar()} className="px-4 py-2 bg-[#0078d4] text-white rounded text-[13px] hover:bg-[#106ebe]">
              Buscar
            </button>
          </div>
        </div>

        <div className="overflow-auto flex-1">
          {cargando && <p className="text-[13px] text-[#605e5c] p-6 text-center">Buscando…</p>}

          {!cargando && mensajes.length === 0 && (
            <p className="text-[13px] text-[#605e5c] p-10 text-center">
              No hay correo eliminado que recuperar de los últimos {dias} días.
              {texto && ' Prueba con otra palabra.'}
            </p>
          )}

          {!cargando && mensajes.map((m) => (
            <div key={m.uid} className="border-b border-[#f3f2f1]">
              <div className="flex items-center gap-3 px-5 py-2.5 hover:bg-[#faf9f8]">
                <button onClick={() => ver(m.uid)} className="flex-1 text-left min-w-0">
                  <p className="text-[13px] text-[#323130] truncate">{m.asunto || '(sin asunto)'}</p>
                  <p className="text-[11px] text-[#605e5c] truncate">{m.de} · {m.fecha}</p>
                </button>
                {recuperados.has(m.uid) ? (
                  <span className="text-[12px] text-[#107c10] shrink-0">Recuperado ✓</span>
                ) : (
                  <button
                    onClick={() => recuperar(m)}
                    className="px-3 py-1.5 bg-[#107c10] text-white rounded text-[12px] hover:bg-[#0b5a0b] shrink-0"
                  >
                    Recuperar
                  </button>
                )}
              </div>
              {abierto === m.uid && (
                <div className="px-5 pb-4 bg-[#faf9f8]">
                  {!detalle && <p className="text-[12px] text-[#605e5c]">Abriendo…</p>}
                  {detalle && (
                    <>
                      <p className="text-[11px] text-[#605e5c]">Para: {detalle.para || '-'}</p>
                      <pre className="text-[12px] text-[#323130] whitespace-pre-wrap mt-2 max-h-52 overflow-auto bg-white rounded border border-[#edebe9] p-3">
                        {detalle.cuerpo || '(sin texto)'}
                      </pre>
                    </>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="px-5 py-3 border-t border-[#edebe9] bg-[#faf9f8] rounded-b-lg">
          <p className="text-[11px] text-[#605e5c]">
            ¿Buscas algo de hace más de {dias} días? Escribe a sistemas: se conserva y te lo pueden devolver.
          </p>
        </div>
      </div>
    </div>
  );
}
