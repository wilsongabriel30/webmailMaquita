import { useEffect, useState } from "react";
import { api } from "../api/client";

// Bloque de la ficha del buzón: qué cuentas ve esta persona en su webmail (multicuenta).
// Misma API que la sección «Cuentas asignadas»; aquí filtrada por la persona.
interface Asignacion { id: number; persona: string; cuenta: string; completo: boolean; nombre_cuenta?: string }

export function CuentasAsignadasBuzon({ persona }: { persona: string }) {
  const [filas, setFilas] = useState<Asignacion[]>([]);
  const [nueva, setNueva] = useState("");
  const [soloLectura, setSoloLectura] = useState(false);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const yo = persona.toLowerCase();

  const cargar = () => api.get<Asignacion[]>("/asignaciones")
    .then((a) => setFilas(a.filter((x) => x.persona === yo)))
    .catch((e: Error) => setError(e.message));
  useEffect(() => { cargar(); }, [yo]);

  const agregar = async () => {
    setOcupado(true); setError("");
    try {
      await api.post("/asignaciones", { persona: yo, cuenta: nueva, completo: !soloLectura });
      setNueva(""); cargar();
    } catch (e) { setError((e as Error).message); }
    finally { setOcupado(false); }
  };

  const quitar = async (a: Asignacion) => {
    if (!confirm(`${yo} dejará de ver ${a.cuenta} en su webmail al instante. ¿Continuar?`)) return;
    try { await api.del(`/asignaciones/${a.id}`); cargar(); } catch (e) { setError((e as Error).message); }
  };

  return (
    <div className="border-t border-ms-gray-30 pt-3">
      <label className="block text-xs text-ms-gray-90 mb-1" title="Cuentas que esta persona ve en la barra «Cuentas» de su webmail, además de la suya.">
        Cuentas que ve en su webmail ({filas.length})
      </label>
      {filas.length === 0 ? (
        <p className="text-xs text-ms-gray-60 mb-2">Ninguna todavía: solo ve su propia cuenta.</p>
      ) : (
        <ul className="mb-2 space-y-1">
          {filas.map((a) => (
            <li key={a.id} className="flex items-center justify-between text-xs">
              <span>{a.cuenta} <span className={a.completo ? "text-green-700" : "text-amber-700"}>({a.completo ? "completo" : "solo lectura"})</span></span>
              <button type="button" onClick={() => quitar(a)} aria-label={`Quitar ${a.cuenta}`} className="text-red-600 hover:underline">Quitar</button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex gap-2 items-center">
        <input value={nueva} onChange={(e) => setNueva(e.target.value)} placeholder="cuenta@dominio que debe ver" autoComplete="off"
          className="flex-1 px-2 py-1.5 border border-ms-gray-40 rounded text-xs focus:outline-none focus:border-ms-blue" />
        <button type="button" onClick={agregar} disabled={ocupado || !nueva.includes("@")} className="px-3 py-1.5 bg-ms-blue text-white rounded text-xs disabled:opacity-50">Asignar</button>
      </div>
      <label className="flex items-center gap-2 text-xs text-ms-gray-90 mt-1">
        <input type="checkbox" checked={soloLectura} onChange={(e) => setSoloLectura(e.target.checked)} className="accent-ms-blue" /> Solo lectura
      </label>
      {error && <div className="text-ms-red text-xs mt-1" role="alert">{error}</div>}
    </div>
  );
}
