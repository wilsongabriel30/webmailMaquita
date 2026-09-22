import { useEffect, useState } from "react";
import { api } from "../../../api/client";
import { fechaHora } from "../tipos";
import { Alerta, ConfigAlertas, NOMBRE_ALERTA, describirAlerta, rolActual } from "./tipos";

// Alertas automáticas (las abre y cierra el trabajo del servidor cada 15 min) y sus umbrales.
// El rol lector solo las ve; los umbrales los edita un administrador.

const CAMPOS: { k: keyof ConfigAlertas; t: string; tipo?: string; ayuda?: string }[] = [
  { k: "sin_reportar_horas", t: "Sin reportar (horas)", tipo: "number" }, { k: "bateria_pct", t: "Batería baja (%)", tipo: "number" },
  { k: "bateria_horas", t: "…sostenida (horas)", tipo: "number" }, { k: "almacenamiento_pct", t: "Almacenamiento libre (%)", tipo: "number" },
  { k: "version_atrasada_dias", t: "App atrasada (días)", tipo: "number" }, { k: "acuse_horas", t: "Urgente sin acuse (horas)", tipo: "number" },
  { k: "correo_ti", t: "Correo de Tecnología (avisos)", ayuda: "Varios separados por coma" }, { k: "resumen_diario_para", t: "Resumen diario a", ayuda: "Dirección; vacío = no se envía" },
  { k: "resumen_hora", t: "Hora del resumen (HH:MM)" },
];

export function Alertas({ onAbrir }: { onAbrir: (id: number) => void }) {
  const [lista, setLista] = useState<Alerta[]>([]);
  const [cfg, setCfg] = useState<ConfigAlertas | null>(null);
  const [estado, setEstado] = useState<{ resumen_enviado_dia?: string }>({});
  const [historial, setHistorial] = useState(false);
  const [editar, setEditar] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; t: string } | null>(null);
  const admin = rolActual() !== "viewer";

  const cargar = (h = historial) => api.get<{ alertas: Alerta[]; config: ConfigAlertas; estado: any }>(`/dispositivos/alertas?abiertas=${!h}`)
    .then((r) => { setLista(r.alertas); setCfg(r.config); setEstado(r.estado || {}); }).catch((e) => setMsg({ ok: false, t: e.message }));
  useEffect(() => { cargar(); }, [historial]);

  const guardar = async () => {
    try { const r = await api.put<{ config: ConfigAlertas }>("/dispositivos/alertas/config", cfg); setCfg(r.config); setEditar(false); setMsg({ ok: true, t: "Umbrales guardados" }); }
    catch (e: any) { setMsg({ ok: false, t: e.message }); }
  };

  return (
    <div className="space-y-4">
      {msg && <div className={`text-sm px-3 py-2 rounded ${msg.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>{msg.t}</div>}
      <div className="bg-white rounded-lg border border-ms-gray-30">
        <div className="p-3 border-b border-ms-gray-30 flex items-center gap-3 text-sm">
          <h3 className="font-semibold">{historial ? "Alertas de los últimos 30 días" : "Alertas abiertas"}</h3>
          <button onClick={() => setHistorial(!historial)} className="text-xs text-ms-blue hover:underline">{historial ? "Ver solo abiertas" : "Ver historial"}</button>
          <span className="ml-auto text-xs text-ms-gray-60">Cada alerta se avisa una sola vez por correo y se cierra sola cuando el equipo vuelve a la normalidad.{estado.resumen_enviado_dia ? ` Último resumen diario: ${estado.resumen_enviado_dia}.` : ""}</span>
        </div>
        <table className="w-full text-sm">
          <thead><tr className="bg-ms-gray-10">{["Equipo", "Alerta", "Detalle", "Desde", "Hasta", "Avisada"].map((h) => <th key={h} className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">{h}</th>)}</tr></thead>
          <tbody>
            {lista.map((a) => <tr key={a.id} onClick={() => onAbrir(a.equipo_id)} className={`border-t border-ms-gray-20 cursor-pointer hover:bg-ms-gray-10 ${a.hasta ? "text-ms-gray-60" : ""}`}>
              <td className="px-4 py-2"><div className="font-medium">{a.nombre || `${a.fabricante || ""} ${a.modelo || ""}`.trim() || `Equipo ${a.equipo_id}`}</div><div className="text-xs text-ms-gray-60">{a.custodio_nombre || a.custodio_email}{a.sede ? ` · ${a.sede}` : ""}</div></td>
              <td className={`px-4 py-2 ${a.hasta ? "" : "text-red-700 font-medium"}`}>{NOMBRE_ALERTA[a.tipo] || a.tipo}</td>
              <td className="px-4 py-2 text-xs">{describirAlerta(a)}</td>
              <td className="px-4 py-2 text-xs">{fechaHora(a.desde)}</td><td className="px-4 py-2 text-xs">{a.hasta ? fechaHora(a.hasta) : "abierta"}</td>
              <td className="px-4 py-2 text-xs">{a.avisada_en ? fechaHora(a.avisada_en) : <span className="text-amber-700">pendiente</span>}</td>
            </tr>)}
            {!lista.length && <tr><td colSpan={6} className="px-4 py-6 text-center text-ms-gray-60">{historial ? "Sin alertas en 30 días." : "Sin alertas abiertas. Todo en orden."}</td></tr>}
          </tbody>
        </table>
      </div>

      {cfg && <div className="bg-white rounded-lg border border-ms-gray-30 p-4">
        <div className="flex items-center gap-3 mb-2">
          <h3 className="text-sm font-semibold">Umbrales y destinatarios</h3>
          {!cfg.activo && <span className="text-xs px-2 py-0.5 rounded bg-red-50 text-red-700">alertas desactivadas</span>}
          {admin && !editar && <button onClick={() => setEditar(true)} className="text-xs text-ms-blue hover:underline">Editar</button>}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
          {CAMPOS.map((c) => <label key={c.k} className="text-xs text-ms-gray-90">{c.t}
            <input type={c.tipo || "text"} disabled={!editar} value={String(cfg[c.k] ?? "")} title={c.ayuda} placeholder={c.ayuda}
              onChange={(e) => setCfg({ ...cfg, [c.k]: c.tipo === "number" ? Number(e.target.value) : e.target.value })}
              className="mt-1 w-full px-2.5 py-1.5 text-sm border border-ms-gray-40 rounded disabled:bg-ms-gray-10" /></label>)}
          <label className="text-xs text-ms-gray-90 flex items-end gap-2 pb-2"><input type="checkbox" disabled={!editar} checked={cfg.activo} onChange={(e) => setCfg({ ...cfg, activo: e.target.checked })} />Alertas activas</label>
        </div>
        {editar && <div className="mt-3 flex gap-2">
          <button onClick={guardar} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark">Guardar</button>
          <button onClick={() => { setEditar(false); cargar(); }} className="px-3 py-1.5 text-sm border border-ms-gray-40 rounded">Cancelar</button>
        </div>}
        <p className="text-xs text-ms-gray-60 mt-2">También se alerta, sin umbral, por eventos de seguridad sin revisar (quitar la app como administradora, intento de desinstalar, cambio de SIM) y por Play Protect apagado.</p>
      </div>}
    </div>
  );
}
