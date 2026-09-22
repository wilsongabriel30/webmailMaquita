import { useState } from 'react';
import { api } from '../../api/client';

// IMEI del teléfono, a mano para la persona: si lo roban o lo pierden, la operadora bloquea el equipo con
// ese número. Doble SIM y eSIM tienen 2 a 4. La app los manda cuando puede leerlos (equipo administrado);
// si no, la persona los escribe aquí (*#06# en el teléfono o la caja).

export function MisImeis({ equipoId, imeis, onCambio }: { equipoId: number; imeis: string[]; onCambio: () => void }) {
  const [editar, setEditar] = useState(false);
  const [texto, setTexto] = useState(imeis.join(', '));
  const [msg, setMsg] = useState('');
  const [copiado, setCopiado] = useState(false);

  const guardar = async () => {
    try { const r = await api.put<{ imeis: string[] }>(`/settings/mi-equipo/${equipoId}/imeis`, { imeis: texto }); setMsg(`Guardado: ${r.imeis.length} IMEI.`); setEditar(false); onCambio(); }
    catch (e: any) { setMsg(e.message); }
  };
  const copiar = async () => { try { await navigator.clipboard.writeText(imeis.join(', ')); setCopiado(true); setTimeout(() => setCopiado(false), 1500); } catch { /* noop */ } };

  return (
    <div className="mt-1.5 text-xs">
      <span className="text-[#605e5c]">IMEI (para bloquearlo en la operadora si te lo roban): </span>
      {imeis.length ? <>{imeis.map((i) => <code key={i} className="font-mono bg-[#f3f2f1] px-1.5 py-0.5 rounded mr-1">{i}</code>)}
        <button onClick={copiar} className="text-[#0078d4] hover:underline mr-2">{copiado ? 'Copiado' : 'Copiar'}</button></>
        : <span className="text-[#a4262c]">sin registrar. </span>}
      <button onClick={() => { setEditar(!editar); setMsg(''); }} className="text-[#0078d4] hover:underline">{imeis.length ? 'Agregar o corregir' : 'Registrar ahora'}</button>
      {editar && <div className="mt-2 flex flex-wrap items-center gap-2">
        <input value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Marca *#06# en el teléfono y escribe los números (separados por coma)" className="flex-1 min-w-[260px] px-2 py-1 border border-[#c8c6c4] rounded text-xs" />
        <button onClick={guardar} className="px-2.5 py-1 rounded bg-[#0078d4] text-white text-xs hover:bg-[#106ebe]">Guardar</button>
        <span className="text-[#605e5c]">Los IMEI están también en la caja y en la factura del teléfono.</span>
      </div>}
      {msg && <div className="mt-1 text-[#605e5c]">{msg}</div>}
    </div>
  );
}
