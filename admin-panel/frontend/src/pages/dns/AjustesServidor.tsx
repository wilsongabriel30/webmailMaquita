import { useState } from "react";
import { api } from "../../api/client";
import type { ServidorDns } from "./tipos";

/* IP pública del correo y de la web, y los servidores de nombres (ns1…ns5) con sus IP. */
export function AjustesServidor({ actual, onGuardado }: { actual: ServidorDns; onGuardado: () => void }) {
  const [ipCorreo, setIpCorreo] = useState(actual.ip_correo || "");
  const [ipWeb, setIpWeb] = useState(actual.ip_web || "");
  const [ns, setNs] = useState<{ nombre: string; ip: string }[]>(
    actual.ns?.length ? actual.ns : [{ nombre: "ns1", ip: "" }, { nombre: "ns2", ip: "" }]);
  const [estado, setEstado] = useState("");

  const guardar = async () => {
    setEstado("Guardando…");
    try {
      const r = await api.put<ServidorDns>("/dns/servidor", { ip_correo: ipCorreo.trim(), ip_web: ipWeb.trim() || null, ns: ns.map((n) => ({ nombre: n.nombre, ip: n.ip.trim() })) });
      setEstado(r.aviso ? `Guardado. Aviso: ${r.aviso}` : "Guardado.");
      onGuardado();
    } catch (e) { setEstado((e as Error).message); }
  };

  const campo = "px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue";
  return (
    <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-4">
      <h2 className="font-semibold text-ms-gray-130">Ajustes del servidor</h2>
      <p className="text-xs text-ms-gray-90">Se usan para armar cada zona nueva. Cada dominio tendrá sus propios servidores de nombres (ns1.dominio, ns2.dominio…) apuntando a estas IP.</p>
      <div className="grid sm:grid-cols-2 gap-3">
        <label className="text-sm text-ms-gray-90">IP pública del correo
          <input value={ipCorreo} onChange={(e) => setIpCorreo(e.target.value)} placeholder="192.0.2.10" className={`${campo} w-full mt-1`} /></label>
        <label className="text-sm text-ms-gray-90">IP pública de la web (si es otra)
          <input value={ipWeb} onChange={(e) => setIpWeb(e.target.value)} placeholder="igual que el correo" className={`${campo} w-full mt-1`} /></label>
      </div>
      <div className="space-y-2">
        <div className="text-sm text-ms-gray-90">Servidores de nombres (2 a 5)</div>
        {ns.map((n, i) => (
          <div key={n.nombre} className="flex items-center gap-2">
            <span className="w-10 text-sm font-mono">{n.nombre}</span>
            <input value={n.ip} onChange={(e) => setNs(ns.map((x, j) => (j === i ? { ...x, ip: e.target.value } : x)))} placeholder="IP pública" className={`${campo} w-56`} />
            {ns.length > 2 && i === ns.length - 1 && <button onClick={() => setNs(ns.slice(0, -1))} className="text-ms-red text-xs hover:underline">Quitar</button>}
          </div>
        ))}
        {ns.length < 5 && <button onClick={() => setNs([...ns, { nombre: `ns${ns.length + 1}`, ip: "" }])} className="text-ms-blue text-xs hover:underline">+ Añadir {`ns${ns.length + 1}`}</button>}
      </div>
      <div className="flex items-center gap-3">
        <button onClick={guardar} className="px-4 py-2 bg-ms-blue text-white rounded text-sm">Guardar</button>
        {estado && <span className="text-sm text-ms-gray-90">{estado}</span>}
      </div>
    </div>
  );
}
