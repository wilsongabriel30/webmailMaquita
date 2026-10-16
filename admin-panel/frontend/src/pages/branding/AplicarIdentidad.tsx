import { useState } from "react";
import { api } from "../../api/client";

interface Resultado { app: string; iconos: string; drive: string; sitios: { dominio: string; ok: boolean }[] }

/* Lleva la identidad guardada a todo el servidor: app del correo, Drive y páginas «en construcción». */
export function AplicarIdentidad({ hayCambiosSinGuardar }: { hayCambiosSinGuardar: boolean }) {
  const [estado, setEstado] = useState("");
  const [res, setRes] = useState<Resultado | null>(null);
  const aplicar = async () => {
    if (!confirm("Se aplicará la identidad en la app del correo (nombre e íconos), el Drive y las páginas «en construcción» de los sitios, y se reiniciarán el webmail y el Drive (unos segundos). ¿Continuar?")) return;
    setEstado("Aplicando…"); setRes(null);
    try { setRes(await api.post<Resultado>("/branding/aplicar")); setEstado(""); }
    catch (e) { setEstado((e as Error).message); }
  };
  return (
    <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-ms-gray-130">Aplicar en todo el servidor</h3>
          <p className="text-xs text-ms-gray-60">Nombre e íconos de la app del correo (se generan desde el logo), nombre del Drive y páginas «en construcción» de los sitios web.</p>
        </div>
        <button onClick={aplicar} disabled={hayCambiosSinGuardar || estado === "Aplicando…"}
          title={hayCambiosSinGuardar ? "Guarde primero los cambios" : ""}
          className="px-4 py-2 bg-ms-blue text-white rounded text-sm disabled:opacity-50 whitespace-nowrap">Aplicar en todo</button>
      </div>
      {estado && <p className="text-sm text-ms-gray-90">{estado}</p>}
      {res && (
        <ul className="text-sm space-y-1">
          <li>App del correo: {res.app}</li>
          <li>Íconos: {res.iconos}</li>
          <li>Drive: {res.drive}</li>
          <li>Sitios: {res.sitios.length ? res.sitios.map((s) => `${s.dominio}${s.ok ? "" : " (error)"}`).join(", ") : "ninguno «en construcción»"}</li>
        </ul>
      )}
    </div>
  );
}
