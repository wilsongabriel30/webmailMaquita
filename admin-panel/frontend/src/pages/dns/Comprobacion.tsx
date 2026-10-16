import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { Comprobacion as Datos } from "./tipos";

/* Semáforo de propagación: cómo ve Internet la zona (consulta por DNS sobre HTTPS). */
export function Comprobacion({ zona, automatica = false }: { zona: string; automatica?: boolean }) {
  const [datos, setDatos] = useState<Datos | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");

  const comprobar = () => {
    setCargando(true); setError("");
    api.get<Datos>(`/dns/${zona}/comprobar`).then(setDatos).catch((e) => setError(e.message)).finally(() => setCargando(false));
  };

  useEffect(() => {
    comprobar();
    if (!automatica) return;
    // Mientras no esté todo en verde, se vuelve a mirar cada 5 minutos.
    const t = setInterval(() => { if (!datos?.lista) comprobar(); }, 300000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zona]);

  return (
    <div className="bg-white rounded border border-ms-gray-30 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-ms-gray-130 text-sm">Cómo lo ve Internet</h3>
        <button onClick={comprobar} disabled={cargando} className="text-ms-blue hover:underline text-xs disabled:opacity-50">
          {cargando ? "Comprobando…" : "Comprobar ahora"}
        </button>
      </div>
      {error && <p className="text-ms-red text-sm">{error}</p>}
      {datos && (
        <ul className="space-y-2">
          {datos.pruebas.map((p) => (
            <li key={p.clave} className="flex gap-3 text-sm">
              <span className={`mt-1 inline-block w-2.5 h-2.5 rounded-full shrink-0 ${p.ok ? "bg-green-500" : "bg-amber-400"}`} aria-label={p.ok ? "correcto" : "pendiente"} />
              <div>
                <div className="text-ms-gray-130">{p.titulo}</div>
                <div className="text-xs text-ms-gray-60 break-all">Respuesta: {p.obtenido}</div>
                {!p.ok && p.que_hacer && <div className="text-xs text-amber-700 mt-0.5">{p.que_hacer}</div>}
              </div>
            </li>
          ))}
        </ul>
      )}
      {datos?.lista && <p className="text-sm text-ms-green">Todo listo: ya se pueden pedir los certificados (Zonas DNS → Certificado del correo y Sitios web → HTTPS).</p>}
    </div>
  );
}
