import { useEffect, useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";
import { AjustesServidor } from "./dns/AjustesServidor";
import { EditorZona } from "./dns/EditorZona";
import type { ServidorDns } from "./dns/tipos";

interface Estado { bind: boolean; servidor: ServidorDns; zonas: number; lista: { zona: string; registros: number; serial: number; creada: string }[] }

export function ZonasDns() {
  const [estado, setEstado] = useState<Estado | null>(null);
  const [error, setError] = useState("");
  const [abierta, setAbierta] = useState<string | null>(new URLSearchParams(window.location.search).get("zona"));
  const [ajustes, setAjustes] = useState(false);

  const cargar = () => api.get<Estado>("/dns").then((d) => { setEstado(d); setError(""); }).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, []);

  const borrar = async (zona: string) => {
    const conf = prompt(`Se borrará la zona ${zona}: el dominio dejará de resolver desde este servidor (correo y web incluidos).\n\nEscriba la zona para confirmar:`);
    if (conf === null) return;
    try { await api.del(`/dns/${zona}`, { confirmacion: conf }); cargar(); } catch (e) { setError((e as Error).message); }
  };

  const sinAjustes = estado && !estado.servidor?.ip_correo;
  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ms-gray-130">Zonas DNS</h1>
        <div className="flex items-center gap-2">
          <SectionHelp titulo="Zonas DNS" items={[
            { titulo: "Para qué sirve", desc: "Este servidor responde por sus propios dominios (servidor DNS autoritativo). Aquí se ven y cambian sus registros." },
            { titulo: "Zona nueva", desc: "Se crean desde «Nuevo dominio»: la zona sale completa para el correo y la web." },
            { titulo: "Registros", desc: "Cada cambio se valida con BIND antes de aplicarse; si algo está mal, no se publica nada. Los marcados con ● los creó el asistente." },
            { titulo: "Ajustes", desc: "IP pública del correo y de la web y los servidores de nombres (ns1…ns5) con sus IP. Cada dominio usa sus propios ns1.dominio, ns2.dominio…" },
            { titulo: "Cómo lo ve Internet", desc: "Comprueba la delegación en el registrador y que el dominio, el correo y la web respondan desde fuera." },
          ]} />
          <button onClick={() => setAjustes(!ajustes)} className="px-3 py-1.5 border border-ms-blue text-ms-blue rounded text-sm hover:bg-ms-blue-lighter">Ajustes</button>
        </div>
      </div>
      {error && <div className="bg-red-50 border border-red-200 text-ms-red rounded px-4 py-2 text-sm">{error}</div>}
      {estado && !estado.bind && (
        <div className="bg-amber-50 border border-amber-200 rounded p-4 text-sm">El DNS aún no está instalado. Como administrador del sistema, ejecute:
          <pre className="mt-2 bg-white border rounded p-2 text-xs">sudo bash deploy/webmail/instalar-app.sh dns</pre></div>
      )}
      {estado && (ajustes || sinAjustes) && <AjustesServidor actual={estado.servidor || {}} onGuardado={() => { cargar(); setAjustes(false); }} />}
      {estado?.servidor?.aviso && <p className="text-xs text-amber-700">{estado.servidor.aviso}</p>}

      {abierta ? (
        <EditorZona zona={abierta} onVolver={() => { setAbierta(null); cargar(); }} />
      ) : estado && (
        <div className="bg-white rounded border border-ms-gray-30 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-ms-gray-20 border-b border-ms-gray-30">
              <tr>
                <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Zona</th>
                <th className="text-center px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Registros</th>
                <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Serie</th>
                <th className="text-right px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ms-gray-30">
              {estado.lista.map((z) => (
                <tr key={z.zona} className="hover:bg-ms-blue-lighter/50">
                  <td className="px-4 py-2.5"><button onClick={() => setAbierta(z.zona)} className="font-medium text-ms-gray-130 hover:underline">{z.zona}</button></td>
                  <td className="px-4 py-2.5 text-center">{z.registros}</td>
                  <td className="px-4 py-2.5 font-mono text-xs">{z.serial}</td>
                  <td className="px-4 py-2.5 text-right text-xs">
                    <button onClick={() => setAbierta(z.zona)} className="text-ms-blue hover:underline mr-4">Editar</button>
                    <button onClick={() => borrar(z.zona)} className="text-ms-red hover:underline">Borrar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {estado.lista.length === 0 && <div className="p-8 text-center text-ms-gray-60 text-sm">Sin zonas. Use «Nuevo dominio».</div>}
        </div>
      )}
    </div>
  );
}
