import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { consulta, type Cumplimiento as Datos, type Rango } from "./api";
import { COLOR, Estado, Kpi, Seccion, etiqueta, fecha, useDatos } from "./comunes";

const th = "text-left px-2 py-1.5 font-medium text-ms-gray-90";
const td = "px-2 py-1.5 border-t border-ms-gray-20";
const NOMBRES: Record<string, string> = {
  ediscovery_search: "Búsqueda eDiscovery", ediscovery_export: "Exportación eDiscovery", custodian_add: "Custodio añadido",
  custodian_remove: "Custodio retirado", mail_read: "Lectura de buzón ajeno", mail_export: "Exportación de correo",
};
const nombre = (a: string) => NOMBRES[a] || a;

/* Tablero «Cumplimiento»: actividad de eDiscovery, retenciones legales, políticas y auditoría. */
export function Cumplimiento({ rango }: { rango: Rango }) {
  const { datos, error, cargando } = useDatos<Datos>(`/seguridad/cumplimiento?${consulta(rango)}`);
  const porDia = new Map<string, Record<string, number | string>>();
  for (const f of datos?.acciones || []) {
    const fila = porDia.get(f.t) || { x: etiqueta(f.t, "day") };
    fila[f.action] = Number(f.n);
    porDia.set(f.t, fila);
  }
  for (const f of datos?.busquedas || []) {
    const fila = porDia.get(f.t) || { x: etiqueta(f.t, "day") };
    fila.busquedas = Number(f.n);
    porDia.set(f.t, fila);
  }
  const serie = [...porDia.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([, f]) => f);
  const acciones = [...new Set((datos?.acciones || []).map((f) => f.action as string))];
  const paleta = [COLOR.azul, COLOR.naranja, COLOR.morado, COLOR.ok, COLOR.amarillo, COLOR.fallo, COLOR.gris];

  return (
    <div className="space-y-4">
      <Estado cargando={cargando} error={error} />
      {datos && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <Kpi titulo="Búsquedas eDiscovery" valor={(datos.busquedas || []).reduce((s, f) => s + Number(f.n), 0)} />
            <Kpi titulo="Exportaciones" valor={datos.exportaciones?.length ?? null} tono="text-ms-orange" ayuda="Exportaciones de evidencia (cada una con motivo y firma)." />
            <Kpi titulo="Retenciones activas" valor={datos.retenciones?.activas ?? null} ayuda="Buzones con retención legal vigente (no se puede borrar su correo)." />
            <Kpi titulo="Retenciones puestas" valor={datos.retenciones?.puestas ?? null} />
            <Kpi titulo="Retenciones liberadas" valor={datos.retenciones?.liberadas ?? null} />
          </div>
          {serie.length > 0 && (
            <Seccion titulo="Actividad por día (auditoría del panel y búsquedas)">
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={serie}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#edebe9" />
                  <XAxis dataKey="x" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                  <Tooltip /><Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="busquedas" name="Búsquedas eDiscovery (casos)" fill={COLOR.gris} />
                  {acciones.map((a, i) => <Bar key={a} dataKey={a} name={nombre(a)} stackId="a" fill={paleta[i % paleta.length]} />)}
                </BarChart>
              </ResponsiveContainer>
            </Seccion>
          )}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <Seccion titulo="Exportaciones de eDiscovery">
              {datos.exportaciones === null ? <p className="text-xs text-ms-gray-60">Esta instalación no tiene el módulo de casos de eDiscovery.</p> : (
                <table className="w-full text-xs">
                  <thead><tr><th className={th}>Fecha</th><th className={th}>Caso</th><th className={th}>Por</th><th className={th}>Mensajes</th><th className={th}>Motivo</th></tr></thead>
                  <tbody>{datos.exportaciones.map((f) => (
                    <tr key={f.id}><td className={td}>{fecha(f.exported_at)}</td><td className={td}>{f.case_id}</td><td className={td}>{f.exported_by}</td>
                      <td className={td}>{f.total_messages}</td><td className={td}>{f.reason}</td></tr>))}
                    {datos.exportaciones.length === 0 && <tr><td className={td} colSpan={5}>Ninguna en el periodo.</td></tr>}
                  </tbody>
                </table>)}
            </Seccion>
            <Seccion titulo="Políticas de retención">
              {datos.politicas === null || datos.politicas.length === 0 ? <p className="text-xs text-ms-gray-60">No hay políticas de retención.</p> : (
                <table className="w-full text-xs">
                  <thead><tr><th className={th}>Política</th><th className={th}>Activa</th><th className={th}>Días</th><th className={th}>Acción</th><th className={th}>Última ejecución</th><th className={th}>Mensajes</th></tr></thead>
                  <tbody>{datos.politicas.map((p) => (
                    <tr key={p.name}><td className={td}>{p.name}</td><td className={td}>{p.is_active ? "Sí" : "No"}</td><td className={td}>{p.max_age_days}</td>
                      <td className={td}>{p.action}</td><td className={td}>{fecha(p.last_run)}</td><td className={td}>{p.messages_affected}</td></tr>))}
                  </tbody>
                </table>)}
            </Seccion>
          </div>
          <Seccion titulo="Últimas acciones de cumplimiento (auditoría del panel)">
            <table className="w-full text-xs">
              <thead><tr><th className={th}>Fecha</th><th className={th}>Administrador</th><th className={th}>Acción</th><th className={th}>Objetivo</th><th className={th}>IP</th></tr></thead>
              <tbody>{(datos.recientes || []).map((f, i) => (
                <tr key={i}><td className={td}>{fecha(f.created_at)}</td><td className={td}>{f.admin_username}</td><td className={td}>{nombre(f.action)}</td>
                  <td className={`${td} break-all`}>{f.target}</td><td className={`${td} font-mono`}>{f.ip_address}</td></tr>))}
                {(datos.recientes || []).length === 0 && <tr><td className={td} colSpan={5}>Ninguna en el periodo.</td></tr>}
              </tbody>
            </table>
            {(datos.webmail || []).length > 0 && (
              <p className="text-xs text-ms-gray-90 mt-3">Desde el webmail: {(datos.webmail || []).map((f) => `${nombre(f.action)} (${f.n})`).join(" · ")}</p>
            )}
          </Seccion>
        </>
      )}
    </div>
  );
}
