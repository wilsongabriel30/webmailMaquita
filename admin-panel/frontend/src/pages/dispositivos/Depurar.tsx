import { useState } from "react";
import { api } from "../../api/client";
import { rolActual } from "./telemetria/tipos";

// Botón «Depurar»: en un paso borra lo que sobra (códigos anulados/agotados/caducados sin equipo,
// equipos retirados o de baja y los que nunca reportaron, mensajes sin destinatarios o caducados).
// Primero muestra la vista previa; solo borra al escribir DEPURAR. Nunca toca equipos activos.

interface Vista { vista_previa: boolean; codigos: number; equipos: { id: number; nombre: string; estado: string; custodio?: string }[]; mensajes: { id: number; titulo: string }[]; carpetas_borradas?: number }

export function Depurar({ onHecho }: { onHecho: () => void }) {
  const [v, setV] = useState<Vista | null>(null);
  const [palabra, setPalabra] = useState("");
  const [msg, setMsg] = useState("");
  if (rolActual() === "viewer") return null;

  const previsualizar = async () => { setMsg(""); setPalabra(""); try { setV(await api.post<Vista>("/dispositivos/depurar", {})); } catch (e: any) { setMsg(e.message); } };
  const ejecutar = async () => {
    try { const r = await api.post<Vista>("/dispositivos/depurar", { confirmacion: palabra }); setV(null); setMsg(`Depurado: ${r.codigos} códigos, ${r.equipos.length} equipos y ${r.mensajes.length} mensajes.`); onHecho(); }
    catch (e: any) { setMsg(e.message); }
  };
  const nada = v && !v.codigos && !v.equipos.length && !v.mensajes.length;

  return (
    <div className="relative">
      <button onClick={previsualizar} className="px-3 py-1.5 text-sm border border-ms-gray-40 rounded hover:bg-ms-gray-10" title="Borra en un paso códigos, equipos y mensajes que ya no sirven">Depurar</button>
      {msg && <span className="ml-2 text-xs text-ms-gray-60">{msg}</span>}
      {v && <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={() => setV(null)}>
        <div className="bg-white rounded-lg shadow-xl max-w-lg w-full p-5 text-sm" onClick={(e) => e.stopPropagation()}>
          <h3 className="text-base font-semibold mb-2">Depurar lo que sobra</h3>
          {nada ? <p className="text-ms-gray-60">No hay nada que depurar: todo lo que queda está en uso.</p> : <>
            <ul className="space-y-1.5 mb-3">
              <li><strong>{v.codigos}</strong> códigos anulados, agotados o caducados sin equipo enrolado.</li>
              <li><strong>{v.equipos.length}</strong> equipos retirados, de baja o que nunca reportaron:
                {v.equipos.length > 0 && <ul className="pl-4 mt-1 text-xs text-ms-gray-60">{v.equipos.map((e) => <li key={e.id}>#{e.id} {e.nombre} · {e.estado}{e.custodio ? ` · ${e.custodio}` : ""}</li>)}</ul>}
              </li>
              <li><strong>{v.mensajes.length}</strong> mensajes sin destinatarios o caducados hace más de 30 días.</li>
            </ul>
            <p className="text-xs text-ms-gray-60 mb-3">Se borran con todo su historial (y las carpetas de respaldo en disco de esos equipos). No se toca ningún equipo activo ni perdido. Queda en la auditoría.</p>
            <label className="text-xs">Para confirmar escribe <strong>DEPURAR</strong>
              <input value={palabra} onChange={(e) => setPalabra(e.target.value)} className="mt-1 block w-full px-2.5 py-1.5 text-sm border border-ms-gray-40 rounded" /></label>
          </>}
          <div className="flex gap-2 justify-end mt-4">
            <button onClick={() => setV(null)} className="px-3 py-1.5 text-sm border border-ms-gray-40 rounded">Cerrar</button>
            {!nada && <button onClick={ejecutar} disabled={palabra.trim().toUpperCase() !== "DEPURAR"} className="px-3 py-1.5 text-sm bg-ms-red text-white rounded disabled:opacity-50">Borrar</button>}
          </div>
        </div>
      </div>}
    </div>
  );
}
