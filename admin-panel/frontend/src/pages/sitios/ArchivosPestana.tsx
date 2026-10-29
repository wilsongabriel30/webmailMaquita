import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { ArchivosPapelera } from "./ArchivosPapelera";
import { abrirEnlace, campo, tamano } from "./datosComun";

interface Entrada { nombre: string; tipo: "carpeta" | "archivo" | "enlace" | "otro"; bytes: number | null; modificado: string; permisos: string; fuera?: boolean; apunta_a?: string | null }
interface Listado { ruta: string; entradas: Entrada[]; recortado: boolean }

const MODOS = [
  { modo: "640", texto: "640 — de serie (la web lo lee)" }, { modo: "750", texto: "750 — carpeta de serie" },
  { modo: "644", texto: "644 — lectura para todos" }, { modo: "755", texto: "755 — carpeta o script ejecutable" },
  { modo: "600", texto: "600 — solo el dueño (la web no lo lee)" }, { modo: "700", texto: "700 — carpeta solo del dueño" },
];
const COMPRIMIDO = /\.(zip|tar\.gz|tgz|tar|rar|7z)$/i;
const unir = (carpeta: string, nombre: string) => (carpeta === "." ? nombre : `${carpeta}/${nombre}`);

/* Administrador de archivos de la carpeta pública del sitio. Todo se hace con el usuario del sitio, nunca como root;
   lo borrado va a la papelera del sitio (30 días). */
