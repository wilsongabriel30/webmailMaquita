import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { Equipo, fechaHora } from "./tipos";

interface Fila { id: number; titulo: string; nivel: string; creado_por: string; creado_en: string; destinatarios: number; entregados: number; leidos: number }
interface Det { mensaje: { titulo: string; texto: string }; equipos: { id: number; nombre: string; modelo?: string; custodio_nombre?: string; entregado_en?: string; leido_en?: string }[] }

export function Mensajes({ equipos }: { equipos: Equipo[] }) {
  const [lista, setLista] = useState<Fila[]>([]);
  const [det, setDet] = useState<Det | null>(null);
  const [f, setF] = useState({ titulo: "", texto: "", nivel: "urgente", requiere_acuse: true, todos: true });
  const [sel, setSel] = useState<number[]>([]);
  const [msg, setMsg] = useState<{ ok: boolean; t: string } | null>(null);
  const activos = equipos.filter((e) => e.estado === "activo" || e.estado === "perdido");

  const cargar = () => api.get<{ mensajes: Fila[] }>("/dispositivos/mensajes").then((r) => setLista(r.mensajes)).catch((e) => setMsg({ ok: false, t: e.message }));
  useEffect(() => { cargar(); }, []);

  const enviar = async () => {
    const n = f.todos ? activos.length : sel.length;
    if (!n) { setMsg({ ok: false, t: "No hay equipos destinatarios." }); return; }
    if (!confirm(`¿Enviar «${f.titulo}» a ${n} equipo(s)? Sonará como aviso ${f.nivel} y quedará en la auditoría.`)) return;
    try {
      const r = await api.post<{ destinatarios: number }>("/dispositivos/mensajes", { ...f, equipos: f.todos ? null : sel });
      setMsg({ ok: true, t: `Enviado a ${r.destinatarios} equipo(s). Cada teléfono lo muestra en su próximo reporte (hasta 15 minutos).` });
      setF({ ...f, titulo: "", texto: "" }); setSel([]); cargar();
    } catch (e: any) { setMsg({ ok: false, t: e.message }); }
  };

  return (
    <div className="space-y-4">
      {msg && <div className={`text-sm px-3 py-2 rounded ${msg.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>{msg.t}</div>}
      <div className="bg-white rounded-lg border border-ms-gray-30 p-4 space-y-3">
        <h3 className="text-sm font-semibold">Nuevo mensaje al personal</h3>
        <input value={f.titulo} onChange={(e) => setF({ ...f, titulo: e.target.value })} maxLength={160} placeholder="Título (ej: Alerta: corte de energía en la matriz)"
          className="w-full px-3 py-1.5 text-sm border border-ms-gray-40 rounded" />
        <textarea value={f.texto} onChange={(e) => setF({ ...f, texto: e.target.value })} rows={3} maxLength={4000} placeholder="Texto del mensaje"
          className="w-full px-3 py-1.5 text-sm border border-ms-gray-40 rounded" />
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <label>Nivel <select value={f.nivel} onChange={(e) => setF({ ...f, nivel: e.target.value })} className="ml-1 px-2 py-1 border border-ms-gray-40 rounded">
            <option value="urgente">Urgente (pantalla completa y alarma)</option><option value="importante">Importante</option><option value="informativo">Informativo</option></select></label>
          <label className="flex items-center gap-1.5"><input type="checkbox" checked={f.requiere_acuse} onChange={(e) => setF({ ...f, requiere_acuse: e.target.checked })} />Exigir «Leído»</label>
          <label className="flex items-center gap-1.5"><input type="checkbox" checked={f.todos} onChange={(e) => setF({ ...f, todos: e.target.checked })} />Todos los equipos activos ({activos.length})</label>
        </div>
        {!f.todos && <div className="max-h-40 overflow-y-auto border border-ms-gray-30 rounded p-2 grid md:grid-cols-2 gap-1 text-sm">
          {activos.map((e) => <label key={e.id} className="flex items-center gap-1.5">
            <input type="checkbox" checked={sel.includes(e.id)} onChange={(ev) => setSel(ev.target.checked ? [...sel, e.id] : sel.filter((i) => i !== e.id))} />
            {e.nombre || e.modelo} <span className="text-xs text-ms-gray-60">{e.custodio_nombre}</span></label>)}
        </div>}
        <button onClick={enviar} disabled={!f.titulo.trim() || !f.texto.trim()} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark disabled:opacity-50">Enviar</button>
      </div>

      <div className="bg-white rounded-lg border border-ms-gray-30 overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="bg-ms-gray-10">{["Mensaje", "Nivel", "Enviado", "Entregados", "Leídos", ""].map((h) => <th key={h} className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">{h}</th>)}</tr></thead>
          <tbody>
            {lista.map((m) => <tr key={m.id} className="border-t border-ms-gray-20">
              <td className="px-4 py-2.5 font-medium">{m.titulo}</td><td className="px-4 py-2.5">{m.nivel}</td>
              <td className="px-4 py-2.5 text-xs">{fechaHora(m.creado_en)}<div className="text-ms-gray-60">{m.creado_por}</div></td>
              <td className="px-4 py-2.5">{m.entregados} / {m.destinatarios}</td>
              <td className={`px-4 py-2.5 ${m.leidos < m.destinatarios ? "text-amber-700" : "text-green-700"}`}>{m.leidos} / {m.destinatarios}</td>
              <td className="px-4 py-2.5 text-right"><button onClick={() => api.get<Det>(`/dispositivos/mensajes/${m.id}`).then(setDet)} className="text-xs text-ms-blue hover:underline">Quién leyó</button></td>
            </tr>)}
            {!lista.length && <tr><td colSpan={6} className="px-4 py-6 text-center text-ms-gray-60">Aún no se ha enviado ningún mensaje.</td></tr>}
          </tbody>
        </table>
      </div>

      {det && <div className="bg-white rounded-lg border border-ms-gray-30 p-4">
        <div className="flex justify-between"><h3 className="text-sm font-semibold">{det.mensaje.titulo}</h3><button onClick={() => setDet(null)} className="text-xs text-ms-blue">Cerrar</button></div>
        <p className="text-sm text-ms-gray-90 whitespace-pre-wrap my-2">{det.mensaje.texto}</p>
        <ul className="text-sm space-y-1">{det.equipos.map((e) => <li key={e.id} className="flex justify-between gap-2">
          <span>{e.nombre || e.modelo} <span className="text-xs text-ms-gray-60">{e.custodio_nombre}</span></span>
          <span className={`text-xs ${e.leido_en ? "text-green-700" : "text-amber-700"}`}>{e.leido_en ? `leído ${fechaHora(e.leido_en)}` : e.entregado_en ? `entregado ${fechaHora(e.entregado_en)}, sin leer` : "aún no entregado"}</span></li>)}</ul>
      </div>}
    </div>
  );
}
