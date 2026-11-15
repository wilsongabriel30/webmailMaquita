import { Fragment, useEffect, useState } from "react";
import { api } from "../../api/client";
import { CuentaAtras } from "./CuentaAtras";
import { fechaHora } from "./tipos";
import { CIERRE, COLOR_SITUACION, SITUACION, Tunel, duracion } from "./tunelTipos";

// Auditoría de los túneles de soporte: quién pidió abrir cada uno, a qué equipo, cuándo, con qué
// resultado y cuánto estuvo abierto. Sale de las órdenes firmadas y de su registro, que no se pueden editar.

export function AuditoriaTunel() {
  const [lista, setLista] = useState<Tunel[] | null>(null);
  const [abierta, setAbierta] = useState<string | null>(null);
  const [error, setError] = useState("");
  const cargar = () => api.get<{ tuneles: Tunel[] }>("/flota/tunel/auditoria?limite=300").then((r) => { setLista(r.tuneles); setError(""); }).catch((e) => setError(e.message));
  useEffect(() => { cargar(); const t = setInterval(cargar, 30000); return () => clearInterval(t); }, []);

  const columnas = ["Equipo", "Quién lo pidió", "Motivo", "Resultado", "Abierto", "Cerrado", "Duración", "Conexión", ""];
  return (
    <div className="space-y-3">
      <p className="text-xs text-ms-gray-60">Cada apertura de un túnel de soporte da acceso remoto temporal a un equipo. Aquí queda quién la pidió, a qué equipo, cuándo, con qué resultado y cuánto duró. Se abre y se cierra desde la ficha de cada equipo (pestaña Inventario).</p>
      {error && <div className="text-sm px-3 py-2 rounded bg-red-50 text-red-700">{error}</div>}
      <div className="bg-white rounded-lg border border-ms-gray-30 overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="bg-ms-gray-10">{columnas.map((h) => <th key={h} className="text-left px-3 py-2.5 font-medium text-ms-gray-90 text-xs">{h}</th>)}</tr></thead>
          <tbody>
            {(lista || []).map((t) => <Fragment key={t.orden_id}>
              <tr className="border-t border-ms-gray-20 align-top">
                <td className="px-3 py-2 font-medium">{t.nombre}</td>
                <td className="px-3 py-2 text-xs whitespace-nowrap">{t.emitida_por}<div className="text-ms-gray-60">{fechaHora(t.emitida_en)}{t.ip_panel ? ` · desde ${t.ip_panel}` : ""}</div></td>
                <td className="px-3 py-2 text-xs max-w-xs">{t.motivo}</td>
                <td className={`px-3 py-2 text-xs ${COLOR_SITUACION[t.situacion]}`}>{SITUACION[t.situacion]}
                  {(t.situacion === "abierto" || t.situacion === "cierre_solicitado") && t.expira_en && <div>quedan <CuentaAtras hasta={t.expira_en} onFin={cargar} /></div>}</td>
                <td className="px-3 py-2 text-xs whitespace-nowrap">{fechaHora(t.abierto_en)}</td>
                <td className="px-3 py-2 text-xs">{t.cerrado_en ? <><span className="whitespace-nowrap">{fechaHora(t.cerrado_en)}</span><div className="text-ms-gray-60">{CIERRE[t.cierre || ""] || t.cierre}{t.cierre === "orden de cierre" && t.cierre_por ? ` por ${t.cierre_por}${t.cierre_motivo ? `: ${t.cierre_motivo}` : ""}` : ""}</div></> : "—"}</td>
                <td className="px-3 py-2 text-xs whitespace-nowrap">{duracion(t.duracion_s)}<div className="text-ms-gray-60">de {t.parametros.minutos} min pedidos</div></td>
                <td className="px-3 py-2 text-xs">puerto {t.parametros.puerto_remoto}<div className="text-ms-gray-60">{t.parametros.modo === "automatico" ? "clave automática" : t.parametros.clave_huella ? "clave pegada a mano" : "clave instalada en el equipo"}</div></td>
                <td className="px-3 py-2 text-right text-xs"><button onClick={() => setAbierta(abierta === t.orden_id ? null : t.orden_id)} className="text-ms-blue hover:underline">Detalle</button></td>
              </tr>
              {abierta === t.orden_id && <tr><td colSpan={columnas.length} className="px-3 pb-3 text-xs space-y-1">
                <div>Orden {t.orden_id} · servidor de túneles {t.parametros.host} · {t.parametros.clave_huella ? `huella de la clave: ${t.parametros.clave_huella}` : "sin clave en la orden"}
                  {t.parametros.clave_eliminada_en ? ` · clave retirada del servidor el ${fechaHora(t.parametros.clave_eliminada_en)}` : t.parametros.clave_en_orden ? " · la clave se retirará del servidor en cuanto el equipo conteste o la orden caduque" : ""}</div>
                {t.registro && <pre className="bg-ms-gray-10 rounded p-2 whitespace-pre-wrap max-h-64 overflow-auto">{t.registro}</pre>}
              </td></tr>}
            </Fragment>)}
            {lista && !lista.length && <tr><td colSpan={columnas.length} className="px-4 py-6 text-center text-ms-gray-60">Todavía no se ha abierto ningún túnel de soporte.</td></tr>}
            {!lista && !error && <tr><td colSpan={columnas.length} className="px-4 py-6 text-center text-ms-gray-60">Cargando…</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
