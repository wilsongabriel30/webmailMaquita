import { useEffect, useState } from "react";
import { api } from "../../api/client";

interface EstadoPhp { instaladas: string[]; disponibles: string[]; repositorio: boolean; en_uso: Record<string, number>; sitio?: string }
interface Extensiones { version: string; cargadas: string[]; ofrecidas: { id: string; nombre: string; instalada: boolean }[] }

const NOMBRES: Record<string, string> = {
  memory_limit: "Memoria por proceso (MB)", upload_max_filesize: "Tamaño máximo de subida (MB)",
  post_max_size: "Tamaño máximo del formulario (MB)", max_execution_time: "Tiempo máximo de ejecución (s)",
  max_input_time: "Tiempo máximo de recepción (s)", max_input_vars: "Máximo de campos por formulario",
  max_file_uploads: "Archivos por subida", "session.gc_maxlifetime": "Duración de la sesión inactiva (s)",
  default_socket_timeout: "Espera de conexiones salientes (s)", output_buffering: "Búfer de salida (bytes, 0 = sin búfer)",
  "opcache.revalidate_freq": "OPcache: revisar cambios cada (s)",
  display_errors: "Mostrar errores en pantalla", allow_url_fopen: "Abrir URL como archivos (allow_url_fopen)",
  short_open_tag: "Etiquetas cortas <?", "opcache.enable": "OPcache (caché de código)",
  permitir_ejecucion: "Permitir ejecutar programas (exec, shell_exec…)",
  "date.timezone": "Zona horaria", error_reporting: "Errores que se registran",
};
const NIVELES: Record<string, string> = { produccion: "Producción (sin avisos de obsolescencia)", todos: "Todos (desarrollo)", solo_errores: "Solo errores graves" };
const ZONAS = ["America/Guayaquil", "America/Bogota", "America/Lima", "America/Mexico_City", "America/Santiago", "Europe/Madrid", "UTC"];
const campo = "mt-0.5 w-full px-2 py-1.5 border border-ms-gray-40 rounded text-sm font-mono";

