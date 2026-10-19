import { useState } from "react";
import { api } from "../../api/client";
import { AvisoDns, type RegistroDns } from "./NuevoSitioForm";

/* Dominios alias de un sitio: otros dominios que muestran el mismo sitio (p. ej. ejemplo.com y ejemplo.com.ec). */
export function DominiosModal({ dominio, www, alias, sinHttps, onCerrar }: {
  dominio: string;
  www: boolean;
  alias: string[];
  sinHttps: string[];
  onCerrar: () => void;
}) {
  const [lista, setLista] = useState<string[]>(alias);
  const [nuevo, setNuevo] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState("");
  const [dns, setDns] = useState<RegistroDns[]>([]);
  const [fuera, setFuera] = useState<string[]>(sinHttps);

  const agregar = () => {
    const d = nuevo.trim().toLowerCase().replace(/^www\./, "");
    if (d && !lista.includes(d) && d !== dominio) setLista([...lista, d]);
    setNuevo("");
  };
  const guardar = async () => {
    setOcupado(true); setError(""); setDns([]);
    try {
      const r = await api.put<{ dns: RegistroDns[]; alias_sin_https: string[] }>(`/sitios/${dominio}/alias`, { alias: lista });
      setDns(r.dns || []); setFuera(r.alias_sin_https || []);
    } catch (e) { setError((e as Error).message); } finally { setOcupado(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 p-4" onClick={onCerrar}>
      <div className="bg-white rounded shadow-lg w-full max-w-lg p-5 space-y-3" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-base font-semibold text-ms-gray-130">Dominios de {dominio}</h2>
        <p className="text-xs text-ms-gray-90">Los dominios alias muestran este mismo sitio{www ? " (también con www.)" : ""}. Para una página distinta en un subdominio, cree un sitio nuevo de tipo «Subdominio».</p>
        <ul className="space-y-1">
          {lista.map((d) => (
            <li key={d} className="flex items-center justify-between text-sm border border-ms-gray-30 rounded px-3 py-1.5">
              <span>{d}{fuera.includes(d) && <span className="ml-2 text-[11px] text-amber-700">solo HTTP: todavía no apunta aquí</span>}</span>
              <button onClick={() => setLista(lista.filter((x) => x !== d))} className="text-ms-red text-xs hover:underline">Quitar</button>
            </li>
          ))}
          {lista.length === 0 && <li className="text-sm text-ms-gray-60">Sin alias.</li>}
        </ul>
        <div className="flex gap-2">
          <input placeholder="otrodominio.org" value={nuevo} onChange={(e) => setNuevo(e.target.value)} onKeyDown={(e) => e.key === "Enter" && agregar()}
            className="flex-1 px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
          <button onClick={agregar} disabled={lista.length >= 10} className="px-3 py-2 border border-ms-blue text-ms-blue rounded text-sm disabled:opacity-50">Añadir</button>
        </div>
        {error && <p className="text-sm text-ms-red">{error}</p>}
        <AvisoDns registros={dns} />
        <div className="flex gap-2 justify-end">
          <button onClick={guardar} disabled={ocupado} className="px-4 py-2 bg-ms-blue text-white rounded text-sm disabled:opacity-50">{ocupado ? "Guardando (con HTTPS puede tardar)…" : "Guardar"}</button>
          <button onClick={onCerrar} className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90">Cerrar</button>
        </div>
      </div>
    </div>
  );
}
