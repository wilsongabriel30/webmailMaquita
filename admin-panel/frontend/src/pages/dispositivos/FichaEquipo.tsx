import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { ModoPerdido } from "./ModoPerdido";
import { Ubicacion } from "./Ubicacion";
import { Respaldos } from "./Respaldos";
import { Apps } from "./Apps";
import { Reasignar } from "./Reasignar";
import { Equipo, Evento, EVENTOS_GRAVES, Latido, MensajeEquipo, NOMBRE_EVENTO, dinero, fechaHora, gigas } from "./tipos";

interface Detalle { equipo: Equipo; latidos: Latido[]; eventos: Evento[]; mensajes: MensajeEquipo[] }
const CAMPOS: { k: keyof Equipo; label: string; tipo?: string; ayuda?: string }[] = [
  { k: "nombre", label: "Nombre del equipo", ayuda: "Ej: Celular Ventas 03" },
  { k: "custodio_nombre", label: "Custodio (nombre)" },
  { k: "custodio_email", label: "Custodio (correo)", tipo: "email" },
  { k: "centro_costo", label: "Centro de costo" },
  { k: "sede", label: "Sede / oficina" },
  { k: "imei", label: "IMEI principal", ayuda: "15 dígitos: *#06# o la caja. En equipos administrados lo reporta el teléfono." },
  { k: "imeis", label: "Todos los IMEI (separados por coma)", ayuda: "Doble SIM y eSIM tienen 2 a 4. Son los que se dan a la operadora para bloquear el teléfono si lo roban. La persona también puede registrarlos desde su correo." },
  { k: "serie", label: "Número de serie" },
  { k: "fecha_compra", label: "Fecha de compra", tipo: "date" },
  { k: "valor_compra", label: "Valor de compra (USD)", tipo: "number" },
  { k: "vida_util_meses", label: "Vida útil (meses)", tipo: "number", ayuda: "36 meses por defecto (equipos de cómputo)" },
  { k: "factura_ref", label: "Factura", ayuda: "Número de factura o ruta del archivo en el Drive" },
];

