import { useCallback, useEffect, useState } from "react";
import { api } from "../../api/client";
import { AutenticacionGit } from "./AutenticacionGit";
import { campo } from "./datosComun";

interface Version { id: string; commit: string | null; fecha: string; mensaje?: string }
interface Despliegue { id: string; inicio: string; origen: string; estado: string; commit?: string; mensaje?: string; error?: string; segundos?: number }
interface Estado {
  configurado: boolean; compatible: boolean; motivo: string | null;
  repo?: string; rama?: string; carpeta?: string; raiz_web?: string; exclusiones?: string[]; exclusiones_fijas?: string[];
  actual?: string; gancho?: boolean; gancho_ruta?: string; clave_publica?: string | null; en_curso?: boolean;
  versiones?: Version[]; despliegues?: Despliegue[];
}

const ORIGEN: Record<string, string> = { panel: "Panel", gancho: "Push", volver: "Vuelta atrás" };
const corto = (c?: string | null) => (c ? c.slice(0, 8) : "—");

/* Despliegue desde git del sitio PHP: configuración, clave de despliegue, gancho, registro y versiones guardadas. */
export function GitPestana({ dominio }: { dominio: string }) {
  const [e, setE] = useState<Estado | null>(null);
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");
  const [secreto, setSecreto] = useState<{ url: string; secreto: string } | null>(null);
  const [form, setForm] = useState({ repo: "", rama: "main", carpeta: "", raiz_web: "", exclusiones: "" });
  const ruta = `/sitios/${dominio}/git`;

  const cargar = useCallback(async () => {
    const d = await api.get<Estado>(ruta);
    setE(d);
    if (d.configurado) setForm({ repo: d.repo || "", rama: d.rama || "main", carpeta: d.carpeta || "", raiz_web: d.raiz_web || "", exclusiones: (d.exclusiones || []).join("\n") });
    return d;
  }, [ruta]);
  useEffect(() => { cargar().catch((x) => setError(x.message)); }, [cargar]);
  useEffect(() => {
    if (!e?.en_curso) return;
    const t = setInterval(() => { cargar().catch(() => undefined); }, 3000);
    return () => clearInterval(t);
  }, [e?.en_curso, cargar]);

  const hacer = async (fn: () => Promise<unknown>, texto: string) => {
    setError(""); setAviso("");
    try { await fn(); setAviso(texto); await cargar(); } catch (x) { setError((x as Error).message); }
  };
  if (!e) return <p className="text-sm text-ms-gray-60">{error || "Cargando…"}</p>;
  if (!e.configurado && !e.compatible) return <p className="text-sm text-ms-gray-60">El despliegue desde git no está disponible para este sitio: {e.motivo}.</p>;
  const guardar = () => hacer(() => api.put(ruta, { ...form, exclusiones: form.exclusiones.split("\n").map((x) => x.trim()).filter(Boolean) }), "Configuración guardada.");
  const activarGancho = async () => {
    setError("");
    try {
      const r = await api.post<{ secreto: string; gancho_ruta: string }>(`${ruta}/gancho`, { accion: "activar" });
      setSecreto({ url: `https://${window.location.hostname}${r.gancho_ruta}`, secreto: r.secreto });
      await cargar();
    } catch (x) { setError((x as Error).message); }
  };
  const boton = "px-3 py-1.5 text-sm rounded border border-ms-gray-40 hover:bg-ms-gray-10 disabled:opacity-50";
  return (
    <div className="space-y-3 text-sm">
      {error && <p className="text-ms-red">{error}</p>}
      {aviso && <p className="text-ms-green">{aviso}</p>}
      <div className="grid sm:grid-cols-2 gap-2">
        <label className="space-y-1"><span className="text-xs text-ms-gray-90">Repositorio (ssh o https)</span>
          <input className={`${campo} w-full`} value={form.repo} onChange={(x) => setForm({ ...form, repo: x.target.value })} placeholder="git@servidor:organizacion/sitio.git" /></label>
        <label className="space-y-1"><span className="text-xs text-ms-gray-90">Rama</span>
          <input className={`${campo} w-full`} value={form.rama} onChange={(x) => setForm({ ...form, rama: x.target.value })} /></label>
        <label className="space-y-1"><span className="text-xs text-ms-gray-90">Carpeta del repositorio que se publica</span>
          <input className={`${campo} w-full`} value={form.carpeta} onChange={(x) => setForm({ ...form, carpeta: x.target.value })} placeholder="vacío = todo" /></label>
        <label className="space-y-1"><span className="text-xs text-ms-gray-90">Carpeta que sirve la web</span>
          <input className={`${campo} w-full`} value={form.raiz_web} onChange={(x) => setForm({ ...form, raiz_web: x.target.value })} placeholder="p. ej. public" /></label>
      </div>
      <label className="block space-y-1"><span className="text-xs text-ms-gray-90">No se tocan (uno por línea; siempre: {(e.exclusiones_fijas || [".well-known"]).join(", ")})</span>
        <textarea className={`${campo} w-full`} rows={3} value={form.exclusiones} onChange={(x) => setForm({ ...form, exclusiones: x.target.value })} placeholder={"wp-content/uploads\nstorage"} /></label>
      <div className="flex flex-wrap gap-2">
        <button className={boton} onClick={guardar}>{e.configurado ? "Guardar cambios" : "Configurar"}</button>
        {e.configurado && <button className={`${boton} bg-ms-blue text-white`} disabled={e.en_curso} onClick={() => hacer(() => api.post(`${ruta}/desplegar`), "Despliegue iniciado.")}>{e.en_curso ? "Desplegando…" : "Desplegar ahora"}</button>}
        {e.configurado && <button className={boton} onClick={activarGancho}>{e.gancho ? "Cambiar el secreto del gancho" : "Activar el gancho"}</button>}
        {e.configurado && e.gancho && <button className={boton} onClick={() => hacer(() => api.post(`${ruta}/gancho`, { accion: "desactivar" }), "Gancho desactivado.")}>Desactivar el gancho</button>}
      </div>
      {secreto && (
        <div className="bg-yellow-50 border border-yellow-200 rounded p-2 text-xs space-y-1">
          <p><b>Webhook:</b> <code>{secreto.url}</code> · tipo application/json · solo push</p>
          <p><b>Secreto</b> (no se vuelve a mostrar): <code className="select-all">{secreto.secreto}</code></p>
        </div>
      )}
      <AutenticacionGit dominio={dominio} repo={form.repo} />

      {(e.versiones || []).length > 0 && (
        <div><b>Versiones guardadas</b>
          <ul className="mt-1 space-y-1">{[...(e.versiones || [])].reverse().map((v) => (
            <li key={v.id} className="flex gap-2 items-center"><span>{v.fecha}</span><code>{corto(v.commit)}</code><span className="text-ms-gray-90">{v.mensaje}</span>
              {v.id === e.actual ? <span className="text-ms-green text-xs">publicada</span>
                : <button className="text-ms-blue text-xs hover:underline" onClick={() => hacer(() => api.post(`${ruta}/volver`, { version: v.id }), "Versión publicada.")}>Volver a esta</button>}</li>
          ))}</ul>
        </div>
      )}
      {(e.despliegues || []).length > 0 && (
        <table className="w-full text-xs"><thead><tr className="text-left text-ms-gray-90"><th>Inicio</th><th>Origen</th><th>Resultado</th><th>Commit</th><th>Duración</th></tr></thead>
          <tbody>{(e.despliegues || []).map((d) => (
            <tr key={d.id + d.inicio} className="border-t border-ms-gray-30 align-top"><td>{d.inicio}</td><td>{ORIGEN[d.origen] || d.origen}</td>
              <td className={d.estado === "ok" ? "text-ms-green" : d.estado === "error" ? "text-ms-red" : ""}>{d.estado === "ok" ? "Bien" : d.estado === "error" ? `Falló: ${d.error || ""}` : "En curso"}</td>
              <td><code>{corto(d.commit)}</code> {d.mensaje}</td><td>{d.segundos != null ? `${d.segundos} s` : ""}</td></tr>
          ))}</tbody></table>
      )}
      {e.configurado && <button className="text-ms-red text-xs hover:underline" onClick={() => { if (window.confirm(`¿Quitar el despliegue desde git de ${dominio}? Lo publicado se queda.`)) hacer(() => api.del(ruta, { confirmacion: dominio }), "Despliegue desde git quitado."); }}>Quitar el despliegue desde git</button>}
      <p className="text-[11px] text-ms-gray-60">Cada despliegue clona la rama con el usuario del sitio y la publica con rsync (lo que ya no está en el repositorio se borra, salvo lo indicado). Antes del primero se hace una copia del sitio. Se guardan las 3 últimas versiones.</p>
    </div>
  );
}
