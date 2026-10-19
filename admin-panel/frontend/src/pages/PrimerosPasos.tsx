import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { RedesSociales } from "./branding/RedesSociales";

type EstadoPaso = "hecho" | "omitido" | "pendiente";
interface Estado { pendiente: boolean; pasos: Record<string, EstadoPaso> }

const CAMPOS = [
  { clave: "org_description", etiqueta: "Descripción de la institución (página web, buscadores e IA)", ejemplo: "Trabajamos por … en …", largo: true },
  { clave: "org_slogan", etiqueta: "Lema", ejemplo: "Opcional" },
  { clave: "org_phone", etiqueta: "Teléfono", ejemplo: "+593 2 123 4567" },
  { clave: "org_email", etiqueta: "Correo de contacto público", ejemplo: "info@…", tipo: "email" },
  { clave: "org_website", etiqueta: "Sitio web", ejemplo: "https://…", tipo: "url" },
];

const SIGUIENTES = [
  { paso: "clave", titulo: "Cambiar la clave inicial", desc: "La del panel (botón de su usuario, arriba a la derecha → Mi cuenta) y la del primer buzón al entrar al webmail. Active también la verificación en dos pasos." },
  { paso: "dominio", titulo: "Dar de alta el dominio", desc: "Zona DNS, correo con firma DKIM, página «en construcción» y primer buzón, en un solo paso.", enlace: "/dominio-nuevo", textoEnlace: "Nuevo dominio" },
  { paso: "certificado", titulo: "Certificado del correo", desc: "Cuando el dominio ya apunte a este servidor (registrador y puertos del router), pida el certificado para que nadie vea avisos de seguridad.", enlace: "/dns", textoEnlace: "Zonas DNS" },
];

const campo = "w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue";

/* Primeros pasos de un servidor recién instalado: identidad (logo e información) y lo que queda por hacer.
   Cada paso se puede omitir y retomar luego desde Personalización o desde esta misma pantalla. */
