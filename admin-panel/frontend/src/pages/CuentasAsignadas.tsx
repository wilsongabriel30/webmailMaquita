import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

// Multicuenta del webmail, vista por persona: una fila por cada quien; al abrirla se ven las
// cuentas que tiene asignadas y se le agregan más ahí mismo (ventas@ ve turismo@, operaciones@…).
interface Asignacion { id: number; persona: string; cuenta: string; completo: boolean; nombre_persona?: string; nombre_cuenta?: string; created_at?: string }
interface Buzon { username: string; name?: string; active: boolean }

export function CuentasAsignadas() {
  const [asignaciones, setAsignaciones] = useState<Asignacion[]>([]);
  const [buzones, setBuzones] = useState<Buzon[]>([]);
  const [abierta, setAbierta] = useState<string | null>(null);
  const [nuevaPersona, setNuevaPersona] = useState("");
  const [nueva, setNueva] = useState("");
  const [soloLectura, setSoloLectura] = useState(false);
  const [mensaje, setMensaje] = useState<{ tipo: "ok" | "error"; texto: string } | null>(null);
  const [busqueda, setBusqueda] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const cargar = () => Promise.all([api.get<Asignacion[]>("/asignaciones"), api.get<Buzon[]>("/mailboxes")])
    .then(([a, b]) => { setAsignaciones(a); setBuzones(b.filter((x) => x.active)); })
    .catch((e: Error) => setMensaje({ tipo: "error", texto: e.message || "No se pudo cargar la lista" }));
  useEffect(() => { cargar(); }, []);

  const porPersona = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    const mapa = new Map<string, { nombre?: string; filas: Asignacion[] }>();
    for (const a of asignaciones) {
      if (q && !a.persona.includes(q) && !a.cuenta.includes(q) && !(a.nombre_persona || "").toLowerCase().includes(q) && !(a.nombre_cuenta || "").toLowerCase().includes(q)) continue;
      if (!mapa.has(a.persona)) mapa.set(a.persona, { nombre: a.nombre_persona, filas: [] });
      mapa.get(a.persona)!.filas.push(a);
    }
    return [...mapa.entries()];
  }, [asignaciones, busqueda]);

  const abrir = (persona: string) => { setAbierta(abierta === persona ? null : persona); setNueva(""); setSoloLectura(false); setMensaje(null); };

  const asignar = async (persona: string) => {
    setOcupado(true); setMensaje(null);
    try {
      const r = await api.post<Asignacion>("/asignaciones", { persona, cuenta: nueva, completo: !soloLectura });
      setMensaje({ tipo: "ok", texto: `${r.cuenta} asignada a ${r.persona}. La verá en su webmail al volver a cargarlo.` });
      setNueva(""); setSoloLectura(false); setNuevaPersona(""); setAbierta(r.persona);
      cargar();
    } catch (e) { setMensaje({ tipo: "error", texto: (e as Error).message || "No se pudo asignar" }); }
    finally { setOcupado(false); }
  };

  const cambiarPermiso = async (a: Asignacion) => {
    try { await api.put(`/asignaciones/${a.id}`, { completo: !a.completo }); cargar(); }
    catch (e) { setMensaje({ tipo: "error", texto: (e as Error).message }); }
  };

  const quitar = async (a: Asignacion) => {
    if (!confirm(`${a.persona} dejará de ver ${a.cuenta} en su webmail desde este momento. La cuenta y su correo no se tocan. ¿Continuar?`)) return;
    try { await api.del(`/asignaciones/${a.id}`); setMensaje({ tipo: "ok", texto: "Asignación quitada." }); cargar(); }
    catch (e) { setMensaje({ tipo: "error", texto: (e as Error).message }); }
  };

  const entrada = "px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue";

  // Formulario «+ Agregar»: el mismo dentro de la fila de una persona y para una persona nueva.
  const formAgregar = (persona: string) => (
    <div className="flex flex-wrap items-center gap-2 px-4 py-3 bg-ms-gray-10 border-t border-ms-gray-20">
      <input list="cuentas-activas" value={nueva} onChange={(e) => setNueva(e.target.value)} placeholder="cuenta@dominio que debe ver" autoComplete="off" className={entrada + " w-80"} />
      <label className="flex items-center gap-1 text-xs text-ms-gray-90"><input type="checkbox" checked={soloLectura} onChange={(e) => setSoloLectura(e.target.checked)} className="accent-ms-blue" /> Solo lectura</label>
      <button onClick={() => asignar(persona)} disabled={ocupado || !persona.includes("@") || !nueva.includes("@")} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm disabled:opacity-50">+ Agregar</button>
    </div>
  );

  return (
    <div className="p-6 space-y-5">
      <datalist id="cuentas-activas">{buzones.map((b) => <option key={b.username} value={b.username}>{b.name || ""}</option>)}</datalist>
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ms-gray-130">Cuentas asignadas por persona ({porPersona.length})</h1>
        <div className="flex items-center gap-2">
          <SectionHelp
            titulo="Cuentas asignadas (varias cuentas en un webmail)"
            items={[
              { titulo: "Para qué sirve", desc: "Una persona ve en su webmail, además de la suya, las cuentas que se le asignen aquí (de cualquier dominio). Las cambia con un clic en la barra «Cuentas», sin cerrar sesión ni abrir otro navegador. Drive, chat y calendario siguen siendo los suyos." },
              { titulo: "Cómo se usa", desc: "Cada fila es una persona (el correo con el que entra al webmail). Clic en la fila para ver sus cuentas asignadas; «+ Agregar» para darle otra. «Nueva persona» para alguien que todavía no tiene ninguna." },
              { titulo: "Completo o solo lectura", desc: "Completo: lee, envía como esa cuenta (con su firma) y gestiona sus carpetas. Solo lectura: solo lee." },
              { titulo: "Quitar", desc: "El acceso se corta al instante, aunque tenga el webmail abierto. La cuenta y su correo no se tocan." },
              { titulo: "Portal de cada dominio", desc: "El administrador de un dominio puede hacer lo mismo desde su portal, solo con cuentas de sus dominios." },
            ]}
          />
          <button onClick={() => { setAbierta(abierta === "__nueva__" ? null : "__nueva__"); setNueva(""); setMensaje(null); }} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark">+ Nueva persona</button>
        </div>
      </div>

      {mensaje && <p role={mensaje.tipo === "error" ? "alert" : "status"} className={`px-3 py-2 rounded text-sm ${mensaje.tipo === "error" ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>{mensaje.texto}</p>}

      {abierta === "__nueva__" && (
        <div className="bg-white rounded border border-ms-gray-30">
          <div className="px-4 py-3 flex items-center gap-2">
            <label className="text-sm text-ms-gray-90">Persona (su correo de entrada)</label>
            <input list="cuentas-activas" value={nuevaPersona} onChange={(e) => setNuevaPersona(e.target.value)} placeholder="quien@dominio" autoComplete="off" className={entrada + " w-80"} />
          </div>
          {formAgregar(nuevaPersona.trim().toLowerCase())}
        </div>
      )}

      <div className="flex items-center gap-2">
        <input value={busqueda} onChange={(e) => setBusqueda(e.target.value)} placeholder="Buscar por persona, cuenta o nombre…" className={entrada + " w-96"} />
        {busqueda && <button onClick={() => setBusqueda("")} className="text-xs text-ms-blue hover:underline">Limpiar</button>}
      </div>

      <div className="bg-white rounded border border-ms-gray-30 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-ms-gray-20 border-b border-ms-gray-30"><tr>
            <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Persona</th>
            <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Nombre</th>
            <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Cuentas que ve</th>
          </tr></thead>
          <tbody>
            {porPersona.length === 0 && (
              <tr><td colSpan={3} className="px-4 py-6 text-center text-ms-gray-60">{busqueda ? "Nada coincide con la búsqueda." : "Todavía nadie tiene cuentas asignadas. Usa «+ Nueva persona»."}</td></tr>
            )}
            {porPersona.map(([persona, p]) => (
              <>
                <tr key={persona} onClick={() => abrir(persona)} aria-expanded={abierta === persona} className={`border-t border-ms-gray-20 cursor-pointer hover:bg-ms-blue-lighter ${abierta === persona ? "bg-ms-blue-lighter" : ""}`}>
                  <td className="px-4 py-2.5 font-medium text-ms-gray-130"><span className="inline-block w-4 text-ms-gray-60">{abierta === persona ? "▾" : "▸"}</span>{persona}</td>
                  <td className="px-4 py-2.5 text-ms-gray-90">{p.nombre || ""}</td>
                  <td className="px-4 py-2.5 text-ms-gray-90">{p.filas.length === 1 ? "1 cuenta" : `${p.filas.length} cuentas`}: {p.filas.map((a) => a.cuenta.split("@")[0]).join(", ")}</td>
                </tr>
                {abierta === persona && (
                  <tr key={persona + "-detalle"}><td colSpan={3} className="p-0">
                    <ul className="divide-y divide-ms-gray-20">
                      {p.filas.map((a) => (
                        <li key={a.id} className="flex items-center justify-between px-10 py-2">
                          <span>{a.cuenta}{a.nombre_cuenta && <span className="ml-2 text-xs text-ms-gray-90">{a.nombre_cuenta}</span>}
                            <span className={`ml-3 inline-block text-xs px-2 py-0.5 rounded-full ${a.completo ? "bg-green-50 text-green-700" : "bg-amber-50 text-amber-700"}`}>{a.completo ? "Completo" : "Solo lectura"}</span></span>
                          <span className="whitespace-nowrap">
                            <button onClick={() => cambiarPermiso(a)} className="text-xs text-ms-blue hover:underline mr-3">{a.completo ? "Pasar a solo lectura" : "Dar acceso completo"}</button>
                            <button onClick={() => quitar(a)} className="text-xs text-red-600 hover:underline" aria-label={`Quitar ${a.cuenta} a ${persona}`}>Quitar</button>
                          </span>
                        </li>
                      ))}
                    </ul>
                    {formAgregar(persona)}
                  </td></tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
