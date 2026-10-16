import { useEffect, useState } from "react";
import { api } from "../../api/client";

interface Revision {
  app: string;
  version?: string;
  actualizaciones?: { nucleo: string[]; complementos: string[]; temas: string[] };
  integridad_nucleo?: string;
  detalle?: string;
}

/* Estado de seguridad de la aplicación de un sitio y actualización con un clic. */
export function SeguridadModal({ dominio, onCerrar }: { dominio: string; onCerrar: () => void }) {
  const [rev, setRev] = useState<Revision | null>(null);
  const [estado, setEstado] = useState("Revisando versión, actualizaciones e integridad de los archivos…");
  const [error, setError] = useState("");

  const revisar = () => {
    setError("");
    api.get<Revision>(`/sitios/${dominio}/seguridad`).then((r) => { setRev(r); setEstado(""); })
      .catch((e) => { setError(e.message); setEstado(""); });
  };
  useEffect(revisar, [dominio]);

  const actualizar = async () => {
    setEstado("Actualizando (puede tardar unos minutos)…"); setError("");
    try { setRev(await api.post<Revision>(`/sitios/${dominio}/actualizar`)); setEstado(""); }
    catch (e) { setError((e as Error).message); setEstado(""); }
  };

  const pend = rev?.actualizaciones;
  const hayPendientes = !!pend && (pend.nucleo.length + pend.complementos.length + pend.temas.length) > 0;
  const integra = rev?.integridad_nucleo === "correcta";

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" role="dialog" aria-modal="true">
      <div className="bg-white rounded shadow-lg w-full max-w-lg p-5 space-y-4">
        <h2 className="text-lg font-semibold text-ms-gray-130">Seguridad de {dominio}</h2>
        {estado && <p className="text-sm text-ms-blue">{estado}</p>}
        {error && <p className="text-sm text-ms-red">{error}</p>}
        {rev && (
          <table className="w-full text-sm">
            <tbody>
              <tr className="border-b border-ms-gray-30"><td className="py-2 text-ms-gray-90">Versión</td><td className="py-2">{rev.version || "-"}</td></tr>
              {pend && (
                <tr className="border-b border-ms-gray-30">
                  <td className="py-2 text-ms-gray-90 align-top">Actualizaciones</td>
                  <td className="py-2">
                    {!hayPendientes ? <span className="text-ms-green">Todo al día</span> : (
                      <ul className="list-disc ml-4 text-ms-red">
                        {pend.nucleo.length > 0 && <li>Núcleo: {pend.nucleo.join(", ")}</li>}
                        {pend.complementos.length > 0 && <li>Complementos: {pend.complementos.join(", ")}</li>}
                        {pend.temas.length > 0 && <li>Temas: {pend.temas.join(", ")}</li>}
                      </ul>
                    )}
                  </td>
                </tr>
              )}
              {rev.integridad_nucleo && (
                <tr className="border-b border-ms-gray-30">
                  <td className="py-2 text-ms-gray-90">Archivos del núcleo</td>
                  <td className={`py-2 ${integra ? "text-ms-green" : "text-ms-red font-medium"}`}>
                    {integra ? "Sin alteraciones" : rev.integridad_nucleo}
                  </td>
                </tr>
              )}
              {rev.detalle && <tr><td className="py-2 text-ms-gray-90 align-top">Detalle</td><td className="py-2 text-xs whitespace-pre-wrap">{rev.detalle}</td></tr>}
            </tbody>
          </table>
        )}
        <p className="text-xs text-ms-gray-90">
          Protecciones activas: cortafuegos de aplicación (OWASP CRS), límite de intentos de inicio de sesión, bloqueo automático de
          IP atacantes, XML-RPC y enumeración de usuarios cerrados, versión oculta, editor de archivos desactivado y
          actualizaciones automáticas.
        </p>
        <div className="flex justify-end gap-2">
          <button onClick={actualizar} disabled={!!estado} className="px-4 py-2 bg-ms-blue text-white rounded text-sm disabled:opacity-50">Actualizar ahora</button>
          <button onClick={onCerrar} className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90">Cerrar</button>
        </div>
      </div>
    </div>
  );
}
