import { useState } from "react";
import { api } from "../../../api/client";
import { botonPrincipal, campo, type EstadoWeb, type PropsPestana } from "./tipos";

const NOMBRES: Record<string, string> = {
  "403": "403 · Prohibido",
  "404": "404 · No encontrado",
  "500": "500 · Error del servidor",
  "502": "502 · La aplicación no responde",
  "503": "503 · Sobrecarga o mantenimiento",
};

/* Páginas de error propias: un archivo .html de la carpeta pública para cada código. */
export function ErroresPestana({ dominio, estado, ocupado, hacer }: PropsPestana) {
  const [paginas, setPaginas] = useState<Record<string, string>>(estado.errores.paginas);
  if (!estado.raiz_web) return <p className="text-sm text-ms-gray-90">Este sitio es una aplicación propia de Python o Node.js: sus páginas de error las genera la propia aplicación.</p>;

  return (
    <div className="space-y-3">
      <p className="text-xs text-ms-gray-90">Son las que muestra el servidor cuando el error es suyo (un archivo que no existe, PHP caído o sobrecargado). Las que genera la aplicación (el 404 de WordPress) siguen siendo suyas. Suba antes el .html por FTP o con «Avanzado → Archivos».</p>
      <datalist id="paginas-error">{estado.errores.candidatos.map((c) => <option key={c} value={c} />)}</datalist>
      <div className="grid sm:grid-cols-2 gap-2">
        {estado.errores.codigos.map((c) => (
          <label key={c} className="text-xs text-ms-gray-90">{NOMBRES[c] || c}
            <input list="paginas-error" placeholder="De serie (la de nginx)" value={paginas[c] || ""} onChange={(e) => setPaginas({ ...paginas, [c]: e.target.value.trim() })}
              className={`${campo} w-full font-mono`} />
          </label>
        ))}
      </div>
      {estado.errores.candidatos.length === 0 && <p className="text-[11px] text-ms-gray-60">No hay archivos .html en la carpeta pública todavía.</p>}
      <button disabled={ocupado} onClick={() => hacer("Páginas de error guardadas.", () => api.put<EstadoWeb>(`/sitios/${dominio}/web/errores`, { paginas }))} className={botonPrincipal}>Guardar</button>
    </div>
  );
}