export function PrimerosPasos() {
  const navegar = useNavigate();
  const [estado, setEstado] = useState<Estado | null>(null);
  const [datos, setDatos] = useState<Record<string, string>>({});
  const [logo, setLogo] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const archivo = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.get<Estado>("/primeros-pasos").then(setEstado).catch((e) => setMensaje(e.message));
    api.get<Record<string, string>>("/branding").then((d) => { setDatos(d); setLogo(d.logo_url || null); }).catch(() => {});
  }, []);

  const marcar = async (paso: string, valor: EstadoPaso) => setEstado(await api.put<Estado>("/primeros-pasos", { paso, estado: valor }));

  const subirLogo = async (f: File) => {
    const form = new FormData();
    form.append("file", f);
    setMensaje("Subiendo el logo…");
    const r = await fetch("/api/branding/upload/logo", { method: "POST", headers: { "X-Admin-Token": localStorage.getItem("admin_token") || "" }, body: form });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) { setMensaje(j.detail || "No se pudo subir el logo"); return; }
    setLogo(j.url + "?t=" + Date.now()); setMensaje("");
  };

  const guardarIdentidad = async () => {
    setOcupado(true); setMensaje("Guardando y aplicando en el correo, el Drive y las páginas…");
    try {
      const cambios: Record<string, string> = {};
      for (const c of [...CAMPOS.map((x) => x.clave), "primary_color", "org_social"]) if (datos[c] !== undefined) cambios[c] = datos[c];
      await api.put("/branding", cambios);
      await api.post("/branding/aplicar");
      await marcar("identidad", "hecho");
      setMensaje("Identidad aplicada en todo el servidor.");
    } catch (e) { setMensaje((e as Error).message); } finally { setOcupado(false); }
  };

  const terminar = async () => { await api.put("/primeros-pasos", { terminar: true }); navegar("/"); };

  if (!estado) return <div className="p-6 text-sm text-ms-gray-60">{mensaje || "Cargando…"}</div>;
  const identidad = estado.pasos.identidad || "pendiente";

  return (
    <div className="p-6 space-y-5 max-w-3xl">
      <div>
        <h1 className="text-xl font-semibold text-ms-gray-130">Primeros pasos</h1>
        <p className="text-sm text-ms-gray-90">El servidor de {datos.org_name || "la institución"} ya está instalado. Complete lo que quiera ahora; todo se puede omitir y hacer después.</p>
      </div>

      <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-4">
        <div className="flex items-center gap-2">
          <h2 className="font-semibold text-ms-gray-130">1. Logo e información de la institución</h2>
          {identidad !== "pendiente" && <span className="text-[11px] px-2 py-0.5 rounded bg-ms-gray-20 text-ms-gray-90">{identidad === "hecho" ? "Hecho" : "Omitido"}</span>}
        </div>
        <div className="flex items-center gap-4">
          <div className="w-24 h-24 rounded border-2 border-dashed border-ms-gray-40 flex items-center justify-center bg-ms-gray-10 overflow-hidden shrink-0">
            {logo ? <img src={logo} alt="Logo" className="max-w-full max-h-full object-contain" /> : <span className="text-xs text-ms-gray-60">Sin logo</span>}
          </div>
          <div className="text-sm space-y-2">
            <p className="text-xs text-ms-gray-90">PNG, JPG o WebP, hasta 2 MB; mejor cuadrado y con fondo transparente. De él salen los íconos de la app del correo en el celular.</p>
            <input ref={archivo} type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" className="hidden" onChange={(e) => e.target.files?.[0] && subirLogo(e.target.files[0])} />
            <button onClick={() => archivo.current?.click()} className="px-3 py-1.5 border border-ms-blue text-ms-blue rounded text-sm">{logo ? "Cambiar logo" : "Subir logo"}</button>
          </div>
        </div>
        <div className="grid sm:grid-cols-2 gap-3">
          {CAMPOS.map((c) => (
            <label key={c.clave} className={`text-xs text-ms-gray-90 ${c.largo ? "sm:col-span-2" : ""}`}>{c.etiqueta}
              {c.largo
                ? <textarea rows={2} maxLength={300} value={datos[c.clave] || ""} placeholder={c.ejemplo} onChange={(e) => setDatos({ ...datos, [c.clave]: e.target.value })} className={`${campo} mt-1`} />
                : <input type={c.tipo || "text"} value={datos[c.clave] || ""} placeholder={c.ejemplo} onChange={(e) => setDatos({ ...datos, [c.clave]: e.target.value })} className={`${campo} mt-1`} />}
            </label>
          ))}
          <label className="text-xs text-ms-gray-90">Color principal
            <input type="color" value={datos.primary_color || "#0078d4"} onChange={(e) => setDatos({ ...datos, primary_color: e.target.value })} className="mt-1 block h-9 w-20 border border-ms-gray-40 rounded" />
          </label>
        </div>
        <RedesSociales valor={datos.org_social || ""} onCambio={(json) => setDatos({ ...datos, org_social: json })} />
        <div className="flex flex-wrap gap-2">
          <button onClick={guardarIdentidad} disabled={ocupado} className="px-4 py-2 bg-ms-blue text-white rounded text-sm disabled:opacity-50">Guardar y aplicar en todo</button>
          <button onClick={() => marcar("identidad", "omitido")} disabled={ocupado} className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90">Omitir por ahora</button>
          <span className="text-xs text-ms-gray-60 self-center">Luego, en Personalización.</span>
        </div>
      </div>

      <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-3">
        <h2 className="font-semibold text-ms-gray-130">2. Lo que queda</h2>
        {SIGUIENTES.map((s) => {
          const e = estado.pasos[s.paso] || "pendiente";
          return (
            <div key={s.paso} className="flex gap-3 items-start border-t border-ms-gray-30 pt-3 first-of-type:border-0">
              <span className={`mt-1 w-3 h-3 rounded-full shrink-0 ${e === "hecho" ? "bg-green-500" : e === "omitido" ? "bg-ms-gray-40" : "bg-amber-400"}`} />
              <div className="flex-1 text-sm">
                <p className="font-medium">{s.titulo}{e !== "pendiente" && <span className="text-xs text-ms-gray-60 font-normal"> — {e === "hecho" ? "hecho" : "omitido"}</span>}</p>
                <p className="text-xs text-ms-gray-90">{s.desc}</p>
                <div className="flex gap-3 mt-1 text-xs">
                  {s.enlace && <Link to={s.enlace} className="text-ms-blue hover:underline">Ir a {s.textoEnlace}</Link>}
                  {e !== "hecho" && <button onClick={() => marcar(s.paso, "hecho")} className="text-ms-blue hover:underline">Marcar como hecho</button>}
                  {e === "pendiente" && <button onClick={() => marcar(s.paso, "omitido")} className="text-ms-gray-90 hover:underline">Omitir</button>}
                  {e !== "pendiente" && <button onClick={() => marcar(s.paso, "pendiente")} className="text-ms-gray-90 hover:underline">Volver a pendiente</button>}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {mensaje && <p className="text-sm text-ms-gray-90">{mensaje}</p>}
      <div className="flex gap-2">
        <button onClick={terminar} className="px-4 py-2 bg-ms-blue text-white rounded text-sm">Terminar</button>
        <button onClick={() => { try { sessionStorage.setItem("primeros_pasos_mas_tarde", "1"); } catch { /* sin almacenamiento */ } navegar("/"); }} className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90">Más tarde</button>
      </div>
      <p className="text-xs text-ms-gray-60">«Terminar» deja de mostrar esta pantalla al entrar; «Más tarde» la vuelve a mostrar la próxima vez (y, mientras tanto, el aviso de arriba la abre). La información de la institución se cambia cuando quiera en Personalización.</p>
    </div>
  );
}
