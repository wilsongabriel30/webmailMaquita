import { useState } from "react";

export interface ResultadoPaquete {
  url: string;
  raiz_web: string;
  base_datos?: string;
  bd_usuario?: string;
  bd_clave?: string;
  bd_servidor?: string;
  tablas?: number;
  app?: string;
  migracion?: { aplicacion: string | null; conexion: string; direccion_anterior?: string; reemplazos?: number; admin_usuario?: string; aviso?: string };
}

/* Subir un paquete propio (.zip o .tar.gz, hasta 512 MB) a un sitio vacío, con barra de progreso. */
export function SubirPaqueteForm({ dominio, onCancelar, onListo }: {
  dominio: string;
  onCancelar: () => void;
  onListo: (r: ResultadoPaquete) => void;
}) {
  const [archivo, setArchivo] = useState<File | null>(null);
  const [base, setBase] = useState<File | null>(null);
  const [conBd, setConBd] = useState(true);
  const [progreso, setProgreso] = useState<number | null>(null);
  const [error, setError] = useState("");

  const subir = () => {
    if (!archivo) return;
    setError(""); setProgreso(0);
    const datos = new FormData();
    datos.append("archivo", archivo);
    if (base) datos.append("base", base);
    datos.append("con_bd", conBd ? "true" : "false");
    // XMLHttpRequest y no fetch: así se ve el avance de la subida.
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/sitios/${dominio}/paquete`);
    const token = localStorage.getItem("admin_token");
    if (token) xhr.setRequestHeader("X-Admin-Token", token);
    xhr.upload.onprogress = (e) => e.lengthComputable && setProgreso(Math.round((e.loaded / e.total) * 100));
    xhr.onload = () => {
      let cuerpo: { detail?: string } & Partial<ResultadoPaquete> = {};
      try { cuerpo = JSON.parse(xhr.responseText); } catch { /* respuesta vacía */ }
      if (xhr.status >= 200 && xhr.status < 300) onListo(cuerpo as ResultadoPaquete);
      else { setError(cuerpo.detail || (xhr.status === 413 ? "El paquete supera 512 MB" : `Error ${xhr.status}`)); setProgreso(null); }
    };
    xhr.onerror = () => { setError("Se cortó la conexión durante la subida"); setProgreso(null); };
    xhr.send(datos);
  };

  return (
    <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-3">
      <h2 className="text-base font-semibold text-ms-gray-130">Subir un paquete o traer un sitio de otro hosting a {dominio}</h2>
      <ul className="text-xs text-ms-gray-90 list-disc ml-4 space-y-0.5">
        <li><b>Migrar un sitio:</b> suba el .zip con sus archivos y el respaldo de su base (.sql o .sql.gz, exportado con phpMyAdmin o el panel del otro hosting). La base se importa y, si es WordPress, Joomla o usa un archivo .env (Laravel y similares), su conexión se corrige sola; en WordPress también la dirección del sitio.</li>
        <li><b>Aplicación que no está en el catálogo:</b> suba el .zip o .tar.gz del proyecto y siga su instalador con los datos de la base que se mostrarán.</li>
        <li>Hasta 512 MB en total. Se detecta la carpeta pública (public/, htdocs/…).</li>
      </ul>
      <label className="block text-sm">Archivos del sitio (.zip o .tar.gz)
        <input type="file" accept=".zip,.tar.gz,.tgz,application/zip,application/gzip" onChange={(e) => setArchivo(e.target.files?.[0] || null)} className="block text-sm mt-1" />
      </label>
      <label className="block text-sm">Respaldo de la base (opcional: .sql o .sql.gz)
        <input type="file" accept=".sql,.gz,application/sql,application/gzip" onChange={(e) => setBase(e.target.files?.[0] || null)} className="block text-sm mt-1" />
      </label>
      {!base && <label className="text-sm text-ms-gray-90 flex items-center gap-1.5">
        <input type="checkbox" checked={conBd} onChange={(e) => setConBd(e.target.checked)} /> Preparar una base de datos MariaDB vacía
      </label>}
      {progreso !== null && (
        <div>
          <div className="h-2 bg-ms-gray-20 rounded"><div className="h-2 bg-ms-blue rounded" style={{ width: `${progreso}%` }} /></div>
          <p className="text-xs text-ms-gray-90 mt-1">{progreso < 100 ? `Subiendo… ${progreso} %` : base ? "Extrayendo, importando la base y conectando la aplicación…" : "Extrayendo y comprobando el paquete…"}</p>
        </div>
      )}
      {error && <p className="text-sm text-ms-red">{error}</p>}
      <div className="flex gap-2">
        <button onClick={subir} disabled={!archivo || progreso !== null} className="px-4 py-2 bg-ms-blue text-white rounded text-sm disabled:opacity-50">Subir e instalar</button>
        <button onClick={onCancelar} disabled={progreso !== null && progreso < 100} className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90">Cancelar</button>
      </div>
    </div>
  );
}
