import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { consulta, type Accesos, type Rango } from "./api";
import { COLOR, COLOR_SERVICIO, Estado, Kpi, SERVICIOS, Seccion, etiqueta, fecha, nombrePais, useDatos } from "./comunes";

const th = "text-left px-2 py-1.5 font-medium text-ms-gray-90";
const td = "px-2 py-1.5 border-t border-ms-gray-20";

/* Tablero «Inicios de sesión»: correctos y fallidos por servicio y país, IP y cuentas más atacadas. */
export function InicioSesion({ rango }: { rango: Rango }) {
  const [servicio, setServicio] = useState("");
  const extra: Record<string, string> = servicio ? { servicio } : {};
  const { datos, error, cargando } = useDatos<Accesos>(`/seguridad/accesos?${consulta(rango, extra)}`);

  // Serie: una fila por periodo con «<servicio>_ok» y «<servicio>_fallos».
  const filas = new Map<string, Record<string, number | string>>();
  for (const p of datos?.serie || []) {
    const f = filas.get(p.t) || { x: etiqueta(p.t, datos!.paso) };
    f[`${p.servicio}_ok`] = p.ok; f[`${p.servicio}_fallos`] = p.fallos;
    filas.set(p.t, f);
  }
  const serie = [...filas.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([, f]) => f);
  const presentes = [...new Set((datos?.serie || []).map((p) => p.servicio))];
  const ok = (datos?.por_servicio || []).reduce((s, x) => s + x.ok, 0);
  const fallos = (datos?.por_servicio || []).reduce((s, x) => s + x.fallos, 0);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 flex-1">
          <Kpi titulo="Accesos correctos" valor={ok} tono="text-ms-green" ayuda="ActiveSync cuenta un acceso por hora, cuenta e IP (el teléfono repite la conexión cada pocos minutos)." />
          <Kpi titulo="Intentos fallidos" valor={fallos} tono="text-ms-red" />
          <Kpi titulo="IP con fallos" valor={datos?.top_ips.length ?? null} ayuda="Hasta 25: las que más fallaron." />
          <Kpi titulo="Cuentas con fallos" valor={datos?.top_cuentas.length ?? null} ayuda="Hasta 25: las más atacadas." />
        </div>
        <select value={servicio} onChange={(e) => setServicio(e.target.value)} className="px-2 py-1.5 border border-ms-gray-30 rounded text-sm" title="Filtrar las gráficas por servicio">
          <option value="">Todos los servicios</option>
          {Object.entries(SERVICIOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>
      <Estado cargando={cargando} error={error} vacio={!cargando && !error && serie.length === 0} />
      {serie.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Seccion titulo="Correctos por servicio">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={serie}>
                <CartesianGrid strokeDasharray="3 3" stroke="#edebe9" />
                <XAxis dataKey="x" tick={{ fontSize: 11 }} minTickGap={12} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip /><Legend wrapperStyle={{ fontSize: 12 }} />
                {presentes.map((s) => <Bar key={s} dataKey={`${s}_ok`} name={SERVICIOS[s] || s} stackId="ok" fill={COLOR_SERVICIO[s] || COLOR.gris} />)}
              </BarChart>
            </ResponsiveContainer>
          </Seccion>
          <Seccion titulo="Fallidos por servicio">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={serie}>
                <CartesianGrid strokeDasharray="3 3" stroke="#edebe9" />
                <XAxis dataKey="x" tick={{ fontSize: 11 }} minTickGap={12} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip /><Legend wrapperStyle={{ fontSize: 12 }} />
                {presentes.map((s) => <Bar key={s} dataKey={`${s}_fallos`} name={SERVICIOS[s] || s} stackId="f" fill={COLOR_SERVICIO[s] || COLOR.gris} />)}
              </BarChart>
            </ResponsiveContainer>
          </Seccion>
        </div>
      )}
      {datos && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <Seccion titulo="Por país">
            <table className="w-full text-xs">
              <thead><tr><th className={th}>País</th><th className={th}>Correctos</th><th className={th}>Fallidos</th></tr></thead>
              <tbody>{datos.por_pais.map((p) => (
                <tr key={p.pais}><td className={td}>{nombrePais(p.pais)}</td><td className={td}>{p.ok.toLocaleString("es")}</td>
                  <td className={`${td} ${p.fallos ? "text-ms-red" : ""}`}>{p.fallos.toLocaleString("es")}</td></tr>))}
              </tbody>
            </table>
          </Seccion>
          <Seccion titulo="IP con más fallos">
            <table className="w-full text-xs">
              <thead><tr><th className={th}>IP</th><th className={th}>País</th><th className={th}>Fallos</th><th className={th} title="Cuentas distintas probadas">Cuentas</th><th className={th}>Último</th></tr></thead>
              <tbody>{datos.top_ips.map((p) => (
                <tr key={p.ip} title={`Servicios: ${p.servicios.map((s) => SERVICIOS[s] || s).join(", ")} · correctos: ${p.ok}`}>
                  <td className={`${td} font-mono`}>{p.ip}</td><td className={td}>{nombrePais(p.pais)}</td>
                  <td className={`${td} text-ms-red`}>{p.fallos}</td><td className={td}>{p.cuentas}</td><td className={td}>{fecha(p.ultima)}</td></tr>))}
              </tbody>
            </table>
          </Seccion>
          <Seccion titulo="Cuentas más atacadas">
            <table className="w-full text-xs">
              <thead><tr><th className={th}>Cuenta</th><th className={th}>Fallos</th><th className={th}>IP</th><th className={th}>Países</th><th className={th}>Correctos</th></tr></thead>
              <tbody>{datos.top_cuentas.map((c) => (
                <tr key={c.cuenta}><td className={`${td} break-all`}>{c.cuenta}</td><td className={`${td} text-ms-red`}>{c.fallos}</td>
                  <td className={td}>{c.ips}</td><td className={td}>{c.paises}</td><td className={td}>{c.ok}</td></tr>))}
              </tbody>
            </table>
          </Seccion>
        </div>
      )}
    </div>
  );
}
