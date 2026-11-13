import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api } from "../api/client";

interface Resumen { pendientes: number; ataques: number; por_revisar?: number; inicios_riesgosos: number; anomalias: number; envios?: number; envios_bloqueadas?: number; }

/* Franja que avisa, apenas se entra al panel, de que hay alertas de seguridad por revisar. */
export function AvisoAlertas() {
  const [r, setR] = useState<Resumen | null>(null);
  const { pathname } = useLocation();
  useEffect(() => {
    api.get<Resumen>("/alertas-seguridad/resumen").then(setR).catch(() => setR(null));
  }, [pathname]);
  if (!r || r.pendientes === 0 || pathname === "/alertas-seguridad") return null;
  const partes = [
    r.envios_bloqueadas ? `${r.envios_bloqueadas} cuenta(s) BLOQUEADA(S) por escribir a muchas personas` : "",
    r.envios && r.envios > (r.envios_bloqueadas || 0) ? `${r.envios - (r.envios_bloqueadas || 0)} aviso(s) de envío a muchas personas por revisar` : "",
    r.ataques ? `${r.ataques} cuenta(s) con intentos de adivinar la contraseña` : "",
    r.por_revisar ? `${r.por_revisar} cuenta(s) con muchos fallos de contraseña por revisar` : "",
    r.inicios_riesgosos ? `${r.inicios_riesgosos} inicio(s) de sesión riesgoso(s)` : "",
    r.anomalias ? `${r.anomalias} anomalía(s)` : "",
  ].filter(Boolean).join(" · ");
  return (
    <div role="alert" className={`flex items-center justify-between gap-3 px-4 py-2 text-sm ${r.ataques || r.envios_bloqueadas ? "bg-red-50 text-red-700 border-b border-red-200" : "bg-amber-50 text-amber-800 border-b border-amber-200"}`}>
      <span><b>Alertas de seguridad:</b> {partes || `${r.pendientes} por revisar`}.</span>
      <Link to="/alertas-seguridad" className="shrink-0 px-3 py-1 rounded bg-white border border-current text-xs font-medium">Ver alertas</Link>
    </div>
  );
}
