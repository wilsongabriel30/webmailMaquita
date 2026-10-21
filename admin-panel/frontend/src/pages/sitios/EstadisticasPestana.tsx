import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { abrirEnlace, tamano } from "./datosComun";

interface Dia { fecha: string; visitas: number; paginas: number; solicitudes: number; bytes: number }
interface Datos {
  goaccess: boolean;
  informe: boolean;
  resumen: { dias: Dia[]; totales: Omit<Dia, "fecha">; generado: string } | null;
}

/* Visitas y ancho de banda de los últimos 30 días (se calculan cada noche) e informe completo de GoAccess. */
export function EstadisticasPestana({ dominio }: { dominio: string }) {
  const [datos, setDatos] = useState<Datos | null>(null);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => { api.get<Datos>(`/sitios/${dominio}/estadisticas`).then(setDatos).catch((e) => setError(e.message)); }, [dominio]);

  const generar = async () => {
    setOcupado(true); setError("");
    try { setDatos(await api.post<Datos>(`/sitios/${dominio}/estadisticas/generar`)); }
    catch (e) { setError((e as Error).message); } finally { setOcupado(false); }
  };
  const informe = async () => {
    setError("");
    try { abrirEnlace((await api.post<{ enlace: string }>(`/sitios/${dominio}/estadisticas/informe`)).enlace, true); }
    catch (e) { setError((e as Error).message); }
  };

  const dias = datos?.resumen?.dias || [];
  const maximo = Math.max(1, ...dias.map((d) => d.visitas));
  return (
    <div className="space-y-3">
      {error && <p className="text-sm text-ms-red">{error}</p>}
      {datos && !datos.resumen && <p className="text-sm text-ms-gray-60">Todavía no hay estadísticas: se calculan cada noche a partir de los registros de acceso.</p>}
      {datos?.resumen && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {([["Visitas", datos.resumen.totales.visitas.toLocaleString("es")], ["Páginas vistas", datos.resumen.totales.paginas.toLocaleString("es")],
              ["Solicitudes", datos.resumen.totales.solicitudes.toLocaleString("es")], ["Transferido", tamano(datos.resumen.totales.bytes)]] as const).map(([t, v]) => (
              <div key={t} className="border border-ms-gray-30 rounded p-2"><div className="text-[11px] text-ms-gray-60">{t} (30 días)</div><div className="text-lg font-semibold">{v}</div></div>
            ))}
          </div>
          <div className="flex items-end gap-0.5 h-28 border-b border-ms-gray-30" aria-label="Visitas por día">
            {dias.map((d) => (
              <div key={d.fecha} title={`${d.fecha}: ${d.visitas} visitas, ${d.paginas} páginas, ${tamano(d.bytes)}`}
                className="flex-1 bg-ms-blue/70 hover:bg-ms-blue rounded-t" style={{ height: `${Math.max(2, (d.visitas / maximo) * 100)}%` }} />
            ))}
          </div>
          <div className="flex justify-between text-[11px] text-ms-gray-60"><span>{dias[0]?.fecha}</span><span>Calculado: {datos.resumen.generado}</span><span>{dias[dias.length - 1]?.fecha}</span></div>
        </>
      )}
      <div className="flex flex-wrap gap-2 items-center">
        <button onClick={informe} disabled={!datos?.informe} className="px-4 py-1.5 bg-ms-blue text-white rounded text-sm disabled:opacity-50">Ver informe completo</button>
        <button onClick={generar} disabled={ocupado} className="px-3 py-1.5 border border-ms-gray-40 rounded text-sm disabled:opacity-50">{ocupado ? "Generando…" : "Generar ahora"}</button>
        {datos && !datos.goaccess && <span className="text-xs text-ms-gray-60">GoAccess no está instalado: hay resumen, pero no informe completo (se instala con «instalar-app.sh sitios»).</span>}
      </div>
      <p className="text-[11px] text-ms-gray-60">Visitas = personas distintas por día (dirección y navegador), sin contar robots conocidos. El informe completo (GoAccess) no es público: solo se abre desde aquí.</p>
    </div>
  );
}
