import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { fechaHora } from "./tipos";
import { rolActual } from "./telemetria/tipos";

// Wifi de las sedes compartido con la flota: Tecnología registra nombre y clave (cifrada) de cada sede;
// los teléfonos enrolados reciben la lista y se conectan solos al llegar. Si un teléfono corrige una
// clave y logra conectarse, se replica a todos (aparece en «Cambios»).

interface Cambio { quien: string; origen: string; detalle: string; hecho_en: string }
interface Red { id: number; sede: string; ssid: string; seguridad: string; oculta: boolean; activa: boolean; nota: string; version: number; actualizado_por: string; actualizado_en: string; con_clave: boolean; conectados_ahora: number; cambios: Cambio[]; origen: string; compartida_por?: string | null; ultimo_uso?: string | null }
const VACIO = { id: 0, sede: "", ssid: "", clave: "", seguridad: "WPA", oculta: false, activa: true, nota: "" };

export function Wifis() {
  const [d, setD] = useState<{ version: number; redes: Red[] } | null>(null);
  const [f, setF] = useState<typeof VACIO>(VACIO);
  const [msg, setMsg] = useState<{ ok: boolean; t: string } | null>(null);
  const [vista, setVista] = useState<{ id: number; clave: string | null } | null>(null);
  const admin = rolActual() !== "viewer";
  const cargar = () => api.get<{ version: number; redes: Red[] }>("/dispositivos/wifis").then(setD).catch((e) => setMsg({ ok: false, t: e.message }));
  useEffect(() => { cargar(); }, []);

  const guardar = async () => {
    try { await api.post("/dispositivos/wifis", f); setF(VACIO); setMsg({ ok: true, t: "Guardado: los teléfonos recibirán la red en su próximo reporte." }); cargar(); }
    catch (e: any) { setMsg({ ok: false, t: e.message }); }
  };
  const editar = (r: Red) => { setF({ id: r.id, sede: r.sede, ssid: r.ssid, clave: "", seguridad: r.seguridad, oculta: r.oculta, activa: r.activa, nota: r.nota }); setVista(null); window.scrollTo({ top: 0, behavior: "smooth" }); };
  const borrar = async (r: Red) => { if (confirm(`¿Quitar la red «${r.ssid}» de ${r.sede}? Los teléfonos dejarán de recibirla.`)) { await api.del(`/dispositivos/wifis/${r.id}`); cargar(); } };
  const verClave = async (r: Red) => { try { const x = await api.get<{ clave: string | null }>(`/dispositivos/wifis/${r.id}/clave`); setVista({ id: r.id, clave: x.clave }); } catch (e: any) { setMsg({ ok: false, t: e.message }); } };

  return (
    <div className="space-y-4">
      {msg && <div className={`text-sm px-3 py-2 rounded ${msg.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>{msg.t}</div>}
      {admin && <div className="bg-white rounded-lg border border-ms-gray-30 p-4 space-y-3">
        <h3 className="text-sm font-semibold">{f.id ? `Editar red «${f.ssid}»` : "Nueva red wifi de una sede"}</h3>
        <p className="text-xs text-ms-gray-60">Los teléfonos institucionales reciben estas redes y se conectan solos al llegar. Además, cualquier red que un compañero conecte con su app (un evento, un hotel, un aliado) y acepte compartir aparece aquí sola, marcada «compartida por», y llega a toda la flota sin que Tecnología haga nada. La clave se guarda cifrada y solo viaja a teléfonos enrolados. Si alguien cambia la clave del router, actualícela aquí (o el primer teléfono que la corrija y se conecte la replicará a todos).</p>
        <div className="flex flex-wrap items-end gap-3 text-sm">
          <label className="text-xs">Sede<input value={f.sede} onChange={(e) => setF({ ...f, sede: e.target.value })} placeholder="Maquita central" className="mt-1 block w-40 px-2.5 py-1.5 text-sm border border-ms-gray-40 rounded" /></label>
          <label className="text-xs">Nombre de la red (SSID)<input value={f.ssid} onChange={(e) => setF({ ...f, ssid: e.target.value })} placeholder="MAQUITA CENTRAL" className="mt-1 block w-44 px-2.5 py-1.5 text-sm border border-ms-gray-40 rounded" /></label>
          <label className="text-xs">Clave{f.id ? " (vacía = no cambia)" : ""}<input type="password" value={f.clave} onChange={(e) => setF({ ...f, clave: e.target.value })} className="mt-1 block w-40 px-2.5 py-1.5 text-sm border border-ms-gray-40 rounded" /></label>
          <label className="text-xs">Seguridad<select value={f.seguridad} onChange={(e) => setF({ ...f, seguridad: e.target.value })} className="mt-1 block px-2.5 py-1.5 text-sm border border-ms-gray-40 rounded"><option value="WPA">WPA2</option><option value="WPA3">WPA3</option><option value="NONE">Abierta</option></select></label>
          <label className="text-xs">Nota<input value={f.nota} onChange={(e) => setF({ ...f, nota: e.target.value })} placeholder="Piso 2, sala de reuniones" className="mt-1 block w-44 px-2.5 py-1.5 text-sm border border-ms-gray-40 rounded" /></label>
          <label className="text-xs flex items-center gap-1 pb-2"><input type="checkbox" checked={f.oculta} onChange={(e) => setF({ ...f, oculta: e.target.checked })} />Red oculta</label>
          {f.id ? <label className="text-xs flex items-center gap-1 pb-2"><input type="checkbox" checked={f.activa} onChange={(e) => setF({ ...f, activa: e.target.checked })} />Activa</label> : null}
          <button onClick={guardar} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark">{f.id ? "Guardar cambios" : "Agregar red"}</button>
          {f.id ? <button onClick={() => setF(VACIO)} className="px-3 py-1.5 text-sm border border-ms-gray-40 rounded">Cancelar</button> : null}
        </div>
      </div>}
      <div className="bg-white rounded-lg border border-ms-gray-30 overflow-x-auto">
        <div className="px-4 py-2 border-b border-ms-gray-20 text-xs text-ms-gray-60">Lista versión {d?.version ?? "…"} · los teléfonos la reciben en su siguiente reporte (máximo 15 min) y se conectan solos cuando estén en el sitio.</div>
        <table className="w-full text-sm">
          <thead><tr className="bg-ms-gray-10">{["Sede", "Red", "Seguridad", "Clave", "Conectados ahora", "Actualizada", "Cambios recientes", ""].map((h) => <th key={h} className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">{h}</th>)}</tr></thead>
          <tbody>
            {(d?.redes || []).map((r) => <tr key={r.id} className={`border-t border-ms-gray-20 ${r.activa ? "" : "text-ms-gray-60"}`}>
              <td className="px-4 py-2.5">{r.sede}{!r.activa && <span className="ml-1 text-xs">(inactiva)</span>}{r.origen === "telefono" && <div className="text-xs text-blue-700">compartida por {r.compartida_por}</div>}</td>
              <td className="px-4 py-2.5 font-medium">{r.ssid}{r.oculta && <span className="ml-1 text-xs text-ms-gray-60">(oculta)</span>}{r.nota && <div className="text-xs text-ms-gray-60 font-normal">{r.nota}</div>}</td>
              <td className="px-4 py-2.5 text-xs">{r.seguridad === "NONE" ? "Abierta" : r.seguridad === "WPA3" ? "WPA3" : "WPA2"}</td>
              <td className="px-4 py-2.5 text-xs">{r.seguridad === "NONE" ? "—" : vista?.id === r.id ? <code className="font-mono">{vista.clave || "(sin clave)"}</code> : r.con_clave ? (admin ? <button onClick={() => verClave(r)} className="text-ms-blue hover:underline" title="Queda en la auditoría">Ver</button> : "••••••••") : <span className="text-red-600">sin clave</span>}</td>
              <td className="px-4 py-2.5">{r.conectados_ahora}</td>
              <td className="px-4 py-2.5 text-xs">{fechaHora(r.actualizado_en)}<div className="text-ms-gray-60">{r.actualizado_por}</div></td>
              <td className="px-4 py-2.5 text-xs">{r.cambios.slice(0, 2).map((c, i) => <div key={i} className={c.origen === "telefono" ? "text-blue-700" : ""}>{fechaHora(c.hecho_en)} · {c.quien}: {c.detalle}</div>)}</td>
              <td className="px-4 py-2.5 text-right whitespace-nowrap">{admin && <><button onClick={() => editar(r)} className="text-xs text-ms-blue hover:underline mr-3">Editar</button><button onClick={() => borrar(r)} className="text-xs text-ms-red hover:underline">Quitar</button></>}</td>
            </tr>)}
            {d && !d.redes.length && <tr><td colSpan={8} className="px-4 py-6 text-center text-ms-gray-60">Aún no hay redes registradas. Agregue el wifi de cada sede.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
