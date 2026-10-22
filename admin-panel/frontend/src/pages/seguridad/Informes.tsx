import { useState } from "react";
import { consulta, descargar, imprimir, type Rango } from "./api";
import { Seccion } from "./comunes";

const CSV: { tipo: string; titulo: string; desc: string }[] = [
  { tipo: "flujo", titulo: "Flujo de correo", desc: "Entregados, enviados, rechazados, spam y cola por periodo." },
  { tipo: "accesos", titulo: "Inicios de sesión", desc: "Correctos y fallidos por periodo y servicio." },
  { tipo: "ips", titulo: "IP con fallos", desc: "Hasta 1000 IP, con país, fallos y cuentas probadas." },
  { tipo: "cuentas", titulo: "Cuentas atacadas", desc: "Hasta 1000 cuentas con fallos de inicio de sesión." },
  { tipo: "alertas", titulo: "Alertas de anomalías", desc: "Todas las del periodo con su estado, quién las reconoció y la nota." },
  { tipo: "cumplimiento", titulo: "Cumplimiento", desc: "Acciones de eDiscovery, custodios, retenciones y lectura de buzones (auditoría del panel)." },
];

/* Informes descargables para auditorías: CSV por tablero y un informe completo imprimible (PDF). */
export function Informes({ rango }: { rango: Rango }) {
  const [msg, setMsg] = useState("");
  const q = consulta(rango);
  const sufijo = `${rango.desde}_${rango.hasta}`;
  const hacer = async (f: () => Promise<void>) => { setMsg(""); try { await f(); } catch (e) { setMsg((e as Error).message); } };

  return (
    <div className="space-y-4 max-w-4xl">
      <Seccion titulo="Informe completo (PDF)">
        <p className="text-sm text-ms-gray-90 mb-3">Resumen del periodo con cifras, tablas por día, IP y cuentas con más fallos, alertas y actividad de cumplimiento. Se abre el diálogo de impresión del navegador: elija «Guardar como PDF».</p>
        <div className="flex gap-2">
          <button onClick={() => hacer(() => imprimir(`/seguridad/informes/resumen.html?${q}`))} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm">Imprimir / guardar como PDF</button>
          <button onClick={() => hacer(() => descargar(`/seguridad/informes/resumen.html?${q}`, `informe-seguridad_${sufijo}.html`))} className="px-3 py-1.5 border border-ms-blue text-ms-blue rounded text-sm">Descargar HTML</button>
        </div>
      </Seccion>
      <Seccion titulo="Datos en CSV (hoja de cálculo)">
        <div className="divide-y divide-ms-gray-20">
          {CSV.map((c) => (
            <div key={c.tipo} className="py-2 flex items-center gap-3">
              <div className="flex-1"><p className="text-sm font-medium">{c.titulo}</p><p className="text-xs text-ms-gray-90">{c.desc}</p></div>
              <button onClick={() => hacer(() => descargar(`/seguridad/informes/${c.tipo}.csv?${q}`, `seguridad-${c.tipo}_${sufijo}.csv`))}
                className="px-3 py-1 border border-ms-gray-40 rounded text-sm hover:bg-ms-gray-20">Descargar CSV</button>
            </div>
          ))}
        </div>
      </Seccion>
      <p className="text-xs text-ms-gray-90">Cada descarga queda en la auditoría del panel (contiene cuentas e IP de personas).</p>
      {msg && <p className="text-sm text-ms-red">{msg}</p>}
    </div>
  );
}
