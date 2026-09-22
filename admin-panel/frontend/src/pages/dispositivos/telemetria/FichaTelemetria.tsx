import { useEffect, useState } from "react";
import { api } from "../../../api/client";
import { EVENTOS_GRAVES, NOMBRE_EVENTO, fechaHora } from "../tipos";
import { Grafica, Punto } from "./Grafica";
import { Alerta, NOMBRE_ALERTA, describirAlerta, gb } from "./tipos";

// Ficha de telemetría por equipo: gráficas de batería y almacenamiento (24 h / 7 d desde los latidos,
// 30 d desde el resumen diario), línea de tiempo de eventos, mensajes con quién leyó y cuándo, comandos
// y versiones de la app por las que pasó. Solo lectura (también para el rol lector).

interface Detalle {
  equipo: { id: number; nombre: string; fabricante?: string; modelo?: string; custodio_nombre?: string; custodio_email?: string; modo: string; estado: string; version_app?: string; android?: string; enrolado_en: string };
  rango: string; publicada: { versionName?: string };
  serie: Record<string, any>[];
  eventos: { id: number; tipo: string; detalle: Record<string, unknown>; recibido_en: string; visto_por?: string; visto_en?: string }[];
  mensajes: { id: number; titulo: string; nivel: string; requiere_acuse: boolean; creado_por: string; creado_en: string; entregado_en?: string; leido_en?: string; custodio_nombre?: string; custodio_email?: string }[];
  comandos: { id: number; tipo: string; estado: string; creado_por: string; creado_en: string; entregado_en?: string; terminado_en?: string; resultado?: Record<string, unknown> | null; motivo?: string }[];
  versiones: { version: string; desde: string; hasta: string }[];
  alertas: Alerta[];
  redes: { red?: string | null; wifi?: string | null; sede?: string | null; desde: string; hasta: string; reportes: number }[];
}
const RANGOS = [["24h", "24 horas"], ["7d", "7 días"], ["30d", "30 días"]] as const;

