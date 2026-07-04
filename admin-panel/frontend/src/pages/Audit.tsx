import { useEffect, useState } from "react";
import { api } from "../api/client";
import { SectionHelp } from "../components/SectionHelp";

interface AuditEntry { id: number; admin_username: string; action: string; target: string; details: any; ip_address: string; created_at: string }


const ACTION_LABELS: Record<string, string> = {
  login: "Inicio de sesión",
  login_failed: "Login fallido",
  logout: "Cierre de sesión",
  mailbox_create: "Crear buzón",
  mailbox_update: "Actualizar buzón",
  mailbox_delete: "Eliminar buzón",
  mailbox_impersonate: "Impersonar buzón",
  alias_create: "Crear alias",
  alias_update: "Actualizar alias",
  alias_delete: "Eliminar alias",
  domain_create: "Crear dominio",
  domain_delete: "Eliminar dominio",
  forward_create: "Crear reenvío",
  forward_delete: "Eliminar reenvío",
  service_restart: "Reiniciar servicio",
  service_stop: "Detener servicio",
  ediscovery_search: "Búsqueda eDiscovery",
  ediscovery_export: "Exportar eDiscovery",
  signature_create: "Crear firma",
  signature_update: "Actualizar firma",
  signature_delete: "Eliminar firma",
  group_create: "Crear grupo",
  group_member_add: "Agregar miembro",
  group_member_remove: "Remover miembro",
  mail_read: "Leer correo",
  quarantine_release: "Liberar cuarentena",
  ban_ip: "Banear IP",
  unban_ip: "Desbanear IP",
  config_update: "Actualizar config",
  admin_create: "Crear administrador",
  admin_delete: "Eliminar administrador",
  legal_hold_create: "Crear retención legal",
  legal_hold_release: "Liberar retención legal",
};

export function Audit() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState("");

  const load = (p: number = 1) => {
    const params = new URLSearchParams({ page: String(p), per_page: "30" });
    if (actionFilter) params.set("action", actionFilter);
    api.get<{ total: number; entries: AuditEntry[] }>(`/audit?${params}`).then((d) => { setEntries(d.entries); setTotal(d.total); setPage(p); });
  };
  useEffect(() => { load(); }, []);

  const actionColor = (a: string) => {
    if (a.includes("delete") || a.includes("ban")) return "bg-red-50 text-ms-red border-ms-red/20";
    if (a.includes("create") || a.includes("restore")) return "bg-green-50 text-ms-green border-green-200";
    if (a.includes("login")) return "bg-ms-blue-lighter text-ms-blue border-ms-blue/20";
    return "bg-ms-gray-20 text-ms-gray-90 border-ms-gray-30";
  };

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ms-gray-130" title="Registro de auditoria. Muestra todas las acciones realizadas en el panel. Solo lectura.">Log de auditoría ({total} registros)</h1>
        <SectionHelp titulo="Log de auditoría" items={[
          { titulo: "Qué es esta sección", desc: "Historial de todas las acciones hechas por los administradores del panel: logins, creación y borrado de buzones, alias, dominios, servicios, etc. Es solo lectura: aquí no se modifica nada." },
          { titulo: "Columnas", desc: "Fecha y hora de la acción, administrador que la hizo, tipo de acción, recurso afectado (objetivo) y dirección IP desde donde se realizó." },
          { titulo: "Filtrar", desc: "Escriba parte del nombre técnico de la acción (create, delete, login, ban...) y pulse Filtrar para ver solo esos registros." },
          { titulo: "Colores", desc: "Rojo: acciones destructivas (eliminar, banear). Verde: creaciones. Azul: inicios de sesión. Gris: el resto." },
          { titulo: "Paginación", desc: "Se muestran 30 registros por página. Use Anterior y Siguiente para navegar por el historial completo." },
        ]} />
      </div>

      <div className="flex gap-2">
        <input value={actionFilter} onChange={(e) => setActionFilter(e.target.value)} placeholder="Filtrar por acción..."
          title="Registro de auditoria. Filtra por tipo de accion (create, delete, login, etc.). Solo lectura."
          className="flex-1 px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
        <button onClick={() => load(1)} title="Registro de auditoria. Aplica el filtro de accion y recarga los registros. Solo lectura, no modifica nada." className="px-4 py-2 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark">Filtrar</button>
      </div>

      <div className="bg-white rounded border border-ms-gray-30 overflow-hidden" title="Registro de auditoria. Muestra todas las acciones realizadas en el panel. Solo lectura.">
        <table className="w-full text-sm">
          <thead className="bg-ms-gray-20 border-b border-ms-gray-30"><tr>
            <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs" title="Fecha y hora en que se realizo la accion.">Fecha</th>
            <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs" title="Administrador que realizo la accion.">Admin</th>
            <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs" title="Tipo de accion realizada (create, delete, login, etc.).">Acción</th>
            <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs" title="Recurso afectado por la accion.">Objetivo</th>
            <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs" title="Dirección IP desde la que se realizo la accion.">IP</th>
          </tr></thead>
          <tbody className="divide-y divide-ms-gray-30">
            {entries.map((e) => (
              <tr key={e.id} className="hover:bg-ms-blue-lighter/50" title={`Auditoría #${e.id}: ${e.action} sobre ${e.target || "N/A"} por ${e.admin_username} desde ${e.ip_address}. Solo lectura.`}>
                <td className="px-4 py-2.5 text-xs text-ms-gray-60 whitespace-nowrap">{new Date(e.created_at).toLocaleString()}</td>
                <td className="px-4 py-2.5 text-xs font-medium text-ms-gray-130">{e.admin_username}</td>
                <td className="px-4 py-2.5 text-xs"><span className={`px-2 py-0.5 rounded border text-[10px] font-medium ${actionColor(e.action)}`} title={e.action}>{ACTION_LABELS[e.action] || e.action}</span></td>
                <td className="px-4 py-2.5 text-xs text-ms-gray-130">{e.target || "-"}</td>
                <td className="px-4 py-2.5 text-xs text-ms-gray-60 font-mono">{e.ip_address}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex justify-between items-center">
        <button onClick={() => load(page - 1)} disabled={page <= 1} title="Registro de auditoria. Ir a la página anterior. Solo lectura." className="px-3 py-1.5 border border-ms-gray-40 rounded text-xs disabled:opacity-50 hover:bg-ms-gray-20">Anterior</button>
        <span className="text-xs text-ms-gray-60" title="Registro de auditoria. Paginacion de resultados. Solo lectura.">Página {page} de {Math.ceil(total / 30) || 1}</span>
        <button onClick={() => load(page + 1)} disabled={page >= Math.ceil(total / 30)} title="Registro de auditoria. Ir a la página siguiente. Solo lectura." className="px-3 py-1.5 border border-ms-gray-40 rounded text-xs disabled:opacity-50 hover:bg-ms-gray-20">Siguiente</button>
      </div>
    </div>
  );
}
