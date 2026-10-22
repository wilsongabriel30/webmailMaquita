import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../api/auth";
import { SectionHelp } from "../components/SectionHelp";
import { CredencialesModal } from "./sitios/CredencialesModal";

interface Ficha {
  id: number;
  nombre: string;
  prefijo: string;
  alcances: string[];
  usuario: string;
  creada: string | null;
  vence: string | null;
  ultimo_uso: string | null;
  revocada: boolean;
}
interface Listado { fichas: Ficha[]; areas: Record<string, string>; dias_maximos: number; maximo: number }
interface Creada { id: number; ficha: string; nombre: string; alcances: string[]; vence: string; aviso: string }

const caja = "bg-white rounded border border-ms-gray-30 p-5 space-y-3";
const campo = "px-2 py-1.5 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue";
const fecha = (iso: string | null) => (iso ? new Date(iso).toLocaleString("es") : "—");

/* Fichas de API del panel: para programas propios (Authorization: Bearer mqa_…). Se crean con alcance y caducidad,
   se muestran una sola vez y se pueden revocar. Solo se crean con una sesión abierta con segundo factor. */
export function FichasApi() {
  const { user } = useAuth();
  const [datos, setDatos] = useState<Listado | null>(null);
  const [nueva, setNueva] = useState({ nombre: "", alcances: ["lectura"] as string[], dias: 90, codigo: "" });
  const [creada, setCreada] = useState<Creada | null>(null);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const cargar = () => api.get<Listado>("/fichas-api").then(setDatos).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, []);

  const alternar = (a: string) => setNueva({ ...nueva, alcances: nueva.alcances.includes(a) ? nueva.alcances.filter((x) => x !== a) : [...nueva.alcances, a] });
  const crear = async () => {
    setOcupado(true); setError("");
    try {
      setCreada(await api.post<Creada>("/fichas-api", nueva));
      setNueva({ nombre: "", alcances: ["lectura"], dias: 90, codigo: "" });
      cargar();
    } catch (e) { setError((e as Error).message); } finally { setOcupado(false); }
  };
  const revocar = async (f: Ficha) => {
    if (!confirm(`La ficha «${f.nombre}» (${f.prefijo}…) dejará de funcionar al momento. ¿Continuar?`)) return;
    try { await api.del(`/fichas-api/${f.id}`); cargar(); } catch (e) { setError((e as Error).message); }
  };

  if (!datos) return <div className="p-6 text-sm text-ms-gray-60">{error || "Cargando…"}</div>;
  const superadmin = user?.role === "superadmin";
  const activas = datos.fichas.filter((f) => !f.revocada && f.vence && new Date(f.vence) > new Date()).length;
  return (
    <div className="p-6 space-y-4 max-w-4xl">
      <div>
        <h1 className="text-xl font-semibold text-ms-gray-130">Fichas de API</h1>
        <SectionHelp titulo="Qué son las fichas de API" items={[
          "Llaves para que un programa propio use la API del panel con la cabecera «Authorization: Bearer mqa_…». Cada ficha tiene un alcance (lectura y, si hace falta, las áreas donde puede hacer cambios) y una caducidad. Nunca sirve para la propia cuenta, los administradores, las fichas, el correo de otras personas ni el cortafuegos del servidor, ni para lo que en pantalla pide el segundo factor. Cada cambio hecho con una ficha queda en la auditoría.",
        ]} />
      </div>

      <div className={caja}>
        <h2 className="font-semibold">Fichas{superadmin ? " (de todos los administradores)" : ""}</h2>
        {datos.fichas.length === 0 && <p className="text-sm text-ms-gray-60">Ninguna.</p>}
        <table className="w-full text-sm">
          <tbody>
            {datos.fichas.map((f) => (
              <tr key={f.id} className={`border-b border-ms-gray-30 last:border-0 ${f.revocada ? "text-ms-gray-60" : ""}`}>
                <td className="py-2 pr-2">
                  <div className="font-medium">{f.nombre} <code className="text-xs">{f.prefijo}…</code></div>
                  <div className="text-xs text-ms-gray-90">{f.alcances.map((a) => (a === "lectura" ? "lectura" : datos.areas[a] || a)).join(", ")}{superadmin ? ` · de ${f.usuario}` : ""}</div>
                </td>
                <td className="py-2 pr-2 text-xs whitespace-nowrap">Vence {fecha(f.vence)}<br />Último uso {fecha(f.ultimo_uso)}</td>
                <td className="py-2 text-right">
                  {f.revocada ? <span className="text-xs">Revocada</span>
                    : <button onClick={() => revocar(f)} className="text-ms-red hover:underline text-xs">Revocar</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className={caja}>
        <h2 className="font-semibold">Nueva ficha ({activas} de {datos.maximo} activas)</h2>
        <input className={`${campo} w-full`} maxLength={80} placeholder="Nombre para reconocerla, p. ej. «Inventario de sitios»" value={nueva.nombre}
          onChange={(e) => setNueva({ ...nueva, nombre: e.target.value })} />
        <div className="space-y-1 text-sm">
          <label className="flex items-center gap-2"><input type="checkbox" checked={nueva.alcances.includes("lectura")} onChange={() => alternar("lectura")} /> Lectura (ver en todas las áreas de abajo)</label>
          <p className="text-xs text-ms-gray-90">Áreas donde además podrá hacer cambios:</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
            {Object.entries(datos.areas).map(([id, titulo]) => (
              <label key={id} className="flex items-center gap-2"><input type="checkbox" checked={nueva.alcances.includes(id)} onChange={() => alternar(id)} /> {titulo}</label>
            ))}
          </div>
        </div>
        <div className="flex flex-wrap gap-3 items-center text-sm">
          <label className="flex items-center gap-2">Caduca en
            <input type="number" min={1} max={datos.dias_maximos} className={`${campo} w-24`} value={nueva.dias}
              onChange={(e) => setNueva({ ...nueva, dias: Number(e.target.value) })} /> días
          </label>
          <label className="flex items-center gap-2">Código del segundo factor
            <input className={`${campo} w-28`} inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={nueva.codigo}
              onChange={(e) => setNueva({ ...nueva, codigo: e.target.value.replace(/\D/g, "") })} />
          </label>
        </div>
        {error && <p className="text-sm text-ms-red">{error}</p>}
        <button disabled={ocupado || !nueva.nombre.trim() || !nueva.alcances.length || nueva.codigo.length !== 6 || nueva.dias < 1 || nueva.dias > datos.dias_maximos}
          onClick={crear} className="px-4 py-2 bg-ms-blue text-white rounded text-sm disabled:opacity-50">Crear la ficha</button>
        <p className="text-xs text-ms-gray-60">Hace falta haber entrado con el segundo factor. La ficha se muestra una sola vez.</p>
      </div>

      {creada && <CredencialesModal titulo={`Ficha «${creada.nombre}»`} onCerrar={() => setCreada(null)}
        items={[{ etiqueta: "Ficha", valor: creada.ficha, secreto: true }, { etiqueta: "Vence", valor: fecha(creada.vence) }]}
        nota={creada.aviso} />}
    </div>
  );
}