export function FichaTelemetria({ id, onCerrar }: { id: number; onCerrar: () => void }) {
  const [rango, setRango] = useState<"24h" | "7d" | "30d">("24h");
  const [d, setD] = useState<Detalle | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.get<Detalle>(`/dispositivos/telemetria/equipos/${id}?rango=${rango}`).then(setD).catch((e) => setError(e.message)); }, [id, rango]);
  if (!d) return <div className="p-6 text-sm text-ms-gray-60">{error || "Cargando…"}</div>;

  const e = d.equipo;
  const diario = rango === "30d";
  const bateria: Punto[] = d.serie.map((p) => diario
    ? { t: new Date(p.dia).getTime(), v: p.bateria_prom, min: p.bateria_min, max: p.bateria_max }
    : { t: new Date(p.t).getTime(), v: p.bateria, marca: !!p.cargando });
  const total = Math.max(...d.serie.map((p) => Number(diario ? p.alm_total : p.almacenamiento_total) || 0), 1);
  const gbs = (b: number | null | undefined) => (b == null ? null : b / 1073741824);
  const alm: Punto[] = d.serie.map((p) => diario
    ? { t: new Date(p.dia).getTime(), v: gbs(p.alm_libre_prom), min: gbs(p.alm_libre_min), max: gbs(p.alm_libre_prom) }
    : { t: new Date(p.t).getTime(), v: gbs(p.almacenamiento_libre) });

  return (
    <div className="bg-white rounded-lg border border-ms-gray-30 p-5 space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-ms-gray-130">{e.nombre || `${e.fabricante || ""} ${e.modelo || ""}`}</h2>
          <p className="text-xs text-ms-gray-60">{e.fabricante} {e.modelo} · Android {e.android || "?"} · app {e.version_app || "?"}{d.publicada.versionName && e.version_app !== d.publicada.versionName ? ` (publicada ${d.publicada.versionName})` : ""} · {e.modo === "propietario" ? "control completo" : "modo limitado"} · {e.custodio_nombre || e.custodio_email || "sin custodio"} · enrolado {fechaHora(e.enrolado_en)}</p>
        </div>
        <button onClick={onCerrar} className="px-3 py-1.5 text-sm border border-ms-gray-40 rounded hover:bg-ms-gray-10">← Volver a la flota</button>
      </div>
      {error && <div className="text-sm px-3 py-2 rounded bg-red-50 text-red-700">{error}</div>}

      {d.alertas.some((a) => !a.hasta) && <div className="rounded border border-red-200 bg-red-50 p-3 text-sm">
        <div className="font-medium text-red-700 mb-1">Alertas abiertas</div>
        {d.alertas.filter((a) => !a.hasta).map((a) => <div key={a.id}>• <strong>{NOMBRE_ALERTA[a.tipo] || a.tipo}</strong>: {describirAlerta(a)} <span className="text-xs text-ms-gray-60">(desde {fechaHora(a.desde)}{a.avisada_en ? `, avisada ${fechaHora(a.avisada_en)}` : ", aviso pendiente"})</span></div>)}
      </div>}

      <div className="flex items-center gap-1">
        {RANGOS.map(([k, t]) => <button key={k} onClick={() => setRango(k)} className={`px-3 py-1 text-xs rounded border ${rango === k ? "bg-ms-blue text-white border-ms-blue" : "border-ms-gray-40 hover:bg-ms-gray-10"}`}>{t}</button>)}
        <span className="text-xs text-ms-gray-60 ml-2">{diario ? "Promedio diario con banda mínimo-máximo (resumen que se conserva 12 meses)." : `${d.serie.length} reportes en el rango; el punto verde indica que estaba cargando.`}</span>
      </div>
      <div className="grid md:grid-cols-2 gap-3">
        <Grafica titulo="Batería (%)" puntos={bateria} max={100} unidad="%" umbral={15} />
        <Grafica titulo={`Almacenamiento libre (GB de ${(total / 1073741824).toFixed(0)})`} puntos={alm} max={Math.max(1, Math.ceil(total / 1073741824))} unidad="" color="#107c10" umbral={total / 1073741824 * 0.1} />
      </div>

      <div className="grid md:grid-cols-2 gap-5">
        <div>
          <h3 className="text-sm font-semibold mb-2">Línea de tiempo de eventos</h3>
          <ul className="text-sm space-y-1 max-h-72 overflow-y-auto">
            {d.eventos.map((ev) => <li key={ev.id} className={`px-2 py-1 rounded ${EVENTOS_GRAVES.includes(ev.tipo) ? (ev.visto_en ? "bg-amber-50" : "bg-red-50") : ""}`}>
              <span className="text-xs text-ms-gray-60 mr-2">{fechaHora(ev.recibido_en)}</span>{NOMBRE_EVENTO[ev.tipo] || ev.tipo}
              {ev.visto_por && <span className="text-xs text-ms-gray-60"> · revisó {ev.visto_por} {fechaHora(ev.visto_en)}</span>}
            </li>)}
            {!d.eventos.length && <li className="text-ms-gray-60">Sin eventos.</li>}
          </ul>
        </div>
        <div>
          <h3 className="text-sm font-semibold mb-2">Mensajes: quién leyó y cuándo</h3>
          <ul className="text-sm space-y-1 max-h-72 overflow-y-auto">
            {d.mensajes.map((m) => <li key={m.id} className="flex justify-between gap-2 px-2 py-1">
              <span>{m.titulo} <span className="text-xs text-ms-gray-60">· {m.nivel} · {fechaHora(m.creado_en)} · {m.creado_por}</span></span>
              <span className={`text-xs shrink-0 ${m.leido_en ? "text-green-700" : m.nivel === "urgente" ? "text-red-600" : "text-ms-gray-60"}`}>
                {m.leido_en ? `leído por ${m.custodio_nombre || m.custodio_email || "el custodio"} ${fechaHora(m.leido_en)}` : m.entregado_en ? `entregado ${fechaHora(m.entregado_en)}, sin leer` : "pendiente de entrega"}</span>
            </li>)}
            {!d.mensajes.length && <li className="text-ms-gray-60">Sin mensajes.</li>}
          </ul>
        </div>
        <div className="md:col-span-2">
          <h3 className="text-sm font-semibold mb-2">Redes por las que pasó (30 días)</h3>
          <p className="text-xs text-ms-gray-60 mb-1">Dónde estuvo conectado: sede reconocida por la red y nombre del wifi. Si alguien viajó y el teléfono sigue reportando desde la oficina de Quito o de una provincia, aquí se ve.</p>
          <ul className="text-sm space-y-1 max-h-60 overflow-y-auto">
            {d.redes.map((r, i) => <li key={i} className="px-2 py-1 flex flex-wrap gap-x-3">
              <span className="text-xs text-ms-gray-60 w-64 shrink-0">{fechaHora(r.desde)} → {fechaHora(r.hasta)}</span>
              <span>{r.sede ? <strong className="text-blue-700">en {r.sede}</strong> : <span className="text-ms-gray-60">fuera de las sedes</span>}</span>
              <span className="text-xs text-ms-gray-60">{r.red || "?"}{r.wifi ? ` «${r.wifi}»` : ""} · {r.reportes} reportes</span>
            </li>)}
            {!d.redes.length && <li className="text-ms-gray-60">Sin reportes en 30 días.</li>}
          </ul>
        </div>
        <div>
          <h3 className="text-sm font-semibold mb-2">Comandos enviados</h3>
          <ul className="text-sm space-y-1 max-h-60 overflow-y-auto">
            {d.comandos.map((c) => <li key={c.id} className="px-2 py-1"><span className="text-xs text-ms-gray-60 mr-2">{fechaHora(c.creado_en)}</span>{c.tipo} · {c.creado_por}
              <span className={`text-xs ml-2 ${c.estado === "hecho" ? "text-green-700" : c.estado === "fallido" ? "text-red-600" : "text-ms-gray-60"}`}>{c.estado}{c.terminado_en ? ` ${fechaHora(c.terminado_en)}` : ""}</span>
              {c.resultado?.detalle ? <div className="text-xs text-ms-gray-60">{String(c.resultado.detalle)}</div> : null}</li>)}
            {!d.comandos.length && <li className="text-ms-gray-60">Sin comandos.</li>}
          </ul>
        </div>
        <div>
          <h3 className="text-sm font-semibold mb-2">Versiones de la app por las que pasó</h3>
          <ul className="text-sm space-y-1">
            {d.versiones.map((v) => <li key={v.version} className="px-2 py-1">{v.version} <span className="text-xs text-ms-gray-60">· de {new Date(v.desde).toLocaleDateString("es-EC")} a {new Date(v.hasta).toLocaleDateString("es-EC")}</span></li>)}
            {!d.versiones.length && <li className="text-ms-gray-60">Todavía sin reportes.</li>}
          </ul>
          <h3 className="text-sm font-semibold mb-2 mt-4">Alertas de los últimos 30 días</h3>
          <ul className="text-sm space-y-1 max-h-40 overflow-y-auto">
            {d.alertas.map((a) => <li key={a.id} className="px-2 py-1 text-xs"><span className="text-ms-gray-60">{fechaHora(a.desde)} → {a.hasta ? fechaHora(a.hasta) : "abierta"}</span> · {NOMBRE_ALERTA[a.tipo] || a.tipo}</li>)}
            {!d.alertas.length && <li className="text-ms-gray-60">Sin alertas.</li>}
          </ul>
        </div>
      </div>
      <p className="text-xs text-ms-gray-60">Almacenamiento actual: {gb(d.serie.length ? Number(diario ? d.serie[d.serie.length - 1].alm_libre_prom : d.serie[d.serie.length - 1].almacenamiento_libre) : undefined)} libres.</p>
    </div>
  );
}
