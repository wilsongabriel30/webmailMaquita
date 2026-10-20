import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { Comprobacion } from "./Comprobacion";
import { AYUDA_TIPO, TIPOS, type Registro } from "./tipos";

const VACIO = { nombre: "@", tipo: "A", valor: "", ttl: 3600, prioridad: null as number | null };

/* Registros de una zona: ver, añadir, editar y borrar (cada cambio se valida con BIND antes de aplicarse). */
export function EditorZona({ zona, onVolver }: { zona: string; onVolver: () => void }) {
  const [regs, setRegs] = useState<Registro[]>([]);
  const [servidores, setServidores] = useState<string[]>([]);
  const [form, setForm] = useState(VACIO);
  const [editando, setEditando] = useState<string | null>(null);
  const [error, setError] = useState("");

  const cargar = () => api.get<{ registros: Registro[]; servidores: string[] }>(`/dns/${zona}`)
    .then((d) => { setRegs(d.registros); setServidores(d.servidores); }).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, [zona]);

  const guardar = async () => {
    setError("");
    try {
      if (editando) await api.put(`/dns/${zona}/registros/${editando}`, form);
      else await api.post(`/dns/${zona}/registros`, form);
      setForm(VACIO); setEditando(null); cargar();
    } catch (e) { setError((e as Error).message); }
  };

  const editar = (r: Registro) => {
    if (r.sistema && !confirm("Este registro lo creó el asistente y lo usa el correo o la web. ¿Editarlo de todos modos?")) return;
    setEditando(r.id);
    setForm({ nombre: r.nombre, tipo: r.tipo, valor: r.tipo === "TXT" ? r.valor : r.valor, ttl: r.ttl, prioridad: r.prioridad });
  };

  const borrar = async (r: Registro) => {
    const aviso = r.sistema ? "Este registro lo creó el asistente: borrarlo puede dejar sin correo o sin web al dominio. " : "";
    if (!confirm(`${aviso}¿Borrar ${r.tipo} ${r.nombre}?`)) return;
    try { await api.del(`/dns/${zona}/registros/${r.id}`); cargar(); } catch (e) { setError((e as Error).message); }
  };

  const campo = "px-2 py-1.5 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue";
  const conPrioridad = form.tipo === "MX" || form.tipo === "SRV";
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-ms-gray-130">{zona}</h2>
        <button onClick={onVolver} className="text-ms-blue hover:underline text-sm">← Todas las zonas</button>
      </div>
      <p className="text-xs text-ms-gray-90">Servidores de nombres a poner en el registrador: <span className="font-mono">{servidores.join(", ")}</span></p>
      {error && <div className="bg-red-50 border border-red-200 text-ms-red rounded px-3 py-2 text-sm">{error}</div>}

      <div className="bg-white rounded border border-ms-gray-30 p-4 space-y-2">
        <div className="flex flex-wrap gap-2 items-center">
          <input value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} placeholder="@ o subnombre" className={`${campo} w-36`} title="«@» es el propio dominio; «www», «blog», «_dmarc»…" />
          <select value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })} className={campo}>
            {TIPOS.map((t) => <option key={t}>{t}</option>)}
          </select>
          {conPrioridad && <input type="number" value={form.prioridad ?? ""} onChange={(e) => setForm({ ...form, prioridad: e.target.value === "" ? null : Number(e.target.value) })} placeholder="prioridad" className={`${campo} w-24`} />}
          <input value={form.valor} onChange={(e) => setForm({ ...form, valor: e.target.value })} placeholder="valor" className={`${campo} flex-1 min-w-[16rem]`} />
          <input type="number" value={form.ttl} onChange={(e) => setForm({ ...form, ttl: Number(e.target.value) })} className={`${campo} w-24`} title="Tiempo en caché (segundos)" />
          <button onClick={guardar} disabled={!form.valor} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm disabled:opacity-50">{editando ? "Guardar" : "Añadir"}</button>
          {editando && <button onClick={() => { setEditando(null); setForm(VACIO); }} className="text-sm text-ms-gray-90 hover:underline">Cancelar</button>}
        </div>
        <p className="text-xs text-ms-gray-60">{AYUDA_TIPO[form.tipo]}</p>
      </div>

      <div className="bg-white rounded border border-ms-gray-30 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-ms-gray-20 border-b border-ms-gray-30">
            <tr>
              {["Nombre", "Tipo", "Valor", "TTL", ""].map((h) => <th key={h} className="text-left px-3 py-2 font-medium text-ms-gray-90 text-xs">{h}</th>)}
            </tr>
          </thead>
          <tbody className="divide-y divide-ms-gray-30">
            {regs.map((r) => (
              <tr key={r.id} className="hover:bg-ms-blue-lighter/50 align-top">
                <td className="px-3 py-2 font-mono text-xs whitespace-nowrap">{r.nombre}</td>
                <td className="px-3 py-2 text-xs">{r.tipo}{r.sistema && <span className="ml-1 text-[10px] text-ms-gray-60" title="Creado por el asistente">●</span>}</td>
                <td className="px-3 py-2 font-mono text-xs break-all max-w-xl">{r.prioridad !== null ? `${r.prioridad} ` : ""}{r.valor}</td>
                <td className="px-3 py-2 text-xs">{r.ttl}</td>
                <td className="px-3 py-2 text-right whitespace-nowrap text-xs">
                  <button onClick={() => editar(r)} className="text-ms-blue hover:underline mr-3">Editar</button>
                  <button onClick={() => borrar(r)} className="text-ms-red hover:underline">Borrar</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Comprobacion zona={zona} />
    </div>
  );
}
