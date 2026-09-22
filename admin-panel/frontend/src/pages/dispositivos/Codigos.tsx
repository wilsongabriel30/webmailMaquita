import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { fechaHora } from "./tipos";
import { BuscadorBuzon } from "./BuscadorBuzon";

// Códigos de enrolamiento. Desde el 22/09/2026 solo los crea Tecnología aquí y pueden asignarse a una
// persona: ella lo ve en solo lectura en su Configuración del correo y la app lo recibe para activar con
// un toque. Los códigos asignados se pueden volver a ver (quedan cifrados mientras estén vigentes); los
// que no tienen persona se muestran una sola vez.

interface Uso { id: number; nombre?: string; modelo?: string; fabricante?: string; enrolado_en: string }
interface Codigo { id: number; prefijo: string; etiqueta: string; modo: string; usos_max: number; usos: number; creado_por: string; creado_en: string; caduca_en?: string; revocado_en?: string; custodio_email?: string; autoservicio?: boolean; recuperable: boolean; usado_por: Uso[] }
interface Nuevo { codigo: string; caduca_en: string; custodio_email?: string; recuperable: boolean; aviso?: string | null }

export function Codigos() {
  const [lista, setLista] = useState<Codigo[]>([]);
  const [cifrado, setCifrado] = useState(true);
  const [f, setF] = useState({ etiqueta: "", modo: "limitado", usos_max: 1, horas_validez: 72, custodio_email: "" });
  const [nuevo, setNuevo] = useState<Nuevo | null>(null);
  const [visto, setVisto] = useState<{ id: number; codigo: string } | null>(null);
  const [error, setError] = useState("");

  const cargar = () => api.get<{ codigos: Codigo[]; cifrado_disponible: boolean }>("/dispositivos/codigos")
    .then((r) => { setLista(r.codigos); setCifrado(r.cifrado_disponible); }).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, []);

  const crear = async () => {
    try { setError(""); setVisto(null); setNuevo(await api.post("/dispositivos/codigos", f)); cargar(); }
    catch (e: any) { setError(e.message); }
  };
  const revocar = async (id: number) => { if (confirm("¿Anular este código? Los equipos ya enrolados con él no se ven afectados.")) { await api.del(`/dispositivos/codigos/${id}`); cargar(); } };
  const ver = async (id: number) => {
    try { setError(""); const r = await api.get<{ codigo: string }>(`/dispositivos/codigos/${id}/ver`); setVisto({ id, codigo: r.codigo }); }
    catch (e: any) { setError(e.message); }
  };
  const estado = (c: Codigo) => c.revocado_en ? "anulado" : c.usos >= c.usos_max ? "usado" : c.caduca_en && new Date(c.caduca_en) < new Date() ? "caducado" : "vigente";
  const equipo = (u: Uso) => u.nombre || `${u.fabricante || ""} ${u.modelo || "equipo"}`.trim();

  return (
    <div className="space-y-4">
      {error && <div className="text-sm px-3 py-2 rounded bg-red-50 text-red-700">{error}</div>}
      {!cifrado && <div className="text-sm px-3 py-2 rounded bg-amber-50 text-amber-800">Falta la clave <code>DISP_CODIGO_CLAVE</code> en el <code>.env</code> del panel y del correo: los códigos asignados no quedarán recuperables ni los verá la persona en su Configuración.</div>}
      <div className="bg-white rounded-lg border border-ms-gray-30 p-4 space-y-3">
        <h3 className="text-sm font-semibold">Nuevo código de enrolamiento</h3>
        <p className="text-xs text-ms-gray-60">Es la contraseña de instalación: sin un código vigente, la app no activa la gestión del equipo. Solo Tecnología los crea. Si lo asigna a una persona, ella lo verá en su Configuración del correo («Mi teléfono») y la app podrá activarlo con un toque; esa persona queda como custodia del equipo.</p>
        <div className="flex flex-wrap items-end gap-3 text-sm">
          <label className="text-xs">Para quién (buzón)<BuscadorBuzon value={f.custodio_email} onChange={(v) => setF({ ...f, custodio_email: v })} /></label>
          <label className="text-xs">Para qué es<input value={f.etiqueta} onChange={(e) => setF({ ...f, etiqueta: e.target.value })} placeholder="Ej: Samsung A16 Ventas (compra sep-2026)" className="mt-1 block w-64 px-2.5 py-1.5 text-sm border border-ms-gray-40 rounded" /></label>
          <label className="text-xs">Tipo<select value={f.modo} onChange={(e) => setF({ ...f, modo: e.target.value })} className="mt-1 block px-2.5 py-1.5 text-sm border border-ms-gray-40 rounded">
            <option value="limitado">Teléfono ya en uso (modo limitado)</option><option value="propietario">Equipo restaurado de fábrica (control completo)</option></select></label>
          <label className="text-xs">Equipos<input type="number" min={1} max={500} value={f.usos_max} onChange={(e) => setF({ ...f, usos_max: Number(e.target.value) })} className="mt-1 block w-20 px-2.5 py-1.5 text-sm border border-ms-gray-40 rounded" /></label>
          <label className="text-xs">Válido (horas)<input type="number" min={1} max={2160} value={f.horas_validez} onChange={(e) => setF({ ...f, horas_validez: Number(e.target.value) })} className="mt-1 block w-24 px-2.5 py-1.5 text-sm border border-ms-gray-40 rounded" /></label>
          <button onClick={crear} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark">Crear código</button>
        </div>
        {nuevo && <div className="bg-amber-50 border border-amber-200 rounded p-3">
          <div className="text-xs text-amber-800 mb-1">
            {nuevo.recuperable ? <>Asignado a <strong>{nuevo.custodio_email}</strong>: lo verá en su Configuración del correo y podrá volver a consultarse aquí con «Ver».</> : <>Cópielo ahora: no se volverá a mostrar.</>} Caduca {fechaHora(nuevo.caduca_en)}.
          </div>
          <div className="flex items-center gap-3"><code className="text-2xl font-mono tracking-widest">{nuevo.codigo}</code>
            <button onClick={() => navigator.clipboard.writeText(nuevo.codigo)} className="text-xs text-ms-blue hover:underline">Copiar</button></div>
          {nuevo.aviso && <div className="text-xs text-red-700 mt-1">{nuevo.aviso}</div>}
        </div>}
      </div>
      <div className="bg-white rounded-lg border border-ms-gray-30 overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="bg-ms-gray-10">{["Código", "Asignado a", "Para qué", "Tipo", "Usos", "Usado desde", "Creado", "Caduca", "Estado", ""].map((h) => <th key={h} className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">{h}</th>)}</tr></thead>
          <tbody>
            {lista.map((c) => <tr key={c.id} className="border-t border-ms-gray-20">
              <td className="px-4 py-2.5 font-mono">{visto?.id === c.id ? <span className="text-ms-gray-130">{visto.codigo} <button onClick={() => navigator.clipboard.writeText(visto.codigo)} className="text-xs font-sans text-ms-blue hover:underline">Copiar</button></span> : `${c.prefijo}-••••-••••`}</td>
              <td className="px-4 py-2.5 text-xs">{c.custodio_email || <span className="text-ms-gray-60">—</span>}{c.autoservicio && <div className="text-ms-gray-60">(autoservicio, anterior)</div>}</td>
              <td className="px-4 py-2.5">{c.etiqueta || "—"}</td>
              <td className="px-4 py-2.5 text-xs">{c.modo === "propietario" ? "Control completo" : "Limitado"}</td><td className="px-4 py-2.5">{c.usos} / {c.usos_max}</td>
              <td className="px-4 py-2.5 text-xs">{c.usado_por.length ? c.usado_por.map((u) => <div key={u.id}>{equipo(u)} <span className="text-ms-gray-60">· {fechaHora(u.enrolado_en)}</span></div>) : "—"}</td>
              <td className="px-4 py-2.5 text-xs">{fechaHora(c.creado_en)}<div className="text-ms-gray-60">{c.creado_por}</div></td>
              <td className="px-4 py-2.5 text-xs">{fechaHora(c.caduca_en)}</td><td className="px-4 py-2.5 text-xs">{estado(c)}</td>
              <td className="px-4 py-2.5 text-right whitespace-nowrap">
                {c.recuperable && visto?.id !== c.id && <button onClick={() => ver(c.id)} className="text-xs text-ms-blue hover:underline mr-3" title="Queda en la auditoría">Ver</button>}
                {estado(c) === "vigente" && <button onClick={() => revocar(c.id)} className="text-xs text-ms-red hover:underline">Anular</button>}
              </td>
            </tr>)}
            {!lista.length && <tr><td colSpan={10} className="px-4 py-6 text-center text-ms-gray-60">Sin códigos todavía.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
