import { useMemo, useState } from "react";
import { Equipo, haceCuanto } from "./tipos";

const ESTADO: Record<string, string> = {
  activo: "bg-green-50 text-green-700", perdido: "bg-red-50 text-red-700",
  revocado: "bg-gray-100 text-gray-600", baja: "bg-gray-100 text-gray-600",
};

export function Equipos({ equipos, onAbrir }: { equipos: Equipo[]; onAbrir: (id: number) => void }) {
  const [q, setQ] = useState("");
  const visibles = useMemo(() => {
    const t = q.trim().toLowerCase();
    if (!t) return equipos;
    return equipos.filter((e) =>
      [e.nombre, e.modelo, e.fabricante, e.custodio_nombre, e.custodio_email, e.centro_costo, e.sede, e.imei, e.serie]
        .some((v) => (v || "").toLowerCase().includes(t)));
  }, [equipos, q]);

  return (
    <div className="bg-white rounded-lg border border-ms-gray-30">
      <div className="p-3 border-b border-ms-gray-30">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar por nombre, custodio, modelo, IMEI, centro de costo…"
          className="w-full max-w-md px-3 py-1.5 text-sm border border-ms-gray-40 rounded" />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="bg-ms-gray-10">
            {["Equipo", "Custodio", "Centro de costo / sede", "Modo", "Batería", "Último contacto", "Estado"].map((h) => (
              <th key={h} className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">{h}</th>))}
          </tr></thead>
          <tbody>
            {visibles.map((e) => {
              const c = haceCuanto(e.ultimo_contacto);
              return (
                <tr key={e.id} onClick={() => onAbrir(e.id)} className="border-t border-ms-gray-20 hover:bg-ms-gray-10 cursor-pointer">
                  <td className="px-4 py-2.5">
                    <div className="font-medium text-ms-gray-130">{e.nombre || `${e.fabricante || ""} ${e.modelo || "Equipo"}`.trim()}</div>
                    <div className="text-xs text-ms-gray-60">{e.fabricante} {e.modelo} · Android {e.android || "?"}{e.imei ? ` · IMEI ${e.imei}` : ""}</div>
                  </td>
                  <td className="px-4 py-2.5"><div>{e.custodio_nombre || "—"}</div><div className="text-xs text-ms-gray-60">{e.custodio_email}</div></td>
                  <td className="px-4 py-2.5">{e.centro_costo || "—"}<div className="text-xs text-ms-gray-60">{e.sede}</div></td>
                  <td className="px-4 py-2.5 text-xs" title={e.modo === "propietario" ? "Enrolado como equipo de la organización: control completo" : "App instalada en un teléfono ya en uso: la persona puede quitar permisos o desinstalar"}>
                    {e.modo === "propietario" ? "Administrado" : "Limitado"}</td>
                  <td className="px-4 py-2.5">{e.bateria != null ? `${e.bateria}%${e.cargando ? " ⚡" : ""}` : "—"}</td>
                  <td className={`px-4 py-2.5 ${c.alerta && e.estado === "activo" ? "text-red-600 font-medium" : ""}`}>{c.texto}</td>
                  <td className="px-4 py-2.5"><span className={`px-2 py-0.5 rounded text-xs ${ESTADO[e.estado]}`}>{e.estado}</span></td>
                </tr>);
            })}
            {!visibles.length && <tr><td colSpan={7} className="px-4 py-8 text-center text-ms-gray-60">
              {equipos.length ? "Ningún equipo coincide con la búsqueda." : "Aún no hay equipos. Cree un código en «Códigos de enrolamiento» y escríbalo en la app del teléfono."}</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
