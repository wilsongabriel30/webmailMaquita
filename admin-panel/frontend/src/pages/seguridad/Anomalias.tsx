import { useState } from "react";
import { api } from "../../api/client";
import type { Alerta } from "./api";
import { Estado, Seccion, SERVICIOS, fecha, nombrePais, useDatos } from "./comunes";

const REGLAS: Record<string, string> = {
  pais_nuevo: "País nuevo", fallos_y_exito: "Fallos y luego acceso", hora_inusual: "Hora inusual", muchas_cuentas_ip: "Muchas cuentas desde una IP",
};
const SEVERIDAD: Record<string, string> = { alta: "bg-red-100 text-red-700", media: "bg-amber-100 text-amber-700", baja: "bg-ms-gray-20 text-ms-gray-130" };
const ESTADO: Record<string, string> = { abierta: "text-ms-red", reconocida: "text-amber-700", cerrada: "text-ms-green" };

/* Anomalías: alertas de las reglas con su explicación y el flujo abierta → reconocida → cerrada. */
export function Anomalias({ puedeActuar }: { puedeActuar: boolean }) {
  const [estado, setEstado] = useState("pendientes");
  const [severidad, setSeveridad] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; texto: string } | null>(null);
  const params = new URLSearchParams();
  if (estado !== "todas") params.set("estado", estado);
  if (severidad) params.set("severidad", severidad);
  const { datos, error, cargando, recargar } = useDatos<{ alertas: Alerta[]; abiertas: Record<string, number> }>(`/seguridad/alertas?${params}`);
  const lista = datos?.alertas || [];

  const actuar = async (a: Alerta, accion: "reconocer" | "cerrar", resolucion?: string) => {
    let nota = "";
    if (accion === "cerrar") {
      const p = window.prompt(resolucion === "falso_positivo" ? "¿Por qué es un falso positivo? (obligatorio)" : "Nota de cierre (qué se hizo):", "");
      if (p === null) return;
      nota = p;
    }
    try {
      await api.post(`/seguridad/alertas/${a.id}/${accion}`, accion === "cerrar" ? { resolucion, nota } : { nota });
      setMsg({ ok: true, texto: accion === "reconocer" ? `Alerta #${a.id} reconocida: ya no se escalará.` : `Alerta #${a.id} cerrada.` });
      recargar();
    } catch (e) { setMsg({ ok: false, texto: (e as Error).message }); }
  };

  const ab = datos?.abiertas || {};
  const cuenta = (e: string) => Object.entries(ab).filter(([k]) => k.startsWith(e)).reduce((s, [, n]) => s + n, 0);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 items-center text-sm">
        <span className="px-2 py-1 rounded bg-red-50 text-ms-red">Abiertas: <b>{cuenta("abierta")}</b> ({ab["abierta:alta"] || 0} altas)</span>
        <span className="px-2 py-1 rounded bg-amber-50 text-amber-700">Reconocidas: <b>{cuenta("reconocida")}</b></span>
        <select value={estado} onChange={(e) => setEstado(e.target.value)} className="ml-auto px-2 py-1.5 border border-ms-gray-30 rounded text-sm">
          <option value="pendientes">Pendientes (abiertas y reconocidas)</option>
          <option value="abierta">Abiertas</option><option value="reconocida">Reconocidas</option>
          <option value="cerrada">Cerradas</option><option value="todas">Todas</option>
        </select>
        <select value={severidad} onChange={(e) => setSeveridad(e.target.value)} className="px-2 py-1.5 border border-ms-gray-30 rounded text-sm">
          <option value="">Toda severidad</option><option value="alta">Alta</option><option value="media">Media</option><option value="baja">Baja</option>
        </select>
      </div>
      {msg && <p className={`text-sm ${msg.ok ? "text-ms-green" : "text-ms-red"}`}>{msg.texto}</p>}
      <Estado cargando={cargando} error={error} />
      <Seccion titulo="Alertas">
        {lista.length === 0 ? <p className="text-sm text-ms-gray-60">No hay alertas con este filtro.</p> : (
          <div className="divide-y divide-ms-gray-20">
            {lista.map((a) => (
              <div key={a.id} className="py-3 flex flex-col md:flex-row md:items-start gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <span className={`px-1.5 py-0.5 rounded font-semibold uppercase ${SEVERIDAD[a.severidad]}`}>{a.severidad}</span>
                    <span className="font-medium">{REGLAS[a.regla] || a.regla}</span>
                    <span className={ESTADO[a.estado]}>{a.estado}{a.resolucion ? ` (${a.resolucion === "falso_positivo" ? "falso positivo" : "resuelta"})` : ""}</span>
                    <span className="text-ms-gray-60">#{a.id} · {fecha(a.creada)}{a.repeticiones > 1 ? ` · ${a.repeticiones} veces, última ${fecha(a.ultima_vez)}` : ""}</span>
                    {a.escalada_en && <span className="text-ms-red">escalada {fecha(a.escalada_en)}</span>}
                  </div>
                  <p className="text-sm text-ms-gray-130 mt-1">{a.descripcion}</p>
                  <p className="text-xs text-ms-gray-90 mt-0.5">
                    {a.cuenta && <>Cuenta: <b>{a.cuenta}</b> · </>}{a.ip && <>IP: <span className="font-mono">{a.ip}</span> · </>}
                    {a.pais && <>País: {nombrePais(a.pais)} · </>}{a.servicio && <>Servicio: {SERVICIOS[a.servicio] || a.servicio}</>}
                  </p>
                  {(a.reconocida_por || a.nota) && (
                    <p className="text-xs text-ms-gray-90 mt-0.5">
                      {a.reconocida_por && <>Reconocida por {a.reconocida_por} ({fecha(a.reconocida_en)}). </>}
                      {a.cerrada_por && <>Cerrada por {a.cerrada_por} ({fecha(a.cerrada_en)}). </>}
                      {a.nota && <>Nota: {a.nota}</>}
                    </p>
                  )}
                </div>
                {puedeActuar && a.estado !== "cerrada" && (
                  <div className="flex gap-2 shrink-0">
                    {a.estado === "abierta" && <button onClick={() => actuar(a, "reconocer")} className="px-2.5 py-1 text-xs rounded border border-ms-blue text-ms-blue hover:bg-ms-blue-lighter" title="Indica que alguien la está revisando: deja de escalar.">Reconocer</button>}
                    <button onClick={() => actuar(a, "cerrar", "resuelta")} className="px-2.5 py-1 text-xs rounded bg-ms-blue text-white" title="Cerrar: se investigó y se resolvió (p. ej. se cambió la clave).">Cerrar</button>
                    <button onClick={() => actuar(a, "cerrar", "falso_positivo")} className="px-2.5 py-1 text-xs rounded border border-ms-gray-40 text-ms-gray-130 hover:bg-ms-gray-20" title="Cerrar como falso positivo (la persona viajaba, etc.). Pide el motivo.">Falso positivo</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Seccion>
    </div>
  );
}
