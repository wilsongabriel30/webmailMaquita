// Editor de un reenvío: destinos (agregar, corregir, quitar), copia en el buzón y eliminar todo.
// Se abre al hacer clic en la fila. Guarda con PUT /api/forwarding/<origen>.
import { useEffect, useState } from "react";
import { api } from "../api/client";

export interface ReenvioEditable { address: string; goto: string; name?: string; has_mailbox: boolean; active: boolean }

const esCorreo = (s: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s);

export function EditorReenvio({ reenvio, onCerrar, onGuardado, onEliminar }: {
  reenvio: ReenvioEditable; onCerrar: () => void; onGuardado: () => void; onEliminar: (address: string) => void;
}) {
  const origen = reenvio.address.toLowerCase();
  const inicial = () => {
    const todos = reenvio.goto.split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
    return { destinos: todos.filter((d) => d !== origen), copia: todos.includes(origen) };
  };
  const [destinos, setDestinos] = useState<string[]>(inicial().destinos);
  const [copia, setCopia] = useState<boolean>(inicial().copia);
  const [nuevo, setNuevo] = useState("");
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  useEffect(() => { const i = inicial(); setDestinos(i.destinos); setCopia(i.copia); setNuevo(""); setError(""); }, [reenvio.address, reenvio.goto]);

  const agregar = () => {
    const d = nuevo.trim().toLowerCase();
    if (!d) return;
    if (!esCorreo(d)) { setError(`«${d}» no es una dirección válida`); return; }
    if (d === origen) { setError("El origen no puede ser su propio destino; usa «Conservar copia»"); return; }
    if (destinos.includes(d)) { setError("Ese destino ya está en la lista"); return; }
    setDestinos([...destinos, d]); setNuevo(""); setError("");
  };
  const cambiar = (i: number, v: string) => setDestinos(destinos.map((d, j) => (j === i ? v.trim().toLowerCase() : d)));
  const quitar = (i: number) => setDestinos(destinos.filter((_, j) => j !== i));

  const guardar = async () => {
    const malos = destinos.filter((d) => !esCorreo(d));
    if (malos.length) { setError(`Dirección no válida: ${malos.join(", ")}`); return; }
    if (destinos.length === 0 && !copia) { setError("Sin destinos y sin copia el correo se perdería. Agrega un destino o elimina el reenvío."); return; }
    setGuardando(true); setError("");
    try {
      await api.put(`/forwarding/${encodeURIComponent(origen)}`, { destinos, keep_copy: copia });
      onGuardado();
    } catch (e: any) { setError(e?.message || "No se pudo guardar"); }
    finally { setGuardando(false); }
  };

  const sinCambios = JSON.stringify({ destinos, copia }) === JSON.stringify(inicial());

  return (
    <div className="bg-white rounded border border-ms-blue/40 p-5 space-y-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-ms-gray-130">{origen}</div>
          {reenvio.name && <div className="text-xs text-ms-gray-60">{reenvio.name}</div>}
          <div className="text-[11px] text-ms-gray-60 mt-1">{reenvio.has_mailbox ? "Tiene buzón propio" : "Solo redirige (sin buzón)"} · {reenvio.active ? "Activo" : "Inactivo"}</div>
        </div>
        <button onClick={onCerrar} title="Cerrar sin guardar" className="text-ms-gray-60 hover:text-ms-gray-130 text-lg leading-none">&times;</button>
      </div>

      <div>
        <div className="text-xs font-semibold text-ms-gray-130 mb-2">Se reenvía a</div>
        {destinos.length === 0 && <div className="text-xs text-ms-gray-60 mb-2">Ningún destino: el correo solo queda en el buzón de origen.</div>}
        <div className="space-y-1.5">
          {destinos.map((d, i) => (
            <div key={i} className="flex items-center gap-2">
              <input value={d} onChange={(e) => cambiar(i, e.target.value)} title="Corrige la dirección de destino. Se aplica al pulsar Guardar."
                className={`flex-1 px-3 py-1.5 border rounded text-sm focus:outline-none focus:border-ms-blue ${esCorreo(d) ? "border-ms-gray-40" : "border-ms-red"}`} />
              <button onClick={() => quitar(i)} title="Quita este destino (se aplica al pulsar Guardar)." className="text-xs text-ms-red hover:underline">Quitar</button>
            </div>
          ))}
        </div>
        <div className="flex items-center gap-2 mt-2">
          <input value={nuevo} onChange={(e) => setNuevo(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") agregar(); }}
            placeholder="Agregar otra cuenta que reciba el reenvío…" title="Dirección interna o externa. Enter o «Agregar» la añade a la lista; se aplica al pulsar Guardar."
            className="flex-1 px-3 py-1.5 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
          <button onClick={agregar} className="px-3 py-1.5 bg-ms-gray-20 rounded text-sm hover:bg-ms-gray-30">Agregar</button>
        </div>
      </div>

      {reenvio.has_mailbox && (
        <label className="flex items-center gap-2 text-sm text-ms-gray-130" title="Marcado: el correo queda también en el buzón de origen. Desmarcado: solo llega a los destinos.">
          <input type="checkbox" checked={copia} onChange={(e) => setCopia(e.target.checked)} className="accent-ms-blue" />
          Conservar copia en el buzón de {origen}
        </label>
      )}

      {error && <div className="text-xs text-ms-red">{error}</div>}

      <div className="flex items-center gap-2">
        <button onClick={guardar} disabled={guardando || sinCambios} title="Guarda los destinos y la opción de copia. Se registra en auditoría."
          className="px-4 py-2 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark disabled:opacity-50">{guardando ? "Guardando…" : "Guardar"}</button>
        <button onClick={onCerrar} className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90">Cancelar</button>
        <span className="flex-1" />
        <button onClick={() => onEliminar(origen)} title="Elimina el reenvío completo: los correos dejan de copiarse a todos los destinos y siguen llegando solo al buzón de origen. Se registra en auditoría."
          className="px-3 py-2 text-ms-red border border-ms-red/30 rounded text-sm hover:bg-red-50">Eliminar reenvío</button>
      </div>
    </div>
  );
}