export function FichaEquipo({ id, onCerrar, onCambio }: { id: number; onCerrar: () => void; onCambio: () => void }) {
  const [d, setD] = useState<Detalle | null>(null);
  const [f, setF] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<{ ok: boolean; t: string } | null>(null);

  const cargar = async () => {
    const r = await api.get<Detalle>(`/dispositivos/equipos/${id}`);
    setD(r);
    const e = r.equipo as unknown as Record<string, unknown>;
    setF(Object.fromEntries([...CAMPOS.map((c) => c.k as string), "notas", "estado"].map((k) => [k, e[k] == null ? "" : String(e[k])])));
  };
  useEffect(() => { cargar().catch((e) => setMsg({ ok: false, t: e.message })); }, [id]);

  const guardar = async () => {
    try { await api.put(`/dispositivos/equipos/${id}`, f); setMsg({ ok: true, t: "Guardado" }); await cargar(); onCambio(); }
    catch (e: any) { setMsg({ ok: false, t: e.message }); }
  };
  const revocar = async () => {
    const motivo = prompt("Motivo de la baja de gestión (queda en la auditoría). El teléfono dejará de reportar y tendrá que enrolarse de nuevo:");
    if (!motivo) return;
    try { await api.post(`/dispositivos/equipos/${id}/revocar`, { motivo }); await cargar(); onCambio(); }
    catch (e: any) { setMsg({ ok: false, t: e.message }); }
  };
  const eliminar = async () => {
    const palabra = prompt(`Esto borra el equipo y TODO su historial (reportes, ubicaciones, respaldos, mensajes, comandos, alertas). El teléfono dejará de reportar y podrá enrolarse de nuevo con otro código. Es para pruebas fallidas o equipos que no existen.\n\nPara confirmar escribe: ELIMINAR ${id}`);
    if (!palabra) return;
    try { await api.del(`/dispositivos/equipos/${id}/definitivo`, { confirmacion: palabra }); onCambio(); onCerrar(); }
    catch (e: any) { setMsg({ ok: false, t: e.message }); }
  };
  const visto = async (ev: number) => { await api.post(`/dispositivos/eventos/${ev}/visto`); await cargar(); onCambio(); };

  if (!d) return <div className="p-6 text-sm text-ms-gray-60">Cargando…</div>;
  const e = d.equipo; const dep = e.depreciacion;

  return (
    <div className="bg-white rounded-lg border border-ms-gray-30 p-5 space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-ms-gray-130">{e.nombre || `${e.fabricante || ""} ${e.modelo || ""}`}</h2>
          <p className="text-xs text-ms-gray-60">{e.fabricante} {e.modelo} · Android {e.android || "?"} · app {e.version_app || "?"} · {e.modo === "propietario" ? "Administrado (control completo)" : "Modo limitado"} · enrolado {fechaHora(e.enrolado_en)}</p>
        </div>
        <button onClick={onCerrar} className="px-3 py-1.5 text-sm border border-ms-gray-40 rounded hover:bg-ms-gray-10">← Volver</button>
      </div>
      {msg && <div className={`text-sm px-3 py-2 rounded ${msg.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>{msg.t}</div>}

      {(e.imeis?.length || e.imei) && <div className="rounded border border-ms-gray-30 bg-ms-gray-10 p-3 text-sm flex flex-wrap items-center gap-3">
        <span className="font-semibold">IMEI para la operadora:</span>
        {(e.imeis?.length ? e.imeis : [e.imei as string]).map((i) => <code key={i} className="font-mono bg-white px-2 py-0.5 rounded border border-ms-gray-30">{i}</code>)}
        <button onClick={() => navigator.clipboard.writeText((e.imeis?.length ? e.imeis : [e.imei as string]).join(", "))} className="text-xs text-ms-blue hover:underline">Copiar</button>
        <span className="text-xs text-ms-gray-60">Si roban o pierden el teléfono, la operadora bloquea el equipo con estos números.</span>
      </div>}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
        {[["Último contacto", fechaHora(e.ultimo_contacto)], ["Batería", e.bateria != null ? `${e.bateria}%${e.cargando ? " ⚡" : ""}` : "—"],
          ["Almacenamiento libre", `${gigas(e.almacenamiento_libre)} de ${gigas(e.almacenamiento_total)}`], ["Red", e.red || "—"],
          ["Play Protect", e.play_protect == null ? "—" : e.play_protect ? "Activo" : "DESACTIVADO"]].map(([a, b]) => (
          <div key={a} className="bg-ms-gray-10 rounded p-2.5"><div className="text-[11px] text-ms-gray-60">{a}</div><div className="font-medium">{b}</div></div>))}
      </div>

      {e.estado !== "revocado" && e.estado !== "baja" && <ModoPerdido equipo={e} onCambio={() => { cargar(); onCambio(); }} />}
      {e.estado !== "revocado" && <Ubicacion equipo={e} onCambio={() => { cargar(); onCambio(); }} />}
      <Respaldos equipo={e} />
      {e.estado !== "revocado" && <Apps equipo={e} />}
      {e.estado !== "revocado" && <Reasignar equipo={e} onCambio={() => { cargar(); onCambio(); }} />}

      <div>
        <h3 className="text-sm font-semibold mb-2">Inventario y asignación</h3>
        <div className="grid md:grid-cols-2 gap-3">
          {CAMPOS.map((c) => (
            <label key={c.k as string} className="text-xs text-ms-gray-90">{c.label}
              <input type={c.tipo || "text"} value={f[c.k as string] ?? ""} title={c.ayuda}
                onChange={(ev) => setF({ ...f, [c.k as string]: ev.target.value })}
                className="mt-1 w-full px-2.5 py-1.5 text-sm border border-ms-gray-40 rounded" />
            </label>))}
          <label className="text-xs text-ms-gray-90">Estado
            <select value={f.estado} disabled={e.estado === "revocado" || e.estado === "perdido"} onChange={(ev) => setF({ ...f, estado: ev.target.value })}
              className="mt-1 w-full px-2.5 py-1.5 text-sm border border-ms-gray-40 rounded">
              <option value="activo">Activo</option><option value="baja">Dado de baja del inventario</option>
              {e.estado === "perdido" && <option value="perdido">Perdido o robado (se cambia desde «Pérdida o robo»)</option>}
              {e.estado === "revocado" && <option value="revocado">Revocado</option>}
            </select></label>
          <label className="text-xs text-ms-gray-90 md:col-span-2">Notas
            <textarea value={f.notas ?? ""} onChange={(ev) => setF({ ...f, notas: ev.target.value })} rows={2}
              className="mt-1 w-full px-2.5 py-1.5 text-sm border border-ms-gray-40 rounded" /></label>
        </div>
        <div className="mt-3 flex gap-2">
          <button onClick={guardar} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark">Guardar</button>
          {e.estado !== "revocado" && <button onClick={revocar} className="px-3 py-1.5 text-sm text-ms-red border border-ms-red/30 rounded hover:bg-red-50">Quitar de la gestión</button>}
          <button onClick={eliminar} className="ml-auto px-3 py-1.5 text-sm text-ms-gray-60 border border-ms-gray-30 rounded hover:text-ms-red hover:border-ms-red/30" title="Borra el equipo y todo su historial (pruebas fallidas)">Eliminar definitivamente</button>
        </div>
      </div>

      {dep && <div className="bg-ms-gray-10 rounded p-3 text-sm">
        <span className="font-semibold">Depreciación (línea recta):</span> compra {dinero(e.valor_compra)} · {dep.meses_transcurridos} de {dep.vida_util_meses} meses ·
        acumulada {dinero(dep.depreciacion_acumulada)} · <span className="font-semibold">valor en libros {dinero(dep.valor_en_libros)}</span>
        {dep.totalmente_depreciado && " · totalmente depreciado"}
      </div>}

      <div className="grid md:grid-cols-2 gap-5">
        <div>
          <h3 className="text-sm font-semibold mb-2">Eventos</h3>
          <ul className="text-sm space-y-1.5 max-h-64 overflow-y-auto">
            {d.eventos.map((ev) => {
              const grave = EVENTOS_GRAVES.includes(ev.tipo);
              return <li key={ev.id} className={`flex justify-between gap-2 px-2 py-1 rounded ${grave && !ev.visto_en ? "bg-red-50" : ""}`}>
                <span>{NOMBRE_EVENTO[ev.tipo] || ev.tipo}<span className="text-xs text-ms-gray-60"> · {fechaHora(ev.recibido_en)}</span></span>
                {grave && !ev.visto_en ? <button onClick={() => visto(ev.id)} className="text-xs text-ms-blue hover:underline shrink-0">Marcar revisado</button>
                  : ev.visto_por ? <span className="text-xs text-ms-gray-60 shrink-0">revisó {ev.visto_por}</span> : null}
              </li>;
            })}
            {!d.eventos.length && <li className="text-ms-gray-60">Sin eventos.</li>}
          </ul>
        </div>
        <div>
          <h3 className="text-sm font-semibold mb-2">Mensajes enviados a este equipo</h3>
          <ul className="text-sm space-y-1.5 max-h-64 overflow-y-auto">
            {d.mensajes.map((m) => <li key={m.id} className="flex justify-between gap-2">
              <span>{m.titulo}<span className="text-xs text-ms-gray-60"> · {fechaHora(m.creado_en)}</span></span>
              <span className={`text-xs shrink-0 ${m.leido_en ? "text-green-700" : "text-ms-gray-60"}`}>{m.leido_en ? `leído ${fechaHora(m.leido_en)}` : m.entregado_en ? "entregado, sin leer" : "pendiente de entrega"}</span>
            </li>)}
            {!d.mensajes.length && <li className="text-ms-gray-60">Sin mensajes.</li>}
          </ul>
        </div>
      </div>
      <p className="text-xs text-ms-gray-60">Últimos reportes: {d.latidos.slice(0, 5).map((l) => fechaHora(l.recibido_en)).join(" · ") || "ninguno"} · IP {e.ultima_ip || "—"}</p>
    </div>
  );
}
