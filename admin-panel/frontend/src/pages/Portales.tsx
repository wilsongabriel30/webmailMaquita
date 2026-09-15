import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

// Portales por empresa: cada empresa entra al correo por su propio nombre de servidor
// (mail.<empresa>) y ve su logo, su nombre y sus colores. Lo que no defina se hereda de
// la marca general (Personalización).

interface Portal { host: string; activo: boolean; creado_en: string }
interface Empresa {
  dominio: string; activo: boolean; portales: Portal[];
  marca: Record<string, string>; logo_url?: string; favicon_url?: string;
}

const CAMPOS = [
  { key: "org_name", label: "Nombre visible", placeholder: "Ej: Maquita Turismo" },
  { key: "org_slogan", label: "Eslogan", placeholder: "Ej: Viajes con sentido" },
  { key: "org_website", label: "Sitio web", placeholder: "Ej: https://www.empresa.com" },
  { key: "org_email", label: "Email de contacto", placeholder: "Ej: info@empresa.com" },
  { key: "org_phone", label: "Teléfono", placeholder: "Ej: +593 2 123 4567" },
  { key: "footer_text", label: "Texto del pie", placeholder: "Ej: © 2026 Empresa" },
];
const COLORES = ["#0078d4", "#107c10", "#8661c5", "#d83b01", "#004e8c", "#c239b3"];

function Archivo({ empresa, tipo, url, onChange, onError }: {
  empresa: string; tipo: "logo" | "favicon"; url?: string;
  onChange: (url?: string) => void; onError: (m: string) => void;
}) {
  const ref = useRef<HTMLInputElement>(null);
  const subir = async (f: File) => {
    const fd = new FormData(); fd.append("file", f);
    const token = localStorage.getItem("admin_token");
    const res = await fetch(`/api/portales/marca/${empresa}/upload/${tipo}`, {
      method: "POST", headers: { Authorization: `Bearer ${token}` }, body: fd,
    });
    if (!res.ok) { const e = await res.json().catch(() => ({})); onError(e.detail || "Error al subir"); return; }
    const j = await res.json(); onChange(j.url + "?t=" + Date.now());
  };
  const borrar = async () => {
    if (!confirm(`¿Quitar el ${tipo} propio de ${empresa}? Volverá a mostrarse el de la marca general.`)) return;
    try { await api.del(`/portales/marca/${empresa}/file/${tipo}`); onChange(undefined); }
    catch (e: any) { onError(e.message); }
  };
  return (
    <div className="flex items-center gap-3">
      <div className="w-16 h-16 rounded border-2 border-dashed border-ms-gray-40 bg-ms-gray-10 flex items-center justify-center overflow-hidden shrink-0">
        {url ? <img src={url} alt={tipo} className="max-w-full max-h-full object-contain" />
             : <span className="text-[10px] text-ms-gray-60 text-center px-1">hereda el general</span>}
      </div>
      <div>
        <div className="text-xs font-medium text-ms-gray-130 mb-1">{tipo === "logo" ? "Logo" : "Icono (favicon)"}</div>
        <input ref={ref} type="file" className="hidden"
          accept={tipo === "favicon" ? "image/png,image/x-icon,image/svg+xml,.ico" : "image/png,image/jpeg,image/svg+xml,image/webp"}
          onChange={(e) => { if (e.target.files?.[0]) subir(e.target.files[0]); e.target.value = ""; }} />
        <div className="flex gap-2">
          <button onClick={() => ref.current?.click()} title="PNG, JPG, SVG o WebP, máximo 2 MB. Se aplica al instante en la pantalla de entrada de esta empresa."
            className="px-2.5 py-1 text-xs text-white rounded bg-ms-blue hover:bg-ms-blue-dark">{url ? "Cambiar" : "Subir"}</button>
          {url && <button onClick={borrar} className="px-2.5 py-1 text-xs text-ms-red border border-ms-red/30 rounded hover:bg-red-50">Quitar</button>}
        </div>
      </div>
    </div>
  );
}

