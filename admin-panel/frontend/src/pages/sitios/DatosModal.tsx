import { useState } from "react";
import { ArchivosPestana } from "./ArchivosPestana";
import { CopiasPestana } from "./CopiasPestana";
import { DisponibilidadPestana } from "./DisponibilidadPestana";
import { EstadisticasPestana } from "./EstadisticasPestana";
import { RegistrosPestana } from "./RegistrosPestana";

type Pestana = "archivos" | "registros" | "estadisticas" | "disponibilidad" | "copias";
const PESTANAS: { id: Pestana; titulo: string }[] = [
  { id: "archivos", titulo: "Archivos" },
  { id: "registros", titulo: "Errores y accesos" },
  { id: "estadisticas", titulo: "Visitas" },
  { id: "disponibilidad", titulo: "Disponibilidad" },
  { id: "copias", titulo: "Copias del sitio" },
];

/* Archivos y datos del sitio: administrador de archivos, registros, estadísticas (GoAccess), disponibilidad y
   copias que controla el dueño del sitio. Cada pestaña es su propio componente. */
export function DatosModal({ dominio, onCerrar }: { dominio: string; onCerrar: () => void }) {
  const [pestana, setPestana] = useState<Pestana>("archivos");
  const boton = (activo: boolean) => `px-3 py-1.5 text-sm rounded-t border-b-2 ${activo ? "border-ms-blue text-ms-blue" : "border-transparent text-ms-gray-90"}`;
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" role="dialog" aria-modal="true">
      <div className="bg-white rounded shadow-lg w-full max-w-5xl p-5 space-y-3 max-h-[92vh] overflow-y-auto">
        <div className="flex justify-between items-start">
          <h2 className="text-lg font-semibold text-ms-gray-130">Archivos y datos — {dominio}</h2>
          <button onClick={onCerrar} className="text-sm text-ms-gray-90 hover:underline">Cerrar</button>
        </div>
        <div className="flex flex-wrap gap-1 border-b border-ms-gray-30">
          {PESTANAS.map((p) => <button key={p.id} className={boton(pestana === p.id)} onClick={() => setPestana(p.id)}>{p.titulo}</button>)}
        </div>
        {pestana === "archivos" && <ArchivosPestana dominio={dominio} />}
        {pestana === "registros" && <RegistrosPestana dominio={dominio} />}
        {pestana === "estadisticas" && <EstadisticasPestana dominio={dominio} />}
        {pestana === "disponibilidad" && <DisponibilidadPestana dominio={dominio} />}
        {pestana === "copias" && <CopiasPestana dominio={dominio} />}
      </div>
    </div>
  );
}