export function ArchivosPestana({ dominio }: { dominio: string }) {
  const [ruta, setRuta] = useState(".");
  const [listado, setListado] = useState<Listado | null>(null);
  const [elegidos, setElegidos] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [progreso, setProgreso] = useState<string | null>(null);
  const [reemplazar, setReemplazar] = useState(false);
  const [papelera, setPapelera] = useState(false);

  const cargar = (r = ruta) => api.get<Listado>(`/sitios/${dominio}/archivos?ruta=${encodeURIComponent(r)}`)
    .then((l) => { setListado(l); setRuta(l.ruta); setElegidos([]); })
    .catch((e) => setError(e.message));
  useEffect(() => { cargar("."); }, [dominio]);

  const hacer = async (texto: string, fn: () => Promise<unknown>) => {
    setOcupado(true); setError(""); setMensaje("");
    try { await fn(); setMensaje(texto); await cargar(); }
    catch (e) { setError((e as Error).message); } finally { setOcupado(false); }
  };
  const post = (camino: string, cuerpo: unknown) => api.post(`/sitios/${dominio}/${camino}`, cuerpo);

  const subirUno = (archivo: File) => new Promise<void>((resolver, fallar) => {
    const datos = new FormData();
    datos.append("archivo", archivo);
    datos.append("carpeta", ruta);
    datos.append("reemplazar", reemplazar ? "true" : "false");
    // XMLHttpRequest y no fetch: así se ve el avance de la subida.
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/sitios/${dominio}/archivos/subir`);
    const token = localStorage.getItem("admin_token");
    if (token) xhr.setRequestHeader("X-Admin-Token", token);
    xhr.upload.onprogress = (e) => e.lengthComputable && setProgreso(`${archivo.name}: ${Math.round((e.loaded / e.total) * 100)} %`);
    xhr.onload = () => {
      let cuerpo: { detail?: string } = {};
      try { cuerpo = JSON.parse(xhr.responseText); } catch { /* respuesta vacía */ }
      if (xhr.status >= 200 && xhr.status < 300) resolver();
      else fallar(new Error(`${archivo.name}: ${cuerpo.detail || (xhr.status === 413 ? "supera 512 MB" : `error ${xhr.status}`)}`));
    };
    xhr.onerror = () => fallar(new Error(`${archivo.name}: se cortó la conexión`));
    xhr.send(datos);
  });
  const subir = (archivos: FileList | null) => archivos?.length && hacer(`${archivos.length === 1 ? "Archivo subido" : `${archivos.length} archivos subidos`}.`, async () => {
    try { for (const a of Array.from(archivos)) await subirUno(a); } finally { setProgreso(null); }
  });

  const nuevaCarpeta = () => {
    const nombre = prompt("Nombre de la carpeta nueva:")?.trim();
    if (nombre) hacer("Carpeta creada.", () => post("archivos/carpeta", { ruta: unir(ruta, nombre) }));
  };
  const renombrar = (e: Entrada) => {
    const nombre = prompt(`Nuevo nombre para «${e.nombre}»:`, e.nombre)?.trim();
    if (nombre && nombre !== e.nombre) hacer("Renombrado.", () => post("archivos/mover", { origen: unir(ruta, e.nombre), destino: unir(ruta, nombre) }));
  };
  const moverOCopiar = (e: Entrada, accion: "mover" | "copiar") => {
    const destino = prompt(`Ruta de destino (desde la carpeta pública), p. ej. «css/${e.nombre}»:`, unir(ruta, accion === "copiar" ? `copia-${e.nombre}` : e.nombre))?.trim();
    if (destino) hacer(accion === "mover" ? "Movido." : "Copiado.", () => post(`archivos/${accion}`, { origen: unir(ruta, e.nombre), destino }));
  };
  const descomprimir = (e: Entrada) => {
    const destino = prompt("Descomprimir en la carpeta (desde la carpeta pública; «.» es la raíz). Los archivos que ya existan se sobrescriben:", ruta)?.trim();
    if (destino) hacer("Descomprimido.", () => post("archivos/descomprimir", { origen: unir(ruta, e.nombre), destino }));
  };
  const comprimir = () => {
    const destino = prompt("Nombre del .zip (se crea en esta carpeta):", "archivos.zip")?.trim();
    if (destino) hacer("Comprimido.", () => post("archivos-comprimir", { rutas: elegidos.map((n) => unir(ruta, n)), destino: unir(ruta, destino) }));
  };
  const borrar = (nombres: string[]) => confirm(`¿Llevar a la papelera ${nombres.length === 1 ? `«${nombres[0]}»` : `${nombres.length} elementos`}? Se pueden recuperar durante 30 días.`)
    && hacer("Llevado a la papelera.", async () => { for (const n of nombres) await post("archivos-borrar", { ruta: unir(ruta, n) }); });
  const permisos = (e: Entrada, modo: string) => modo && hacer(`Permisos ${modo}.`, () => post("archivos-permisos", { ruta: unir(ruta, e.nombre), modo }));
  const descargar = async (e: Entrada) => {
    setError("");
    try { abrirEnlace((await api.post<{ enlace: string }>(`/sitios/${dominio}/archivos/descargar`, { ruta: unir(ruta, e.nombre) })).enlace); }
    catch (err) { setError((err as Error).message); }
  };
  const elegir = (n: string) => setElegidos(elegidos.includes(n) ? elegidos.filter((x) => x !== n) : [...elegidos, n]);
  const migas = ruta === "." ? [] : ruta.split("/");

  if (papelera) return <ArchivosPapelera dominio={dominio} onVolver={() => { setPapelera(false); cargar(); }} />;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <label className={`px-3 py-1.5 bg-ms-blue text-white rounded text-sm cursor-pointer ${ocupado ? "opacity-50 pointer-events-none" : ""}`}>
          Subir archivos<input type="file" multiple className="hidden" onChange={(e) => { subir(e.target.files); e.target.value = ""; }} />
        </label>
        <label className="text-xs flex items-center gap-1"><input type="checkbox" checked={reemplazar} onChange={(e) => setReemplazar(e.target.checked)} />reemplazar si existe</label>
        <button onClick={nuevaCarpeta} disabled={ocupado} className="px-3 py-1.5 border border-ms-gray-40 rounded text-sm disabled:opacity-50">Nueva carpeta</button>
        <button onClick={comprimir} disabled={ocupado || !elegidos.length} className="px-3 py-1.5 border border-ms-gray-40 rounded text-sm disabled:opacity-50">Comprimir en .zip{elegidos.length ? ` (${elegidos.length})` : ""}</button>
        <button onClick={() => borrar(elegidos)} disabled={ocupado || !elegidos.length} className="px-3 py-1.5 border border-ms-gray-40 rounded text-sm text-ms-red disabled:opacity-50">Borrar selección</button>
        <button onClick={() => setPapelera(true)} className="ml-auto text-sm text-ms-blue hover:underline">Papelera</button>
      </div>
      <div className="text-sm">
        <button onClick={() => cargar(".")} className="text-ms-blue hover:underline">publico</button>
        {migas.map((m, i) => <span key={i}> / <button onClick={() => cargar(migas.slice(0, i + 1).join("/"))} className="text-ms-blue hover:underline">{m}</button></span>)}
      </div>
      {progreso && <p className="text-xs text-ms-blue">Subiendo {progreso}</p>}
      {error && <p className="text-sm text-ms-red">{error}</p>}
      {mensaje && <p className="text-sm text-ms-green">{mensaje}</p>}
      <table className="w-full text-sm">
        <thead className="bg-ms-gray-20 text-xs text-ms-gray-90"><tr>
          <th className="w-6" /><th className="text-left px-2 py-1.5">Nombre</th><th className="text-right px-2 py-1.5">Tamaño</th>
          <th className="text-left px-2 py-1.5">Modificado</th><th className="text-left px-2 py-1.5">Permisos</th><th className="text-right px-2 py-1.5">Acciones</th></tr></thead>
        <tbody className="divide-y divide-ms-gray-30">
          {ruta !== "." && <tr><td /><td colSpan={5} className="px-2 py-1"><button onClick={() => cargar(migas.slice(0, -1).join("/") || ".")} className="text-ms-blue hover:underline text-xs">↑ Subir un nivel</button></td></tr>}
          {listado?.entradas.map((e) => (
            <tr key={e.nombre}>
              <td className="pl-2"><input type="checkbox" checked={elegidos.includes(e.nombre)} onChange={() => elegir(e.nombre)} aria-label={`Elegir ${e.nombre}`} /></td>
              <td className="px-2 py-1 break-all">
                {e.tipo === "carpeta" ? <button onClick={() => cargar(unir(ruta, e.nombre))} className="text-ms-blue hover:underline font-medium">{e.nombre}/</button> : e.nombre}
                {e.tipo === "enlace" && <span className="text-[11px] text-ms-gray-60"> → {e.fuera ? "fuera del sitio (no se sigue)" : e.apunta_a}</span>}
              </td>
              <td className="px-2 py-1 text-right text-xs whitespace-nowrap">{tamano(e.bytes)}</td>
              <td className="px-2 py-1 text-xs whitespace-nowrap">{e.modificado}</td>
              <td className="px-2 py-1 text-xs">
                {e.tipo === "enlace" ? "—" : (
                  <select value="" onChange={(ev) => permisos(e, ev.target.value)} disabled={ocupado} className={`${campo} py-0.5 text-xs font-mono`} title="Cambiar permisos">
                    <option value="">{e.permisos}</option>
                    {MODOS.map((m) => <option key={m.modo} value={m.modo}>{m.texto}</option>)}
                  </select>
                )}
              </td>
              <td className="px-2 py-1 text-right whitespace-nowrap text-xs space-x-2">
                {e.tipo === "archivo" && <button onClick={() => descargar(e)} className="text-ms-blue hover:underline">Descargar</button>}
                {e.tipo === "archivo" && COMPRIMIDO.test(e.nombre) && <button onClick={() => descomprimir(e)} disabled={ocupado} className="text-ms-blue hover:underline">Descomprimir</button>}
                <button onClick={() => renombrar(e)} disabled={ocupado} className="text-ms-blue hover:underline">Renombrar</button>
                <button onClick={() => moverOCopiar(e, "mover")} disabled={ocupado} className="text-ms-blue hover:underline">Mover</button>
                {e.tipo !== "enlace" && <button onClick={() => moverOCopiar(e, "copiar")} disabled={ocupado} className="text-ms-blue hover:underline">Copiar</button>}
                <button onClick={() => borrar([e.nombre])} disabled={ocupado} className="text-ms-red hover:underline">Borrar</button>
              </td>
            </tr>
          ))}
          {listado && listado.entradas.length === 0 && <tr><td colSpan={6} className="px-2 py-4 text-center text-ms-gray-60">Carpeta vacía.</td></tr>}
        </tbody>
      </table>
      {listado?.recortado && <p className="text-xs text-ms-gray-60">Se muestran los primeros 5000 elementos.</p>}
      <p className="text-[11px] text-ms-gray-60">Hasta 512 MB por archivo (para más, use SFTP). Al descomprimir se rechazan los archivos con rutas que salen de la carpeta, enlaces simbólicos o más de 1 GB / 20 000 archivos.</p>
    </div>
  );
}
