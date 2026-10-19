import { useState } from "react";

export interface ResultadoPaquete {
  url: string;
  raiz_web: string;
  base_datos?: string;
  bd_usuario?: string;
  bd_clave?: string;
  bd_servidor?: string;
}

/* Subir un paquete propio (.zip o .tar.gz, hasta 512 MB) a un sitio vacío, con barra de progreso. */
export function SubirPaqueteForm({ dominio, onCancelar, onListo }: {
  dominio: string;
  onCancelar: () => void;
  onListo: (r: ResultadoPaquete) => void;
}) {
  const [archivo, setArchivo] = useState<File | null>(null);
  const [conBd, setConBd] = useState(true);
  const [progreso, setProgreso] = useState<number | null>(null);
  const [error, setError] = useState("");

  const subir = () => {
    if (!archivo) return;
    setError(""); setProgreso(0);
    const datos = new FormData();
    datos.append("archivo", archivo);
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
      <h2 className="text-base font-semibold text-ms-gray-130">Subir un paquete a {dominio}</h2>
      <p className="text-xs text-ms-gray-90">Para aplicaciones que no están en el catálogo: suba el .zip o .tar.gz que publica el proyecto (hasta 512 MB).
        Se extrae en el sitio, se detecta la carpeta pública (public/, htdocs/…) y, si lo pide, se prepara una base de datos.
        Luego abra el sitio y siga el instalador de la aplicación con los datos de la base que se mostrarán.</p>
      <input type="file" accept=".zip,.tar.gz,.tgz,application/zip,application/gzip" onChange={(e) => setArchivo(e.target.files?.[0] || null)} className="text-sm" />
      <label className="text-sm text-ms-gray-90 flex items-center gap-1.5">
        <input type="checkbox" checked={conBd} onChange={(e) => setConBd(e.target.checked)} /> Preparar una base de datos MariaDB
      </label>
      {progreso !== null && (
        <div>
          <div className="h-2 bg-ms-gray-20 rounded"><div className="h-2 bg-ms-blue rounded" style={{ width: `${progreso}%` }} /></div>
          <p className="text-xs text-ms-gray-90 mt-1">{progreso < 100 ? `Subiendo… ${progreso} %` : "Extrayendo y comprobando el paquete…"}</p>
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
