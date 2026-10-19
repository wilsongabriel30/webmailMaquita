import { useEffect, useState } from "react";
import { api } from "../../api/client";

interface Version { id: string; fecha: string; tipo: string; ruta: string; bytes: number }
interface Estado {
  vhost: string;
  nginx_propias: string;
  php: Record<string, string>;
  php_limites: Record<string, [number, number]>;
  archivos: string[];
  versiones: Version[];
  aviso?: string;
}

const PHP_NOMBRES: Record<string, string> = {
  memory_limit: "Memoria por proceso (MB)", upload_max_filesize: "Tamaño máximo de subida (MB)",
  post_max_size: "Tamaño máximo del formulario (MB)", max_execution_time: "Tiempo máximo de ejecución (s)",
  max_input_time: "Tiempo máximo de recepción (s)", max_input_vars: "Máximo de campos por formulario",
  display_errors: "Mostrar errores en pantalla (1 = sí, 0 = no)",
};
const TIPO: Record<string, string> = { nginx: "Reglas de nginx", php: "Ajustes de PHP", archivo: "Archivo" };
const editor = "w-full h-72 font-mono text-xs border border-ms-gray-40 rounded p-2 focus:outline-none focus:border-ms-blue";

/* Configuración avanzada del sitio: reglas propias de nginx, PHP, archivos de la aplicación y versiones anteriores. */
export function AvanzadoModal({ dominio, onCerrar }: { dominio: string; onCerrar: () => void }) {
  const [est, setEst] = useState<Estado | null>(null);
  const [pestana, setPestana] = useState<"nginx" | "php" | "archivo" | "versiones">("nginx");
  const [nginx, setNginx] = useState("");
  const [php, setPhp] = useState<Record<string, string>>({});
  const [ruta, setRuta] = useState("");
  const [archivo, setArchivo] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [verVhost, setVerVhost] = useState(false);

  const aplicar = (e: Estado) => { setEst(e); setNginx(e.nginx_propias); setPhp(e.php); };
  useEffect(() => { api.get<Estado>(`/sitios/${dominio}/avanzado`).then(aplicar).catch((e) => setError(e.message)); }, [dominio]);

  const hacer = async (texto: string, fn: () => Promise<Estado | void>) => {
    setOcupado(true); setError(""); setMensaje("");
    try {
      const e = await fn();
      if (e) { aplicar(e); setMensaje(e.aviso || texto); }
    } catch (e) { setError((e as Error).message); } finally { setOcupado(false); }
  };
  const abrir = (r: string) => hacer("", async () => {
    const d = await api.get<{ contenido: string; existe: boolean }>(`/sitios/${dominio}/avanzado/archivo?ruta=${encodeURIComponent(r)}`);
    setRuta(r); setArchivo(d.contenido);
    if (!d.existe) setMensaje("El archivo no existe: se creará al guardar.");
  });
  const copiar = async (contenido: string) => {
    try {
      const d = await api.post<{ contenido: string }>(`/sitios/${dominio}/avanzado/copia`, { contenido });
      await navigator.clipboard.writeText(d.contenido);
      setMensaje("Copiado sin contraseñas ni claves (aparecen como ***). Al pegar una propuesta, vuelva a poner los valores reales.");
    } catch (e) { setError((e as Error).message); }
  };
  const restaurar = (v: Version) => {
    if (!confirm(`¿Volver a la versión del ${v.fecha} (${TIPO[v.tipo]}${v.tipo === "archivo" ? ` ${v.ruta}` : ""})? Lo actual también se guarda antes.`)) return;
    hacer("Versión restaurada.", () => api.post<Estado>(`/sitios/${dominio}/avanzado/restaurar/${v.id}`));
  };
  const boton = (activo: boolean) => `px-3 py-1.5 text-sm rounded-t border-b-2 ${activo ? "border-ms-blue text-ms-blue" : "border-transparent text-ms-gray-90"}`;

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" role="dialog" aria-modal="true">
      <div className="bg-white rounded shadow-lg w-full max-w-5xl p-5 space-y-3 max-h-[92vh] overflow-y-auto">
        <div className="flex justify-between items-start">
          <div>
            <h2 className="text-lg font-semibold text-ms-gray-130">Configuración avanzada — {dominio}</h2>
            <p className="text-xs text-ms-gray-90">Para quien sabe lo que hace. Antes de cada cambio se guarda la versión anterior (pestaña «Versiones») y la configuración se comprueba: si nginx o PHP la rechazan, se deja la anterior.</p>
          </div>
          <button onClick={onCerrar} className="text-sm text-ms-gray-90 hover:underline">Cerrar</button>
        </div>
        <div className="flex gap-1 border-b border-ms-gray-30">
          <button className={boton(pestana === "nginx")} onClick={() => setPestana("nginx")}>nginx</button>
          <button className={boton(pestana === "php")} onClick={() => setPestana("php")}>PHP</button>
          <button className={boton(pestana === "archivo")} onClick={() => setPestana("archivo")}>Archivos</button>
          <button className={boton(pestana === "versiones")} onClick={() => setPestana("versiones")}>Versiones{est ? ` (${est.versiones.length})` : ""}</button>
        </div>
        {!est && !error && <p className="text-sm text-ms-gray-60">Cargando…</p>}

        {est && pestana === "nginx" && (
          <div className="space-y-2">
            <p className="text-xs text-ms-gray-90">Reglas propias: se incluyen dentro del <code>server {"{"}…{"}"}</code> del sitio, después de la configuración generada. No admiten <code>include</code> ni <code>root</code>/<code>alias</code> fuera de la carpeta del sitio; lo que ya está en el server (p. ej. <code>client_max_body_size</code>) va dentro de un <code>location</code>.</p>
            <textarea value={nginx} onChange={(e) => setNginx(e.target.value)} spellCheck={false} className={editor}
              placeholder={"# Ejemplo: caché larga para las imágenes de una carpeta\nlocation ^~ /imagenes/ {\n    expires 90d;\n}"} />
            <div className="flex flex-wrap gap-2">
              <button disabled={ocupado} onClick={() => hacer("Reglas guardadas y nginx recargado.", () => api.put<Estado>(`/sitios/${dominio}/avanzado/nginx`, { contenido: nginx }))} className="px-4 py-1.5 bg-ms-blue text-white rounded text-sm disabled:opacity-50">Comprobar y guardar</button>
              <button onClick={() => copiar(`# Configuración generada\n${est.vhost}\n# Reglas propias\n${nginx}`)} className="px-3 py-1.5 border border-ms-gray-40 rounded text-sm">Copiar sin contraseñas</button>
              <button onClick={() => setVerVhost(!verVhost)} className="text-sm text-ms-blue hover:underline">{verVhost ? "Ocultar" : "Ver"} la configuración generada</button>
            </div>
            {verVhost && <pre className="bg-ms-gray-20 border rounded p-2 text-[11px] max-h-72 overflow-auto">{est.vhost}</pre>}
          </div>
        )}

        {est && pestana === "php" && (
          <div className="space-y-2">
            <p className="text-xs text-ms-gray-90">Vacío = valor de serie. Se aplican solo a este sitio.</p>
            <div className="grid sm:grid-cols-2 gap-2">
              {(Object.entries(est.php_limites) as [string, [number, number]][]).map(([k, [min, max]]) => (
                <label key={k} className="text-xs text-ms-gray-90">{PHP_NOMBRES[k] || k} <span className="text-ms-gray-60">({min}–{max})</span>
                  <input value={(php[k] || "").replace(/M$/, "").replace(/^on$/, "1").replace(/^off$/, "0")} onChange={(e) => setPhp({ ...php, [k]: e.target.value.trim() })}
                    className="mt-0.5 w-full px-2 py-1.5 border border-ms-gray-40 rounded text-sm font-mono" />
                </label>
              ))}
            </div>
            <button disabled={ocupado} onClick={() => hacer("Ajustes de PHP aplicados.", () => api.put<Estado>(`/sitios/${dominio}/avanzado/php`, php))} className="px-4 py-1.5 bg-ms-blue text-white rounded text-sm disabled:opacity-50">Comprobar y guardar</button>
          </div>
        )}

        {est && pestana === "archivo" && (
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              {est.archivos.map((a) => <button key={a} onClick={() => abrir(a)} className="px-2 py-1 border border-ms-gray-30 rounded font-mono text-xs hover:border-ms-blue">{a}</button>)}
              <input placeholder="otra ruta dentro de publico/, p. ej. .user.ini" value={ruta} onChange={(e) => setRuta(e.target.value)} className="px-2 py-1 border border-ms-gray-40 rounded text-xs font-mono w-72" />
              <button onClick={() => abrir(ruta)} disabled={!ruta.trim()} className="text-xs text-ms-blue hover:underline disabled:opacity-50">Abrir</button>
            </div>
            {archivo !== null && (
              <>
                <p className="text-xs text-ms-gray-90">Editando <code>{ruta}</code>. Se guarda con su dueño y permisos; en los .php se comprueba la sintaxis.</p>
                <textarea value={archivo} onChange={(e) => setArchivo(e.target.value)} spellCheck={false} className={editor} />
                <div className="flex gap-2">
                  <button disabled={ocupado} onClick={() => hacer("Archivo guardado (la versión anterior quedó en «Versiones»).", () => api.put<Estado>(`/sitios/${dominio}/avanzado/archivo`, { ruta, contenido: archivo }))} className="px-4 py-1.5 bg-ms-blue text-white rounded text-sm disabled:opacity-50">Guardar</button>
                  <button onClick={() => copiar(archivo)} className="px-3 py-1.5 border border-ms-gray-40 rounded text-sm">Copiar sin contraseñas</button>
                </div>
              </>
            )}
          </div>
        )}

        {est && pestana === "versiones" && (
          <table className="w-full text-sm">
            <thead className="bg-ms-gray-20 text-xs text-ms-gray-90"><tr><th className="text-left px-2 py-1">Fecha</th><th className="text-left px-2 py-1">Qué</th><th className="text-right px-2 py-1"></th></tr></thead>
            <tbody className="divide-y divide-ms-gray-30">
              {est.versiones.map((v) => (
                <tr key={v.id}>
                  <td className="px-2 py-1 text-xs">{v.fecha}</td>
                  <td className="px-2 py-1 text-xs">{TIPO[v.tipo]}{v.tipo === "archivo" && <> <code>{v.ruta}</code></>} <span className="text-ms-gray-60">({v.bytes} bytes)</span></td>
                  <td className="px-2 py-1 text-right"><button onClick={() => restaurar(v)} disabled={ocupado} className="text-xs text-ms-blue hover:underline">Restaurar</button></td>
                </tr>
              ))}
              {est.versiones.length === 0 && <tr><td colSpan={3} className="px-2 py-3 text-center text-ms-gray-60 text-sm">Todavía no hay cambios guardados.</td></tr>}
            </tbody>
          </table>
        )}

        {(mensaje || error) && <p className={`text-sm ${error ? "text-ms-red" : "text-ms-green"}`}>{error || mensaje}</p>}
      </div>
    </div>
  );
}
