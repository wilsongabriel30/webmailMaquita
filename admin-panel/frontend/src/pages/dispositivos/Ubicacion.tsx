import { useState } from "react";
import { api } from "../../api/client";
import { Mapa } from "./Mapa";
import { Equipo, fechaHora } from "./tipos";

interface Fila { id: number; tomada_en: string; lat: number; lon: number; precision_m?: number; fuente?: string; origen: string; bateria?: number; rssi?: number; visto_por_nombre?: string }
const ORIGEN: Record<string, string> = { periodica: "periódica", comando: "pedida desde el panel", perdido: "modo perdido", avistamiento: "vista por otro teléfono" };

/** Ubicación de un equipo. Cada consulta pide un motivo y queda en la auditoría del panel. */
export function Ubicacion({ equipo, onCambio }: { equipo: Equipo; onCambio: () => void }) {
  const [filas, setFilas] = useState<Fila[] | null>(null);
  const [sel, setSel] = useState(0);
  const [horas, setHoras] = useState(24);
  const [error, setError] = useState("");
  const [firmada, setFirmada] = useState(equipo.politica_firmada_en?.slice(0, 10) || "");
  const puede = equipo.ubicacion_autorizada || equipo.estado === "perdido";

  const consultar = async () => {
    const motivo = prompt("Motivo de la consulta de ubicación (queda en la auditoría con su usuario):");
    if (!motivo) return;
    try { setError(""); const r = await api.post<{ ubicaciones: Fila[] }>(`/dispositivos/equipos/${equipo.id}/ubicaciones`, { motivo, horas }); setFilas(r.ubicaciones); setSel(0); }
    catch (e: any) { setError(e.message); }
  };
  const autorizar = async (autorizada: boolean) => {
    try { setError(""); await api.post(`/dispositivos/equipos/${equipo.id}/autorizacion-ubicacion`, { autorizada, politica_firmada_en: firmada }); onCambio(); }
    catch (e: any) { setError(e.message); }
  };

  return (
    <div>
      <h3 className="text-sm font-semibold mb-2">Ubicación</h3>
      {error && <div className="text-sm px-3 py-2 mb-2 rounded bg-red-50 text-red-700">{error}</div>}
      <div className="bg-ms-gray-10 rounded p-3 text-sm flex flex-wrap items-center gap-3 mb-3">
        {equipo.ubicacion_autorizada
          ? <><span>Ubicación periódica <strong>activa</strong> · política firmada el {equipo.politica_firmada_en?.slice(0, 10)}</span>
              <button onClick={() => autorizar(false)} className="text-xs text-ms-red hover:underline">Desactivar</button></>
          : <><span>Ubicación periódica <strong>desactivada</strong>: solo se guarda si el equipo se declara perdido. Para activarla, el custodio debe haber firmado la política de uso:</span>
              <input type="date" value={firmada} onChange={(e) => setFirmada(e.target.value)} className="px-2 py-1 text-sm border border-ms-gray-40 rounded" />
              <button onClick={() => autorizar(true)} disabled={!firmada} className="px-2.5 py-1 text-xs bg-ms-blue text-white rounded disabled:opacity-50">Activar</button></>}
      </div>
      <div className="flex items-center gap-2 text-sm mb-3">
        <select value={horas} onChange={(e) => setHoras(Number(e.target.value))} className="px-2 py-1 border border-ms-gray-40 rounded">
          <option value={6}>Últimas 6 horas</option><option value={24}>Último día</option><option value={168}>Última semana</option><option value={720}>Último mes</option>
        </select>
        <button onClick={consultar} disabled={!puede && !filas} title={puede ? "" : "No hay posiciones guardadas: la ubicación no está autorizada y el equipo no está perdido"}
          className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark disabled:opacity-50">Ver ubicaciones</button>
      </div>
      {filas && !filas.length && <p className="text-sm text-ms-gray-60">No hay posiciones en ese periodo.</p>}
      {filas && filas.length > 0 && <div className="grid md:grid-cols-2 gap-4">
        <Mapa actual={filas[sel]} rastro={filas.filter((_, i) => i !== sel)} />
        <ul className="text-sm max-h-[420px] overflow-y-auto divide-y divide-ms-gray-20">
          {filas.map((u, i) => <li key={u.id} onClick={() => setSel(i)} className={`px-2 py-1.5 cursor-pointer ${i === sel ? "bg-blue-50" : "hover:bg-ms-gray-10"}`}>
            <div className="flex justify-between"><span>{fechaHora(u.tomada_en)}</span><span className="text-xs text-ms-gray-60">{u.precision_m ? `±${Math.round(u.precision_m)} m` : ""}{u.bateria != null ? ` · ${u.bateria}%` : ""}</span></div>
            <div className="text-xs text-ms-gray-60">{ORIGEN[u.origen] || u.origen}{u.visto_por_nombre ? ` (${u.visto_por_nombre}${u.rssi ? `, señal ${u.rssi} dBm` : ""})` : ""}{u.fuente ? ` · ${u.fuente}` : ""}</div>
          </li>)}
        </ul>
      </div>}
    </div>
  );
}
