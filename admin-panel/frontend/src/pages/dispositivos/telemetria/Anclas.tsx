import { useEffect, useState } from "react";
import { api } from "../../../api/client";
import { rolActual } from "./tipos";

// Anclas de red por sede (etapa 1 de la triangulación propia): subredes o bloques públicos con
// coordenadas fijas. Un teléfono que reporta desde esa red está en esa sede, sin GPS.

interface Ancla { id: number; tipo: string; valor: string; sede: string; nombre: string; lat: number; lon: number; radio_m: number; activa: boolean; equipos_ahora: number }

export function Anclas() {
  const [lista, setLista] = useState<Ancla[]>([]);
  const [abierto, setAbierto] = useState(false);
  const [f, setF] = useState({ tipo: "red", valor: "", sede: "", nombre: "", lat: "", lon: "", radio_m: 60 });
  const [error, setError] = useState("");
  const admin = rolActual() !== "viewer";
  const cargar = () => api.get<{ anclas: Ancla[] }>("/dispositivos/anclas").then((r) => setLista(r.anclas)).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, []);
  const crear = async () => { try { setError(""); await api.post("/dispositivos/anclas", f); setF({ ...f, valor: "", nombre: "" }); cargar(); } catch (e: any) { setError(e.message); } };
  const borrar = async (id: number) => { if (confirm("¿Quitar esta ancla?")) { await api.del(`/dispositivos/anclas/${id}`); cargar(); } };

  return (
    <div className="bg-white rounded-lg border border-ms-gray-30 p-3">
      <div className="flex items-center gap-3 text-sm">
        <h3 className="font-semibold">Anclas de red por sede</h3>
        <span className="text-xs text-ms-gray-60">Si un teléfono reporta desde una de estas redes, el servidor sabe en qué sede está sin GPS (columna «Red»). Coordenadas fijas de cada sede.</span>
        <button onClick={() => setAbierto(!abierto)} className="ml-auto text-xs text-ms-blue hover:underline">{abierto ? "Ocultar" : `Ver (${lista.length})`}</button>
      </div>
      {abierto && <div className="mt-3 space-y-3">
        {error && <div className="text-sm px-3 py-2 rounded bg-red-50 text-red-700">{error}</div>}
        <table className="w-full text-sm">
          <thead><tr className="bg-ms-gray-10">{["Sede", "Red / BSSID", "Descripción", "Coordenadas", "Radio", "Equipos ahora", ""].map((h) => <th key={h} className="text-left px-3 py-2 font-medium text-ms-gray-90 text-xs">{h}</th>)}</tr></thead>
          <tbody>{lista.map((a) => <tr key={a.id} className="border-t border-ms-gray-20">
            <td className="px-3 py-1.5">{a.sede}</td><td className="px-3 py-1.5 font-mono text-xs">{a.valor}</td><td className="px-3 py-1.5 text-xs">{a.nombre}</td>
            <td className="px-3 py-1.5 text-xs"><a className="text-ms-blue hover:underline" target="_blank" rel="noreferrer" href={`https://www.openstreetmap.org/?mlat=${a.lat}&mlon=${a.lon}#map=18/${a.lat}/${a.lon}`}>{a.lat.toFixed(5)}, {a.lon.toFixed(5)}</a></td>
            <td className="px-3 py-1.5 text-xs">±{a.radio_m} m</td><td className="px-3 py-1.5">{a.equipos_ahora}</td>
            <td className="px-3 py-1.5 text-right">{admin && <button onClick={() => borrar(a.id)} className="text-xs text-ms-red hover:underline">Quitar</button>}</td>
          </tr>)}</tbody>
        </table>
        {admin && <div className="flex flex-wrap items-end gap-2 text-xs">
          <label>Tipo<select value={f.tipo} onChange={(e) => setF({ ...f, tipo: e.target.value })} className="mt-1 block px-2 py-1 border border-ms-gray-40 rounded"><option value="red">Red (CIDR)</option><option value="bssid">Punto de acceso (BSSID)</option></select></label>
          <label>Red o BSSID<input value={f.valor} onChange={(e) => setF({ ...f, valor: e.target.value })} placeholder="193.16.5.0/24" className="mt-1 block w-40 px-2 py-1 border border-ms-gray-40 rounded font-mono" /></label>
          <label>Sede<input value={f.sede} onChange={(e) => setF({ ...f, sede: e.target.value })} placeholder="Guayaquil" className="mt-1 block w-36 px-2 py-1 border border-ms-gray-40 rounded" /></label>
          <label>Descripción<input value={f.nombre} onChange={(e) => setF({ ...f, nombre: e.target.value })} className="mt-1 block w-48 px-2 py-1 border border-ms-gray-40 rounded" /></label>
          <label>Latitud<input value={f.lat} onChange={(e) => setF({ ...f, lat: e.target.value })} placeholder="-0.2772" className="mt-1 block w-24 px-2 py-1 border border-ms-gray-40 rounded" /></label>
          <label>Longitud<input value={f.lon} onChange={(e) => setF({ ...f, lon: e.target.value })} placeholder="-78.5464" className="mt-1 block w-24 px-2 py-1 border border-ms-gray-40 rounded" /></label>
          <label>Radio (m)<input type="number" value={f.radio_m} onChange={(e) => setF({ ...f, radio_m: Number(e.target.value) })} className="mt-1 block w-20 px-2 py-1 border border-ms-gray-40 rounded" /></label>
          <button onClick={crear} className="px-3 py-1.5 bg-ms-blue text-white rounded hover:bg-ms-blue-dark">Guardar ancla</button>
        </div>}
      </div>}
    </div>
  );
}
