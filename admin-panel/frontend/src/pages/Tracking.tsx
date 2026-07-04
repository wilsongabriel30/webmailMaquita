import { useEffect, useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

interface TrackEntry { queue_id: string; date: string; from: string; to: string[]; status: string; size: number; relay: string; delay: string; dsn: string }
interface TrackData { summary: { total: number; sent: number; bounced: number; deferred: number; rejected: number }; entries: TrackEntry[] }

const statusColors: Record<string, string> = {
  sent: "bg-green-50 text-ms-green border-green-200",
  bounced: "bg-red-50 text-ms-red border-ms-red/20",
  deferred: "bg-yellow-50 text-yellow-700 border-yellow-200",
  reject: "bg-red-50 text-ms-red border-ms-red/20",
};

const statusLabels: Record<string, string> = {
  sent: "Enviado", bounced: "Rebotado", deferred: "Diferido", reject: "Rechazado",
};

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString("es-EC", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch { return iso; }
}

export function Tracking() {
  const [data, setData] = useState<TrackData | null>(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);

  const load = (q?: string) => {
    setLoading(true);
    const params = q ? `?search=${encodeURIComponent(q)}` : "";
    api.get<TrackData>(`/tracking${params}`).then(setData).catch(() => {}).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);
  const doSearch = () => load(search);
  const formatSize = (b: number) => b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : b > 1024 ? `${(b / 1024).toFixed(0)} KB` : `${b} B`;

  return (
    <div className="p-6 space-y-5">
      <div className="flex justify-end">
        <SectionHelp
          titulo="Rastreo de mensajes"
          items={[
            { titulo: "Para qué sirve", desc: "Historial de los correos procesados por el servidor (logs de Postfix): permite averiguar si un correo salió, llegó, rebotó o fue rechazado. Todo es de solo lectura." },
            { titulo: "Búsqueda", desc: "Escriba un email (remitente o destinatario) o un Queue ID y pulse Buscar o Enter para filtrar los registros." },
            { titulo: "Tarjetas de resumen", desc: "Conteo de los resultados: Total, Enviados, Rebotados, Diferidos y Rechazados." },
            { titulo: "Estados", desc: "Enviado: entregado al destino. Rebotado: devuelto por el servidor destino. Diferido: falló temporalmente y se reintentará. Rechazado: bloqueado en la entrada (spam, política)." },
            { titulo: "Tabla", desc: "Fecha, remitente, destinatarios, estado, tamaño y relay (servidor por el que se entregó). Se muestran los 100 registros más recientes del filtro." },
          ]}
        />
      </div>
      <h1 className="text-xl font-semibold text-ms-gray-130" title="Rastreo de mensajes enviados y recibidos. Solo lectura, no modifica nada.">Rastreo de mensajes</h1>

      <div className="flex gap-2">
        <input value={search} onChange={(e) => setSearch(e.target.value)} onKeyDown={(e) => e.key === "Enter" && doSearch()}
          placeholder="Buscar por email, queue ID..."
          title="Escriba un email o queue ID para filtrar los registros de envio/recepcion. Solo lectura."
          className="flex-1 px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue focus:ring-1 focus:ring-ms-blue" />
        <button onClick={doSearch} disabled={loading} title="Busca registros de envio/recepcion de correos. Solo lectura, no modifica nada." className="px-5 py-2 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark disabled:opacity-50">
          {loading ? "Buscando..." : "Buscar"}
        </button>
      </div>

      {data && (
        <div className="grid grid-cols-5 gap-2">
          {[
            { label: "Total", value: data.summary.total, color: "text-ms-gray-130 bg-ms-gray-20" },
            { label: "Enviados", value: data.summary.sent, color: "text-ms-green bg-green-50" },
            { label: "Rebotados", value: data.summary.bounced, color: "text-ms-red bg-red-50" },
            { label: "Diferidos", value: data.summary.deferred, color: "text-yellow-700 bg-yellow-50" },
            { label: "Rechazados", value: data.summary.rejected, color: "text-ms-red bg-red-50" },
          ].map((c) => (
            <div key={c.label} className={`${c.color} rounded border border-ms-gray-30 p-3 text-center`} title={`Estadistica de rastreo: ${c.label}. Solo lectura.`}>
              <p className="text-[10px] font-medium uppercase opacity-75">{c.label}</p>
              <p className="text-lg font-bold">{c.value}</p>
            </div>
          ))}
        </div>
      )}

      {data?.entries && (
        <div className="bg-white rounded border border-ms-gray-30 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-ms-gray-20 border-b border-ms-gray-30"><tr>
              <th className="text-left px-4 py-2 font-medium text-ms-gray-90 text-xs">Fecha</th>
              <th className="text-left px-4 py-2 font-medium text-ms-gray-90 text-xs">De</th>
              <th className="text-left px-4 py-2 font-medium text-ms-gray-90 text-xs">Para</th>
              <th className="text-center px-4 py-2 font-medium text-ms-gray-90 text-xs">Estado</th>
              <th className="text-right px-4 py-2 font-medium text-ms-gray-90 text-xs">Tamano</th>
              <th className="text-left px-4 py-2 font-medium text-ms-gray-90 text-xs">Relay</th>
            </tr></thead>
            <tbody className="divide-y divide-ms-gray-30">
              {data.entries.slice(0, 100).map((e, i) => (
                <tr key={i} className="hover:bg-ms-blue-lighter/50">
                  <td className="px-4 py-2 text-xs text-ms-gray-60 whitespace-nowrap">{formatDate(e.date)}</td>
                  <td className="px-4 py-2 text-xs text-ms-gray-130 truncate max-w-[150px]">{e.from || "-"}</td>
                  <td className="px-4 py-2 text-xs text-ms-gray-130 truncate max-w-[150px]">{e.to?.join(", ") || "-"}</td>
                  <td className="px-4 py-2 text-center">
                    <span className={`px-2 py-0.5 rounded border text-[10px] font-medium ${statusColors[e.status] || "bg-ms-gray-20 border-ms-gray-30"}`}>{statusLabels[e.status] || e.status}</span>
                  </td>
                  <td className="px-4 py-2 text-right text-xs text-ms-gray-60">{e.size ? formatSize(e.size) : "-"}</td>
                  <td className="px-4 py-2 text-xs text-ms-gray-60 truncate max-w-[150px]">{e.relay || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