function TarjetaEmpresa({ e, recargar, onError }: { e: Empresa; recargar: () => void; onError: (m: string) => void }) {
  const [marca, setMarca] = useState<Record<string, string>>(e.marca);
  const [nuevoHost, setNuevoHost] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [ok, setOk] = useState(false);
  const [abierta, setAbierta] = useState(e.portales.length > 0);
  useEffect(() => { setMarca(e.marca); }, [e]);

  const color = marca.primary_color || "";
  const cambios = JSON.stringify(marca) !== JSON.stringify(e.marca);

  const guardar = async () => {
    setGuardando(true); setOk(false);
    try {
      const cuerpo: Record<string, string> = {};
      for (const c of [...CAMPOS.map((x) => x.key), "primary_color"]) cuerpo[c] = marca[c] || "";
      await api.put(`/portales/marca/${e.dominio}`, cuerpo);
      setOk(true); setTimeout(() => setOk(false), 3000); recargar();
    } catch (err: any) { onError(err.message); } finally { setGuardando(false); }
  };
  const agregarHost = async () => {
    const h = nuevoHost.trim().toLowerCase(); if (!h) return;
    try { await api.post("/portales/hosts", { host: h, dominio: e.dominio }); setNuevoHost(""); recargar(); }
    catch (err: any) { onError(err.message); }
  };
  const alternar = async (p: Portal) => {
    try { await api.put(`/portales/hosts/${p.host}`, { activo: !p.activo }); recargar(); }
    catch (err: any) { onError(err.message); }
  };
  const quitarHost = async (p: Portal) => {
    if (!confirm(`¿Quitar el portal ${p.host}? Quien entre por ese nombre verá la marca general y podrá usar cualquier cuenta de la casa.`)) return;
    try { await api.del(`/portales/hosts/${p.host}`); recargar(); } catch (err: any) { onError(err.message); }
  };

  return (
    <div className="bg-white rounded border border-ms-gray-30">
      <button onClick={() => setAbierta(!abierta)} className="w-full flex items-center justify-between px-5 py-3 text-left">
        <div className="flex items-center gap-3">
          {e.logo_url ? <img src={e.logo_url} alt="" className="h-7 max-w-[80px] object-contain" />
                      : <span className="w-7 h-7 rounded bg-ms-gray-20 flex items-center justify-center text-[10px] text-ms-gray-60">sin logo</span>}
          <div>
            <div className="text-sm font-semibold text-ms-gray-130">{marca.org_name || e.dominio}</div>
            <div className="text-xs text-ms-gray-60">{e.dominio} · {e.portales.length === 0 ? "sin portal propio (entra por el portal padre)" : e.portales.map((p) => p.host).join(", ")}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {color && <span className="w-4 h-4 rounded-full border border-ms-gray-40" style={{ backgroundColor: color }} />}
          <span className="text-ms-gray-60 text-xs">{abierta ? "▲" : "▼"}</span>
        </div>
      </button>

      {abierta && (
        <div className="border-t border-ms-gray-30 px-5 py-4 space-y-5">
          {/* Portales (nombres de servidor) */}
          <div>
            <div className="text-xs font-semibold text-ms-gray-130 mb-2">Nombres de servidor por los que entra esta empresa</div>
            {e.portales.length === 0 && <div className="text-xs text-ms-gray-60 mb-2">Ninguno. Sus cuentas entran por el portal padre con la marca general.</div>}
            <div className="space-y-1.5 mb-2">
              {e.portales.map((p) => (
                <div key={p.host} className="flex items-center gap-3 text-sm">
                  <span className="font-mono text-ms-gray-130">{p.host}</span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${p.activo ? "bg-green-50 text-ms-green" : "bg-red-50 text-ms-red"}`}>{p.activo ? "Activo" : "Inactivo"}</span>
                  <button onClick={() => alternar(p)} className="text-xs text-ms-blue hover:underline" title="Un portal inactivo deja de restringir el dominio y de mostrar la marca propia, sin borrarlo.">{p.activo ? "Desactivar" : "Activar"}</button>
                  <button onClick={() => quitarHost(p)} className="text-xs text-ms-red hover:underline">Quitar</button>
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <input value={nuevoHost} onChange={(ev) => setNuevoHost(ev.target.value)} placeholder={`mail.${e.dominio}`}
                title="Nombre por el que la empresa abrirá su correo. Además hay que crear el registro DNS, el certificado y el bloque de nginx: ver la ayuda de esta pantalla."
                className="px-3 py-1.5 border border-ms-gray-40 rounded text-sm font-mono w-72 focus:outline-none focus:border-ms-blue" />
              <button onClick={agregarHost} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark">+ Agregar</button>
            </div>
          </div>

          {/* Logo e icono */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Archivo empresa={e.dominio} tipo="logo" url={e.logo_url} onChange={() => recargar()} onError={onError} />
            <Archivo empresa={e.dominio} tipo="favicon" url={e.favicon_url} onChange={() => recargar()} onError={onError} />
          </div>

          {/* Color */}
          <div>
            <div className="text-xs font-semibold text-ms-gray-130 mb-2">Color principal</div>
            <div className="flex items-center gap-3 flex-wrap">
              <input type="color" value={color || "#0078d4"} onChange={(ev) => setMarca({ ...marca, primary_color: ev.target.value })} className="w-10 h-9 rounded border border-ms-gray-40 cursor-pointer" />
              <input type="text" value={color} onChange={(ev) => setMarca({ ...marca, primary_color: ev.target.value })} placeholder="hereda el general" maxLength={7}
                className="w-36 px-3 py-1.5 border border-ms-gray-40 rounded text-sm font-mono focus:outline-none focus:border-ms-blue" />
              <div className="flex gap-1.5">
                {COLORES.map((c) => <button key={c} onClick={() => setMarca({ ...marca, primary_color: c })} className="w-6 h-6 rounded-full border-2" style={{ backgroundColor: c, borderColor: color === c ? "#323130" : "transparent" }} title={c} />)}
              </div>
              {color && <button onClick={() => setMarca({ ...marca, primary_color: "" })} className="text-xs text-ms-gray-60 hover:underline">Usar el general</button>}
            </div>
          </div>

          {/* Textos */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {CAMPOS.map((c) => (
              <div key={c.key}>
                <label className="block text-xs font-medium text-ms-gray-130 mb-1">{c.label}</label>
                <input value={marca[c.key] || ""} onChange={(ev) => setMarca({ ...marca, [c.key]: ev.target.value })} placeholder={c.placeholder}
                  title="Vacío = se usa el valor de la marca general."
                  className="w-full px-3 py-1.5 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
              </div>
            ))}
          </div>

          <div className="flex items-center gap-3">
            <button onClick={guardar} disabled={guardando || !cambios} className="px-4 py-2 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark disabled:opacity-50"
              title="Guarda nombre, textos y color de esta empresa. Los archivos (logo e icono) se guardan al subirlos.">
              {guardando ? "Guardando..." : "Guardar marca"}
            </button>
            {cambios && <span className="text-xs text-ms-gray-60 flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-400" />Cambios sin guardar</span>}
            {ok && <span className="text-xs text-ms-green">Guardado</span>}
          </div>
        </div>
      )}
    </div>
  );
}

export function Portales() {
  const [empresas, setEmpresas] = useState<Empresa[]>([]);
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(true);
  const load = () => api.get<Empresa[]>("/portales").then(setEmpresas).catch((e) => setError(e.message)).finally(() => setCargando(false));
  useEffect(() => { load(); }, []);

  return (
    <div className="p-6 max-w-4xl space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ms-gray-130">Portales por empresa</h1>
          <p className="text-sm text-ms-gray-60 mt-1">Cada empresa entra a su correo por su propio nombre de servidor y ve su logo, su nombre y sus colores. Lo que no se defina se hereda de Personalización.</p>
        </div>
        <SectionHelp titulo="Portales por empresa" items={[
          { titulo: "Para qué sirve", desc: "Que cada empresa de la casa (Turismo, Invertiagro...) perciba su propio servidor de correo aunque por debajo sea uno solo: su nombre de servidor, su logo, su nombre y su color en la pantalla de entrada." },
          { titulo: "Nombre de servidor", desc: "Al agregar mail.<empresa>, quien entre por ese nombre solo podrá usar cuentas de ese dominio y, si escribe solo su usuario, se le completa con ese dominio. El portal padre (mail.maquita.org) nunca restringe." },
          { titulo: "Lo que el panel NO hace", desc: "Publicar el nombre en internet. Para que mail.<empresa> funcione hacen falta además: (1) el registro DNS A apuntando a este servidor, (2) ampliar el certificado con ese nombre, (3) un bloque de nginx igual al de Turismo. Eso lo hace Tecnología." },
          { titulo: "Logo, icono y color", desc: "Se guardan por dominio y se aplican al instante (hasta 1 minuto si el portal es nuevo). Si se quitan, vuelve a mostrarse lo de la marca general." },
          { titulo: "Auditoría", desc: "Cada alta, baja, cambio de marca y subida de archivo queda en la auditoría del panel." },
        ]} />
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-ms-red/30 rounded text-ms-red text-sm flex items-center gap-2">
          {error}<button onClick={() => setError("")} className="ml-auto text-ms-red/60 hover:text-ms-red">&times;</button>
        </div>
      )}

      {cargando ? <div className="text-sm text-ms-gray-60">Cargando...</div> : (
        <div className="space-y-3">
          {empresas.map((e) => <div key={e.dominio}><TarjetaEmpresa e={e} recargar={load} onError={setError} /></div>)}
          {empresas.length === 0 && <div className="p-8 text-center text-ms-gray-60 text-sm">Sin dominios en el servidor</div>}
        </div>
      )}
    </div>
  );
}