/* Pestaña PHP de «Avanzado»: versión del sitio, extensiones de esa versión y ajustes finos del pool. */
export function PhpPestana({ dominio, version, ajustes, limites, tipos, ocupado, onGuardar, onCambio }: {
  dominio: string;
  version: string;
  ajustes: Record<string, string>;
  limites: Record<string, [number, number]>;
  tipos: Record<string, string>;
  ocupado: boolean;
  onGuardar: (ajustes: Record<string, string>) => void;
  onCambio: () => void;
}) {
  const [php, setPhp] = useState<Record<string, string>>(ajustes);
  const [est, setEst] = useState<EstadoPhp | null>(null);
  const [ext, setExt] = useState<Extensiones | null>(null);
  const [nueva, setNueva] = useState("");
  const [destino, setDestino] = useState(version);
  const [trabajando, setTrabajando] = useState("");
  const [error, setError] = useState("");
  const [mensaje, setMensaje] = useState("");

  const cargar = () => {
    api.get<EstadoPhp>(`/sitios/${dominio}/php`).then(setEst).catch((e) => setError(e.message));
    api.get<Extensiones>(`/sitios/php/versiones/${version}/extensiones`).then(setExt).catch(() => setExt(null));
  };
  useEffect(() => { setPhp(ajustes); }, [ajustes]);
  useEffect(cargar, [dominio, version]);

  const hacer = async (texto: string, que: string, fn: () => Promise<unknown>) => {
    setTrabajando(que); setError(""); setMensaje("");
    try { await fn(); setMensaje(texto); cargar(); onCambio(); } catch (e) { setError((e as Error).message); } finally { setTrabajando(""); }
  };
  const valor = (k: string) => (php[k] || "").replace(/M$/, "").replace(/^on$/, "1").replace(/^off$/, "0");
  const poner = (k: string, v: string) => setPhp({ ...php, [k]: v.trim() });
  const ocupadoTodo = ocupado || !!trabajando;
  const instalables = (est?.disponibles || []).filter((v) => !est?.instaladas.includes(v));

  return (
    <div className="space-y-4">
      <section className="border border-ms-gray-30 rounded p-3 space-y-2">
        <h3 className="text-sm font-semibold text-ms-gray-130">Versión de PHP del sitio: {version}</h3>
        <div className="flex flex-wrap items-end gap-2 text-sm">
          <label className="text-xs text-ms-gray-90">Pasar a
            <select value={destino} onChange={(e) => setDestino(e.target.value)} className="ml-1 px-2 py-1.5 border border-ms-gray-40 rounded text-sm">
              {(est?.instaladas || [version]).map((v) => <option key={v} value={v}>PHP {v}{est?.en_uso[v] ? ` (${est.en_uso[v]} sitio${est.en_uso[v] > 1 ? "s" : ""})` : ""}</option>)}
            </select>
          </label>
          <button disabled={ocupadoTodo || destino === version} onClick={() => confirm(`¿Pasar ${dominio} a PHP ${destino}? Compruebe antes que su aplicación lo admite.`) && hacer(`El sitio usa ahora PHP ${destino}.`, "version", () => api.put(`/sitios/${dominio}/php`, { version: destino }))}
            className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm disabled:opacity-50">{trabajando === "version" ? "Cambiando…" : "Cambiar versión"}</button>
        </div>
        <div className="flex flex-wrap items-end gap-2 text-sm pt-1 border-t border-ms-gray-20">
          {!est ? <span className="text-xs text-ms-gray-60">Cargando versiones…</span> : !est.repositorio ? (
            <>
              <p className="text-xs text-ms-gray-90 w-full">Debian trae solo PHP {est.instaladas.join(", ")}. Para otras versiones (más nuevas o más antiguas) se activa el repositorio de Ondřej Surý, mantenedor de PHP en Debian (paquetes firmados).</p>
              <button disabled={ocupadoTodo} onClick={() => hacer("Repositorio activado: ya puede instalar otras versiones.", "repo", () => api.post("/sitios/php/repositorio"))}
                className="px-3 py-1.5 border border-ms-gray-40 rounded text-sm disabled:opacity-50">{trabajando === "repo" ? "Activando…" : "Activar más versiones de PHP"}</button>
            </>
          ) : (
            <>
              <label className="text-xs text-ms-gray-90">Instalar otra versión
                <select value={nueva} onChange={(e) => setNueva(e.target.value)} className="ml-1 px-2 py-1.5 border border-ms-gray-40 rounded text-sm">
                  <option value="">Elegir…</option>
                  {instalables.map((v) => <option key={v} value={v}>PHP {v}</option>)}
                </select>
              </label>
              <button disabled={ocupadoTodo || !nueva} onClick={() => hacer(`PHP ${nueva} instalado con las extensiones de serie.`, "instalar", () => api.post(`/sitios/php/versiones/${nueva}`))}
                className="px-3 py-1.5 border border-ms-gray-40 rounded text-sm disabled:opacity-50">{trabajando === "instalar" ? "Instalando (unos minutos)…" : "Instalar"}</button>
              {instalables.length === 0 && <span className="text-xs text-ms-gray-60">Todas las versiones disponibles están instaladas.</span>}
            </>
          )}
        </div>
      </section>

      <section className="border border-ms-gray-30 rounded p-3 space-y-2">
        <h3 className="text-sm font-semibold text-ms-gray-130">Extensiones de PHP {version}</h3>
        <p className="text-xs text-ms-gray-90">Se instalan para toda la versión: las cargan todos los sitios que usan PHP {version}.</p>
        {!ext ? <p className="text-xs text-ms-gray-60">Cargando…</p> : (
          <>
            <div className="flex flex-wrap gap-1">{ext.cargadas.map((m) => <span key={m} className="px-1.5 py-0.5 bg-ms-gray-20 rounded text-[11px] font-mono">{m}</span>)}</div>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-1 max-h-56 overflow-y-auto pr-1">
              {ext.ofrecidas.map((e) => (
                <div key={e.id} className="flex items-center justify-between gap-2 text-xs border border-ms-gray-20 rounded px-2 py-1">
                  <span><span className="font-mono">{e.id}</span>{e.nombre !== e.id ? ` — ${e.nombre}` : ""}</span>
                  <button disabled={ocupadoTodo} onClick={() => hacer(`Extensión ${e.id} ${e.instalada ? "quitada" : "instalada"}.`, e.id, () => api.post(`/sitios/php/versiones/${version}/extensiones/${e.id}`, { accion: e.instalada ? "quitar" : "instalar" }))}
                    className={`shrink-0 hover:underline disabled:opacity-50 ${e.instalada ? "text-ms-red" : "text-ms-blue"}`}>{trabajando === e.id ? "…" : e.instalada ? "Quitar" : "Instalar"}</button>
                </div>
              ))}
            </div>
          </>
        )}
      </section>

      <section className="border border-ms-gray-30 rounded p-3 space-y-2">
        <h3 className="text-sm font-semibold text-ms-gray-130">Ajustes de este sitio</h3>
        <p className="text-xs text-ms-gray-90">Vacío = valor de serie. Se comprueban con PHP-FPM antes de aplicarse.</p>
        <div className="grid sm:grid-cols-2 gap-2">
          {Object.keys(tipos).map((k) => (
            <label key={k} className="text-xs text-ms-gray-90">{NOMBRES[k] || k}
              {limites[k] && tipos[k] !== "b" && <span className="text-ms-gray-60"> ({limites[k][0]}–{limites[k][1]})</span>}
              {tipos[k] === "b" ? (
                <select value={valor(k)} onChange={(e) => poner(k, e.target.value)} className={campo}>
                  <option value="">De serie</option><option value="1">Sí</option><option value="0">No</option>
                </select>
              ) : tipos[k] === "o" ? (
                <select value={php[k] || ""} onChange={(e) => poner(k, e.target.value)} className={campo}>
                  <option value="">De serie</option>
                  {Object.entries(NIVELES).map(([v, t]) => <option key={v} value={v}>{t}</option>)}
                </select>
              ) : tipos[k] === "z" ? (
                <><input list="zonas-php" value={php[k] || ""} onChange={(e) => poner(k, e.target.value)} placeholder="America/Guayaquil" className={campo} />
                  <datalist id="zonas-php">{ZONAS.map((z) => <option key={z} value={z} />)}</datalist></>
              ) : (
                <input value={valor(k)} onChange={(e) => poner(k, e.target.value)} className={campo} />
              )}
              {k === "permitir_ejecucion" && valor(k) === "1" && <span className="block text-[11px] text-amber-700 mt-0.5">Solo si la aplicación lo necesita: los programas que lance corren con el usuario del sitio, pero fuera del límite de carpetas de PHP.</span>}
            </label>
          ))}
        </div>
        <button disabled={ocupadoTodo} onClick={() => onGuardar(php)} className="px-4 py-1.5 bg-ms-blue text-white rounded text-sm disabled:opacity-50">Comprobar y guardar</button>
      </section>

      {(mensaje || error) && <p className={`text-sm ${error ? "text-ms-red" : "text-ms-green"}`}>{error || mensaje}</p>}
    </div>
  );
}
