import { useState } from "react";

export interface RegistroDns { nombre: string; estado: string; ip?: string | null; zona?: string; detalle?: string }

/* Alta de un sitio: un dominio (ejemplo.org) o un subdominio de uno que ya está en el servidor (blog.ejemplo.org). */
export function NuevoSitioForm({ dominios, ocupado, onCancelar, onCrear }: {
  dominios: string[];
  ocupado: boolean;
  onCancelar: () => void;
  onCrear: (dominio: string, con_www: boolean) => void;
}) {
  const [tipo, setTipo] = useState<"dominio" | "subdominio">("dominio");
  const [dominio, setDominio] = useState("");
  const [sub, setSub] = useState("");
  const [padre, setPadre] = useState(dominios[0] || "");
  const [conWww, setConWww] = useState(true);
  const final = tipo === "dominio" ? dominio.trim().toLowerCase() : `${sub.trim().toLowerCase()}.${padre.trim().toLowerCase()}`;
  const valido = tipo === "dominio" ? !!dominio.trim() : !!sub.trim() && !!padre.trim();
  const campo = "px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue";

  return (
    <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-3">
      <div className="flex gap-4 text-sm">
        <label className="flex items-center gap-1.5"><input type="radio" checked={tipo === "dominio"} onChange={() => { setTipo("dominio"); setConWww(true); }} /> Dominio</label>
        <label className="flex items-center gap-1.5"><input type="radio" checked={tipo === "subdominio"} onChange={() => { setTipo("subdominio"); setConWww(false); }} /> Subdominio</label>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {tipo === "dominio" ? (
          <input placeholder="midominio.org" value={dominio} onChange={(e) => setDominio(e.target.value)} className={`${campo} w-72`} />
        ) : (
          <>
            <input placeholder="blog" value={sub} onChange={(e) => setSub(e.target.value)} className={`${campo} w-40`} />
            <span className="text-ms-gray-60">.</span>
            <input list="dominios-existentes" placeholder="midominio.org" value={padre} onChange={(e) => setPadre(e.target.value)} className={`${campo} w-64`} />
            <datalist id="dominios-existentes">{dominios.map((d) => <option key={d} value={d} />)}</datalist>
          </>
        )}
        <label className="text-sm text-ms-gray-90 flex items-center gap-1.5">
          <input type="checkbox" checked={conWww} onChange={(e) => setConWww(e.target.checked)} /> También www
        </label>
      </div>
      <p className="text-xs text-ms-gray-90">
        {tipo === "subdominio" ? <>Se creará <b>{valido ? final : "subdominio.dominio"}</b>, un sitio independiente con su propia aplicación, base de datos y FTP. </> : null}
        Si el dominio está en «Zonas DNS» de este servidor, el registro DNS se crea solo; si no, al terminar se indica a qué IP apuntarlo.
      </p>
      <div className="flex gap-2">
        <button onClick={() => onCrear(final, conWww)} disabled={ocupado || !valido} className="px-4 py-2 bg-ms-blue text-white rounded text-sm disabled:opacity-50">Crear</button>
        <button onClick={onCancelar} className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90">Cancelar</button>
      </div>
    </div>
  );
}

/* Qué pasó con el DNS de los nombres de un sitio. */
export function AvisoDns({ registros }: { registros: RegistroDns[] }) {
  if (!registros.length) return null;
  const externos = registros.filter((r) => r.estado === "externo");
  return (
    <ul className="text-xs space-y-0.5">
      {registros.map((r) => (
        <li key={r.nombre}>
          <b>{r.nombre}</b>:{" "}
          {r.estado === "creado" ? <span className="text-ms-green">registro A creado en la zona {r.zona}</span>
            : r.estado === "ya estaba" ? <span className="text-ms-gray-90">ya tenía registro en la zona {r.zona}</span>
            : r.estado === "externo" ? <span className="text-amber-700">su DNS no está en este servidor: cree en su proveedor un registro A hacia {r.ip || "la IP pública del servidor"}</span>
            : <span className="text-ms-red">no se pudo crear el registro ({r.detalle})</span>}
        </li>
      ))}
      {externos.length > 0 && !externos[0].ip && <li className="text-ms-gray-60">La IP pública del servidor se configura en «Zonas DNS → Ajustes».</li>}
    </ul>
  );
}
