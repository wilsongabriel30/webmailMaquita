import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

// Multicuenta del webmail, vista por persona: a quien entra con ventas@ se le asignan turismo@ y
// operaciones@, y las ve en la barra «Cuentas» de su webmail sin cerrar sesión.
interface Asignacion { id: number; persona: string; cuenta: string; completo: boolean; nombre_persona?: string; nombre_cuenta?: string; created_at?: string }
interface Buzon { username: string; name?: string; active: boolean }

const VACIO = { persona: "", cuenta: "", solo_lectura: false };

export function CuentasAsignadas() {
  const [asignaciones, setAsignaciones] = useState<Asignacion[]>([]);
  const [buzones, setBuzones] = useState<Buzon[]>([]);
  const [form, setForm] = useState(VACIO);
  const [mostrarForm, setMostrarForm] = useState(false);
  const [mensaje, setMensaje] = useState<{ tipo: "ok" | "error"; texto: string } | null>(null);
  const [busqueda, setBusqueda] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const cargar = () => Promise.all([api.get<Asignacion[]>("/asignaciones"), api.get<Buzon[]>("/mailboxes")])
    .then(([a, b]) => { setAsignaciones(a); setBuzones(b.filter((x) => x.active)); })
    .catch((e: Error) => setMensaje({ tipo: "error", texto: e.message || "No se pudo cargar la lista" }));
  useEffect(() => { cargar(); }, []);

  // Agrupadas por persona: una tarjeta por cada quien, con todas sus cuentas asignadas.
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

  const abrirForm = (persona = "") => { setForm({ ...VACIO, persona }); setMensaje(null); setMostrarForm(true); };

  const asignar = async () => {
    setOcupado(true); setMensaje(null);
    try {
      const r = await api.post<Asignacion>("/asignaciones", { persona: form.persona, cuenta: form.cuenta, completo: !form.solo_lectura });
      setMensaje({ tipo: "ok", texto: `${r.cuenta} asignada a ${r.persona}. La verá en su webmail al volver a cargarlo.` });
      setForm({ ...VACIO, persona: form.persona });
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

  const entrada = "px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue w-full";

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ms-gray-130">Cuentas asignadas por persona ({porPersona.length})</h1>
        <div className="flex items-center gap-2">
          <SectionHelp
            titulo="Cuentas asignadas (varias cuentas en un webmail)"
            items={[
              { titulo: "Para qué sirve", desc: "Una persona ve en su webmail, además de la suya, las cuentas que se le asignen aquí (de cualquier dominio). Las cambia con un clic en la barra «Cuentas», sin cerrar sesión ni abrir otro navegador. Drive, chat y calendario siguen siendo los suyos." },
              { titulo: "Persona", desc: "El correo con el que entra al webmail. Ejemplo: ventas@ejemplo.org." },
              { titulo: "Cuenta que se le asigna", desc: "La cuenta que va a ver. Ejemplo: turismo@ejemplo.org. Se le pueden asignar tantas como haga falta, de uno o varios dominios." },
              { titulo: "Completo o solo lectura", desc: "Completo: lee, envía como esa cuenta (con su firma) y gestiona sus carpetas. Solo lectura: solo lee." },
              { titulo: "Quitar", desc: "El acceso se corta al instante, aunque tenga el webmail abierto. La cuenta y su correo no se tocan." },
              { titulo: "Portal de cada dominio", desc: "El administrador de un dominio puede hacer lo mismo desde su portal, solo con cuentas de sus dominios." },
            ]}
          />
          <button onClick={() => abrirForm()} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark">+ Asignar cuenta</button>
        </div>
      </div>

      {mensaje && <p role={mensaje.tipo === "error" ? "alert" : "status"} className={`px-3 py-2 rounded text-sm ${mensaje.tipo === "error" ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>{mensaje.texto}</p>}

      {mostrarForm && (
        <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-3">
          <datalist id="cuentas-activas">{buzones.map((b) => <option key={b.username} value={b.username}>{b.name || ""}</option>)}</datalist>
          <div className="grid grid-cols-2 gap-3">
            <label className="text-sm text-ms-gray-90">Persona (su correo de entrada)
              <input list="cuentas-activas" value={form.persona} onChange={(e) => setForm({ ...form, persona: e.target.value })} placeholder="ventas@ejemplo.org" autoComplete="off" className={entrada + " mt-1"} />
            </label>
            <label className="text-sm text-ms-gray-90">Cuenta que se le asigna
              <input list="cuentas-activas" value={form.cuenta} onChange={(e) => setForm({ ...form, cuenta: e.target.value })} placeholder="turismo@ejemplo.org" autoComplete="off" className={entrada + " mt-1"} />
            </label>
          </div>
          <label className="flex items-center gap-2 text-sm text-ms-gray-130">
            <input type="checkbox" checked={form.solo_lectura} onChange={(e) => setForm({ ...form, solo_lectura: e.target.checked })} className="accent-ms-blue" />
            Solo lectura (puede leer, pero no enviar como esa cuenta)
          </label>
          <div className="flex gap-2">
            <button onClick={asignar} disabled={ocupado || !form.persona || !form.cuenta} className="px-4 py-2 bg-ms-blue text-white rounded text-sm disabled:opacity-50">Asignar</button>
            <button onClick={() => setMostrarForm(false)} className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90">Cerrar</button>
          </div>
        </div>
      )}

      <div className="flex items-center gap-2">
        <input value={busqueda} onChange={(e) => setBusqueda(e.target.value)} placeholder="Buscar por persona, cuenta o nombre…" className="w-96 px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
        {busqueda && <button onClick={() => setBusqueda("")} className="text-xs text-ms-blue hover:underline">Limpiar</button>}
      </div>

      {porPersona.length === 0 ? (
        <p className="bg-white rounded border border-ms-gray-30 p-5 text-sm text-ms-gray-90">{busqueda ? "Nada coincide con la búsqueda." : "Todavía nadie tiene cuentas asignadas."}</p>
      ) : porPersona.map(([persona, p]) => (
        <section key={persona} aria-label={persona} className="bg-white rounded border border-ms-gray-30 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 bg-ms-gray-20 border-b border-ms-gray-30">
            <div><strong className="text-sm text-ms-gray-130">{persona}</strong>{p.nombre && <span className="ml-2 text-xs text-ms-gray-90">{p.nombre}</span>}</div>
            <button onClick={() => abrirForm(persona)} className="text-xs text-ms-blue hover:underline">+ Asignar otra cuenta</button>
          </div>
          <table className="w-full text-sm">
            <thead><tr>
              <th className="text-left px-4 py-2 font-medium text-ms-gray-90 text-xs">Ve la cuenta</th>
              <th className="text-left px-4 py-2 font-medium text-ms-gray-90 text-xs">Permiso</th>
              <th className="text-right px-4 py-2 font-medium text-ms-gray-90 text-xs">Acciones</th>
            </tr></thead>
            <tbody>
              {p.filas.map((a) => (
                <tr key={a.id} className="border-t border-ms-gray-20">
                  <td className="px-4 py-2">{a.cuenta}{a.nombre_cuenta && <span className="ml-2 text-xs text-ms-gray-90">{a.nombre_cuenta}</span>}</td>
                  <td className="px-4 py-2"><span className={`inline-block text-xs px-2 py-0.5 rounded-full ${a.completo ? "bg-green-50 text-green-700" : "bg-amber-50 text-amber-700"}`}>{a.completo ? "Completo" : "Solo lectura"}</span></td>
                  <td className="px-4 py-2 text-right whitespace-nowrap">
                    <button onClick={() => cambiarPermiso(a)} className="text-xs text-ms-blue hover:underline mr-3" aria-label={`${a.completo ? "Dejar en solo lectura" : "Dar acceso completo a"} ${a.cuenta} para ${persona}`}>{a.completo ? "Pasar a solo lectura" : "Dar acceso completo"}</button>
                    <button onClick={() => quitar(a)} className="text-xs text-red-600 hover:underline" aria-label={`Quitar ${a.cuenta} a ${persona}`}>Quitar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
    </div>
  );
}
