import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { TransferenciasDns } from "./tipos";

type AccionTsig = "mantener" | "generar" | "quitar";

/* Servidores secundarios: a quién se transfieren las zonas, a quién se avisa y la clave TSIG opcional. */
export function Secundarios() {
  const [actual, setActual] = useState<TransferenciasDns | null>(null);
  const [transferir, setTransferir] = useState("");
  const [notificar, setNotificar] = useState("");
  const [oculto, setOculto] = useState(false);
  const [tsig, setTsig] = useState<AccionTsig>("mantener");
  const [secreto, setSecreto] = useState("");
  const [estado, setEstado] = useState("");

  const poner = (t: TransferenciasDns) => {
    setActual(t);
    setTransferir(t.transferencias.transferir_a.join("\n"));
    setNotificar(t.transferencias.notificar_a.join("\n"));
    setOculto(t.transferencias.maestro_oculto);
    setTsig("mantener");
  };
  useEffect(() => { api.get<TransferenciasDns>("/dns/transferencias").then(poner).catch((e) => setEstado(e.message)); }, []);

  const lista = (texto: string) => texto.split(/[\s,]+/).map((x) => x.trim()).filter(Boolean);
  const guardar = async () => {
    setEstado("Guardando y comprobando con BIND…");
    try {
      const r = await api.put<TransferenciasDns>("/dns/transferencias", { transferir_a: lista(transferir), notificar_a: lista(notificar), maestro_oculto: oculto, tsig });
      poner(r); setSecreto("");
      setEstado(r.aviso ? `Guardado. ${r.aviso}` : "Guardado y aplicado a todas las zonas.");
    } catch (e) { setEstado((e as Error).message); }
  };
  const verSecreto = async () => {
    if (!confirm("Se mostrará el secreto TSIG. Cópielo solo al secundario, por un canal seguro. ¿Continuar?")) return;
    try { const r = await api.post<TransferenciasDns>("/dns/transferencias/secreto"); setSecreto(r.transferencias.tsig?.para_el_secundario || ""); }
    catch (e) { setEstado((e as Error).message); }
  };

  if (!actual) return estado ? <p className="text-sm text-ms-red">{estado}</p> : null;
  const clave = actual.transferencias.tsig;
  const propias = Object.keys(actual.zonas_con_ajuste_propio);
  const campo = "px-3 py-2 border border-ms-gray-40 rounded text-sm font-mono focus:outline-none focus:border-ms-blue w-full mt-1";
  return (
    <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-4">
      <h2 className="font-semibold text-ms-gray-130">Servidores secundarios</h2>
      <p className="text-xs text-ms-gray-90">Para que otros servidores DNS (otro servidor propio o uno externo como HE.net) tengan copia de las zonas. Vacío = nadie puede pedirlas (lo de siempre). Una IP o red por línea.</p>
      <div className="grid sm:grid-cols-2 gap-3">
        <label className="text-sm text-ms-gray-90">Pueden pedir las zonas (IP o red)
          <textarea rows={3} value={transferir} onChange={(e) => setTransferir(e.target.value)} placeholder={"198.51.100.53\n2001:db8:53::/64"} className={campo} /></label>
        <label className="text-sm text-ms-gray-90">Avisar de cada cambio (IP, puerto opcional)
          <textarea rows={3} value={notificar} onChange={(e) => setNotificar(e.target.value)} placeholder={"198.51.100.53\n203.0.113.2:5353"} className={campo} /></label>
      </div>
      <label className="flex items-start gap-2 text-sm text-ms-gray-90">
        <input type="checkbox" checked={oculto} onChange={(e) => setOculto(e.target.checked)} className="mt-1" />
        <span>Maestro oculto: este servidor no figura en los servidores de nombres; solo lo consultan los secundarios. Los ns1, ns2… de «Ajustes» deben apuntar a las IP de los secundarios públicos.</span>
      </label>
      <div className="text-sm text-ms-gray-90 space-y-1">
        <div>Clave TSIG: {clave ? <span className="font-mono text-xs">{clave.nombre} ({clave.algoritmo}){clave.clave_presente ? "" : " · falta el archivo"}</span> : "sin clave (solo por IP)"}</div>
        <select value={tsig} onChange={(e) => setTsig(e.target.value as AccionTsig)} className="px-2 py-1 border border-ms-gray-40 rounded text-sm">
          <option value="mantener">{clave ? "Mantener la clave" : "Sin clave"}</option>
          <option value="generar">{clave ? "Generar una clave nueva (el secundario deberá cambiarla)" : "Generar una clave"}</option>
          {clave && <option value="quitar">Quitar la clave</option>}
        </select>
        {clave && <button onClick={verSecreto} className="ml-3 text-ms-blue text-xs hover:underline">Ver clave para el secundario</button>}
      </div>
      {secreto && <pre className="bg-ms-gray-20 border rounded p-2 text-xs overflow-x-auto">{secreto}</pre>}
      {propias.length > 0 && <p className="text-xs text-ms-gray-60">Con ajuste propio (consola: maquita-dns servidor --zona): {propias.join(", ")}</p>}
      <div className="flex items-center gap-3">
        <button onClick={guardar} className="px-4 py-2 bg-ms-blue text-white rounded text-sm">Guardar</button>
        {estado && <span className="text-sm text-ms-gray-90">{estado}</span>}
      </div>
    </div>
  );
}
