import { Asiento, fechaHora } from "./tipos";

// Registro de Flota: toda acción del panel, del equipo y del servidor (solo inserción en la base).

export function TablaRegistro({ registro, conEquipo }: { registro: Asiento[]; conEquipo?: boolean }) {
  return (
    <div className="bg-white rounded-lg border border-ms-gray-30 overflow-x-auto">
      <table className="w-full text-sm">
        <thead><tr className="bg-ms-gray-10">{["Momento", ...(conEquipo ? ["Equipo"] : []), "Quién", "Acción", "Detalle", "IP"].map((h) =>
          <th key={h} className="text-left px-3 py-2.5 font-medium text-ms-gray-90 text-xs">{h}</th>)}</tr></thead>
        <tbody>
          {registro.map((r) => <tr key={r.id} className="border-t border-ms-gray-20 align-top">
            <td className="px-3 py-2 text-xs whitespace-nowrap">{fechaHora(r.momento)}</td>
            {conEquipo && <td className="px-3 py-2 text-xs">{r.nombre || "—"}</td>}
            <td className="px-3 py-2 text-xs">{r.actor}</td>
            <td className="px-3 py-2 text-xs">{r.accion}</td>
            <td className="px-3 py-2 text-xs font-mono break-all max-w-md">{r.detalle ? JSON.stringify(r.detalle) : ""}</td>
            <td className="px-3 py-2 text-xs">{r.ip}</td>
          </tr>)}
          {!registro.length && <tr><td colSpan={6} className="px-4 py-6 text-center text-ms-gray-60">Sin registros.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}
