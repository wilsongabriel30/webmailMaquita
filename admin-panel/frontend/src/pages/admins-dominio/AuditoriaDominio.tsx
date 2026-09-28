import { useEffect, useState } from "react";
import { api } from "../../api/client";

interface Registro { admin_username: string; action: string; target: string | null; ip: string | null; created_at: string }

const NOMBRES: Record<string, string> = {
  entrada: "Entró al portal", entrada_fallida: "Intento fallido de entrada", clave_propia: "Cambió su contraseña",
  cuenta_crear: "Creó la cuenta", cuenta_editar: "Editó la cuenta", cuenta_clave: "Cambió la contraseña de", cuenta_activa: "Activó o desactivó",
  alias_crear: "Creó el alias", alias_editar: "Editó el alias", alias_eliminar: "Eliminó el alias",
};

export function AuditoriaDominio() {
  const [registros, setRegistros] = useState<Registro[]>([]);
  useEffect(() => { api.get<Registro[]>("/admins-dominio/auditoria?limite=100").then(setRegistros).catch(() => {}); }, []);

  return (
    <div className="bg-white rounded border border-ms-gray-30">
      <div className="px-4 py-2.5 border-b border-ms-gray-30 text-sm font-medium text-ms-gray-130">Actividad reciente en el portal de dominio</div>
      <div className="max-h-80 overflow-auto">
        <table className="w-full text-xs">
          <tbody className="divide-y divide-ms-gray-30">
            {registros.map((r, i) => (
              <tr key={i}>
                <td className="px-4 py-1.5 text-ms-gray-60 whitespace-nowrap">{new Date(r.created_at).toLocaleString()}</td>
                <td className="px-4 py-1.5 font-medium text-ms-gray-130">{r.admin_username}</td>
                <td className="px-4 py-1.5 text-ms-gray-90">{NOMBRES[r.action] || r.action} {r.target}</td>
                <td className="px-4 py-1.5 text-ms-gray-60">{r.ip}</td>
              </tr>
            ))}
            {!registros.length && <tr><td className="px-4 py-4 text-center text-ms-gray-60">Sin actividad todavía.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
