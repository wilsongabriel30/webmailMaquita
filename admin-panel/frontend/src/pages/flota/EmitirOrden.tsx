import { useState } from "react";
import { api } from "../../api/client";
import { Catalogo, EquipoFlota } from "./tipos";

// Emitir una orden firmada. El servidor la firma con la clave de Flota; el agente la recoge en su
// siguiente sondeo (≤ 15 min) y rechaza cualquier orden sin firma válida. Las de hardware (fase 3) siguen
// bloqueadas hasta el OK de protección de datos y piden escribir CONFIRMO.

interface Props { catalogo: Catalogo; equipos: EquipoFlota[]; seleccion: string[]; onCerrar: () => void; onHecho: () => void }

export function EmitirOrden({ catalogo, equipos, seleccion, onCerrar, onHecho }: Props) {
  const [todos, setTodos] = useState(seleccion.length === 0);
  const [f, setF] = useState({ tipo: "ping", motivo: "", horas_validez: 72, accion: "", confirmacion: "" });
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const tipo = catalogo.tipos.find((t) => t.tipo === f.tipo);
  const nombres = equipos.filter((e) => e.equipo_id && seleccion.includes(e.equipo_id)).map((e) => e.nombre);
  const activos = equipos.filter((e) => e.enrolado && e.estado === "activo").length;

  const emitir = async () => {
    const destino = todos ? `TODOS los equipos activos (${activos})` : `${seleccion.length} equipo(s)`;
    if (!confirm(`¿Emitir «${tipo?.nombre}» a ${destino}? Queda en el registro con su motivo.`)) return;
    setEnviando(true); setError("");
    try {
      await api.post("/flota/ordenes", {
        tipo: f.tipo, motivo: f.motivo, horas_validez: f.horas_validez, confirmacion: f.confirmacion,
        parametros: tipo?.acciones.length ? { accion: f.accion } : {}, ...(todos ? { todos: true } : { equipos: seleccion }),
      });
      onHecho();
    } catch (e: any) { setError(e.message); } finally { setEnviando(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-lg w-full max-w-lg p-5 space-y-3 text-sm">
        <h3 className="font-semibold text-base">Emitir orden firmada</h3>
        {!catalogo.firma_disponible && <div className="px-3 py-2 rounded bg-red-50 text-red-700 text-xs">Falta la clave de firma en el servidor: no se puede emitir.</div>}
        <div className="text-xs text-ms-gray-90">
          {seleccion.length > 0 && <label className="flex items-center gap-2"><input type="radio" checked={!todos} onChange={() => setTodos(false)} />Seleccionados: {nombres.join(", ")}</label>}
          <label className="flex items-center gap-2"><input type="radio" checked={todos} onChange={() => setTodos(true)} />Todos los equipos activos ({activos})</label>
        </div>
        <label className="block text-xs">Orden
          <select value={f.tipo} onChange={(e) => setF({ ...f, tipo: e.target.value, accion: "", confirmacion: "" })} className="mt-1 block w-full px-2.5 py-1.5 border border-ms-gray-40 rounded">
            {catalogo.tipos.filter((t) => !t.dedicada).map((t) => <option key={t.tipo} value={t.tipo} disabled={!t.habilitado}>{t.nombre}{t.habilitado ? "" : " — fase 3, bloqueada"}</option>)}
          </select>
          {tipo && <span className="block mt-1 text-ms-gray-60">{tipo.desc}</span>}
        </label>
        {tipo && tipo.acciones.length > 0 && <label className="block text-xs">Acción
          <select value={f.accion} onChange={(e) => setF({ ...f, accion: e.target.value })} className="mt-1 block w-full px-2.5 py-1.5 border border-ms-gray-40 rounded">
            <option value="">— elegir —</option>{tipo.acciones.map((a) => <option key={a} value={a}>{a}</option>)}</select></label>}
        <label className="block text-xs">Motivo (queda en el registro)
          <input value={f.motivo} onChange={(e) => setF({ ...f, motivo: e.target.value })} placeholder="Ej: publicar 0.7.18 antes de la reunión" className="mt-1 block w-full px-2.5 py-1.5 border border-ms-gray-40 rounded" /></label>
        <label className="block text-xs">Válida durante (horas)
          <input type="number" min={1} max={720} value={f.horas_validez} onChange={(e) => setF({ ...f, horas_validez: Number(e.target.value) })} className="mt-1 block w-24 px-2.5 py-1.5 border border-ms-gray-40 rounded" /></label>
        {tipo && tipo.fase >= 3 && <label className="block text-xs text-red-700">Orden de hardware: escriba CONFIRMO
          <input value={f.confirmacion} onChange={(e) => setF({ ...f, confirmacion: e.target.value })} className="mt-1 block w-40 px-2.5 py-1.5 border border-red-300 rounded" /></label>}
        {error && <div className="px-3 py-2 rounded bg-red-50 text-red-700 text-xs">{error}</div>}
        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onCerrar} className="px-3 py-1.5 border border-ms-gray-40 rounded">Cancelar</button>
          <button disabled={enviando || !catalogo.firma_disponible || f.motivo.trim().length < 5} onClick={emitir} className="px-3 py-1.5 bg-ms-blue text-white rounded disabled:opacity-40">Firmar y emitir</button>
        </div>
      </div>
    </div>
  );
}
