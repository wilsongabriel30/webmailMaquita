import { useState } from "react";
import { api } from "../../api/client";

// Verificación en dos pasos en la lista de buzones: filtro, recuento y distintivo de cada fila.
// El estado de cada buzón llega con la propia lista (campo dos_pasos); el recuento, de
// /mailboxes/dos-pasos/resumen, y siempre es sobre las cuentas activas del servidor.
export type FiltroDosPasos = "todas" | "con" | "sin";

export interface ResumenDosPasos {
  cuentas_activas: number;
  con_dos_pasos: number;
  sin_dos_pasos: number;
  obligadas: number;
  obligadas_sin_activar: number;
  exigida_a_todas: boolean;
  fecha_limite: string | null;
}

export function useResumenDosPasos() {
  const [resumen, setResumen] = useState<ResumenDosPasos | null>(null);
  const recargar = () => api.get<ResumenDosPasos>("/mailboxes/dos-pasos/resumen").then(setResumen).catch(() => setResumen(null));
  return { resumen, recargar };
}

export const coincideDosPasos = (filtro: FiltroDosPasos, activa?: boolean) =>
  filtro === "todas" || (filtro === "con") === !!activa;

const fecha = (iso: string) => iso.slice(0, 10).split("-").reverse().join("/");

export function FiltroDosPasosBuzones({ valor, onCambio, resumen, mostrados, total }: {
  valor: FiltroDosPasos; onCambio: (f: FiltroDosPasos) => void; resumen: ResumenDosPasos | null; mostrados: number; total: number;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ms-gray-90">
      <label className="flex items-center gap-2">
        <span className="font-medium">Verificación en dos pasos</span>
        <select value={valor} onChange={(e) => onCambio(e.target.value as FiltroDosPasos)}
          title="Muestra solo las cuentas que tienen, o que no tienen, la verificación en dos pasos activa. Se combina con la búsqueda."
          className="px-2 py-1.5 border border-ms-gray-40 rounded text-sm bg-white text-ms-gray-130 focus:outline-none focus:border-ms-blue">
          <option value="todas">Todas</option>
          <option value="con">Con verificación en dos pasos</option>
          <option value="sin">Sin verificación en dos pasos</option>
        </select>
      </label>
      {resumen && (
        <span title="Recuento sobre las cuentas activas del servidor. Cuenta como activa solo la verificación que la persona ya confirmó con un código.">
          <span className="font-semibold text-ms-gray-130">{resumen.con_dos_pasos} de {resumen.cuentas_activas}</span> cuentas activas la tienen activa
          {resumen.obligadas_sin_activar > 0 && (
            <span className="text-ms-red"> · {resumen.obligadas_sin_activar} de {resumen.obligadas} cuentas obligadas aún sin activarla</span>
          )}
          {resumen.exigida_a_todas && (
            <span> · {resumen.fecha_limite ? `Obligatoria para todas las cuentas desde el ${fecha(resumen.fecha_limite)}` : "Obligatoria para todas las cuentas"}</span>
          )}
        </span>
      )}
      {mostrados !== total && <span className="ml-auto">Se muestran {mostrados} de {total} buzones</span>}
    </div>
  );
}

export function DistintivoDosPasos({ activa, desde, obligatoria }: { activa?: boolean; desde?: string | null; obligatoria?: boolean }) {
  const ayuda = activa
    ? `Verificación en dos pasos activa${desde ? ` desde el ${fecha(desde)}` : ""}.`
    : obligatoria
      ? "Cuenta obligada a usar la verificación en dos pasos y todavía sin activarla: el webmail se la pedirá al entrar."
      : "Esta cuenta no tiene activa la verificación en dos pasos. La activa la propia persona desde el webmail.";
  const color = activa ? "bg-green-50 text-ms-green" : obligatoria ? "bg-red-50 text-ms-red" : "bg-yellow-50 text-yellow-700";
  return (
    <span title={ayuda} className={`px-2 py-0.5 rounded text-[10px] font-medium whitespace-nowrap ${color}`}>
      {activa ? "Activa" : obligatoria ? "Sin activar · obligatoria" : "Sin activar"}
    </span>
  );
}
