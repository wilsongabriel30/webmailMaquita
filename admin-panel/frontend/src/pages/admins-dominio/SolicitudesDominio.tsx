import { useEffect, useState } from "react";
import { api } from "../../api/client";

interface Solicitud {
  id: number; admin_username: string; tipo: string; objetivo: string; dominio: string; motivo: string;
  estado: string; resuelto_por: string | null; resuelto_en: string | null; creado_en: string;
}

export function SolicitudesDominio() {
  const [lista, setLista] = useState<Solicitud[]>([]);
  const [error, setError] = useState("");
  const cargar = () => api.get<Solicitud[]>("/admins-dominio/solicitudes").then(setLista).catch(() => {});
  useEffect(() => { cargar(); }, []);

  const resolver = async (s: Solicitud, aprobar: boolean) => {
    const sitio = s.tipo === "baja_sitio";
    const texto = sitio
      ? (aprobar
        ? `DAR DE BAJA el sitio web "${s.objetivo}"? Sus archivos y bases pasan a la papelera del servidor y se quitan sus registros DNS. La pidió ${s.admin_username}.`
        : `Rechazar la baja del sitio "${s.objetivo}"? El sitio sigue publicado como está.`)
      : (aprobar
        ? `ELIMINAR DEFINITIVAMENTE la cuenta "${s.objetivo}"? No tiene vuelta atrás. La pidió ${s.admin_username}.`
        : `Rechazar la solicitud y REACTIVAR la cuenta "${s.objetivo}"?`);
    if (!confirm(texto)) return;
    setError("");
    try { await api.post(`/admins-dominio/solicitudes/${s.id}/resolver`, { aprobar }); cargar(); }
    catch (e) { setError(e instanceof Error ? e.message : "No se pudo resolver"); }
  };

  const pendientes = lista.filter((s) => s.estado === "pendiente");

  return (
    <div className="bg-white rounded border border-ms-gray-30">
      <div className="px-4 py-2.5 border-b border-ms-gray-30 text-sm font-medium text-ms-gray-130">
        Solicitudes del portal de dominio (cuentas y sitios web)
        {pendientes.length > 0 && <span className="ml-2 px-2 py-0.5 rounded text-[10px] bg-red-50 text-ms-red">{pendientes.length} pendiente{pendientes.length > 1 ? "s" : ""}</span>}
      </div>
      {error && <div className="px-4 py-2 text-ms-red text-xs">{error}</div>}
      <div className="max-h-80 overflow-auto">
        <table className="w-full text-xs">
          <tbody className="divide-y divide-ms-gray-30">
            {lista.map((s) => (
              <tr key={s.id}>
                <td className="px-4 py-2 text-ms-gray-60 whitespace-nowrap">{new Date(s.creado_en).toLocaleString()}</td>
                <td className="px-4 py-2"><div className="font-medium text-ms-gray-130">{s.tipo === "baja_sitio" ? "Baja del sitio web " : "Eliminar la cuenta "}{s.objetivo}</div><div className="text-ms-gray-60">{s.motivo || "Sin motivo"}</div></td>
                <td className="px-4 py-2 text-ms-gray-90">{s.admin_username}</td>
                <td className="px-4 py-2 text-right whitespace-nowrap space-x-3">
                  {s.estado === "pendiente" ? (<>
                    <button onClick={() => resolver(s, true)} className="text-ms-red hover:underline">{s.tipo === "baja_sitio" ? "Dar de baja el sitio" : "Eliminar la cuenta"}</button>
                    <button onClick={() => resolver(s, false)} className="text-ms-blue hover:underline">{s.tipo === "baja_sitio" ? "Rechazar" : "Rechazar y reactivar"}</button>
                  </>) : <span className="text-ms-gray-60">{s.estado} por {s.resuelto_por}</span>}
                </td>
              </tr>
            ))}
            {!lista.length && <tr><td className="px-4 py-4 text-center text-ms-gray-60">Sin solicitudes.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
