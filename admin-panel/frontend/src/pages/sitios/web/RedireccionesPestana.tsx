import { useState } from "react";
import { api } from "../../../api/client";
import { botonPrincipal, campo, type EstadoWeb, type PropsPestana, type Redireccion } from "./tipos";

/* Redirecciones 301/302: de una ruta a otra dirección, o de todo el dominio (p. ej. al cambiar de dominio). */
export function RedireccionesPestana({ dominio, estado, ocupado, hacer }: PropsPestana) {
  const lista = estado.redirecciones.lista;
  const [todo, setTodo] = useState(false);
  const [origen, setOrigen] = useState("");
  const [destino, setDestino] = useState("");
  const [codigo, setCodigo] = useState<301 | 302>(301);
  const [subrutas, setSubrutas] = useState(false);
  const [conservar, setConservar] = useState(true);

  const guardar = (nueva: Redireccion[], texto: string) =>
    hacer(texto, () => api.put<EstadoWeb>(`/sitios/${dominio}/web/redirecciones`, { redirecciones: nueva }));
  const agregar = async () => {
    const r: Redireccion = todo
      ? { origen: "*", destino: destino.trim(), codigo, conservar_ruta: conservar }
      : { origen: origen.trim(), destino: destino.trim(), codigo, subrutas };
    if (await guardar([...lista.filter((x) => x.origen !== r.origen), r], "Redirección guardada.")) { setOrigen(""); setDestino(""); }
  };

  return (
    <div className="space-y-3">
      <div className="border border-ms-gray-30 rounded p-3 space-y-2">
        <div className="flex flex-wrap gap-4 text-sm">
          <label><input type="radio" checked={!todo} onChange={() => setTodo(false)} className="mr-1" />Una ruta</label>
          <label><input type="radio" checked={todo} onChange={() => setTodo(true)} className="mr-1" />Todo el dominio</label>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {!todo && <input placeholder="/pagina-vieja" value={origen} onChange={(e) => setOrigen(e.target.value)} className={`${campo} font-mono w-56`} />}
          <span className="text-ms-gray-60 text-sm">→</span>
          <input placeholder="https://example.com/pagina-nueva" value={destino} onChange={(e) => setDestino(e.target.value)} className={`${campo} font-mono flex-1 min-w-64`} />
          <select value={codigo} onChange={(e) => setCodigo(Number(e.target.value) as 301 | 302)} className={campo}>
            <option value={301}>301 permanente</option>
            <option value={302}>302 temporal</option>
          </select>
        </div>
        <label className="block text-xs text-ms-gray-90">
          {todo
            ? <><input type="checkbox" checked={conservar} onChange={(e) => setConservar(e.target.checked)} className="mr-1" />Conservar la ruta (example.org/contacto → destino/contacto)</>
            : <><input type="checkbox" checked={subrutas} onChange={(e) => setSubrutas(e.target.checked)} className="mr-1" />También lo que hay debajo (/blog/entrada → destino/entrada)</>}
        </label>
        <button disabled={ocupado || !destino.trim() || (!todo && !origen.trim())} onClick={agregar} className={botonPrincipal}>Agregar</button>
        <p className="text-[11px] text-ms-gray-60">Use 301 cuando el cambio es definitivo (los buscadores pasan la posición a la dirección nueva) y 302 si es pasajero. La renovación del certificado (/.well-known/) nunca se redirige.</p>
      </div>

      <table className="w-full text-sm">
        <thead className="bg-ms-gray-20 text-xs text-ms-gray-90"><tr>
          <th className="text-left px-2 py-1.5">Desde</th><th className="text-left px-2 py-1.5">Hacia</th><th className="px-2 py-1.5">Tipo</th><th></th></tr></thead>
        <tbody className="divide-y divide-ms-gray-30">
          {lista.map((r) => (
            <tr key={r.origen}>
              <td className="px-2 py-1.5 font-mono text-xs">{r.origen === "*" ? <b>todo el dominio</b> : r.origen}{r.subrutas && <span className="text-ms-gray-60"> y debajo</span>}</td>
              <td className="px-2 py-1.5 font-mono text-xs break-all">{r.destino}{r.origen === "*" && r.conservar_ruta && <span className="text-ms-gray-60">/…</span>}</td>
              <td className="px-2 py-1.5 text-xs text-center">{r.codigo}</td>
              <td className="px-2 py-1.5 text-right"><button disabled={ocupado} onClick={() => confirm(`¿Quitar la redirección de ${r.origen === "*" ? "todo el dominio" : r.origen}?`) && guardar(lista.filter((x) => x.origen !== r.origen), "Redirección quitada.")} className="text-xs text-ms-red hover:underline">Quitar</button></td>
            </tr>
          ))}
          {lista.length === 0 && <tr><td colSpan={4} className="px-2 py-4 text-center text-ms-gray-60 text-sm">Sin redirecciones.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}
