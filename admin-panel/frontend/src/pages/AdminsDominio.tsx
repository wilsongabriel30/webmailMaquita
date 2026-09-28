import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../api/auth";
import { SectionHelp } from "../components/SectionHelp";
import { AdminDominioForm, AdminDominio } from "./admins-dominio/AdminDominioForm";
import { AuditoriaDominio } from "./admins-dominio/AuditoriaDominio";

export function AdminsDominio() {
  const { user } = useAuth();
  const [lista, setLista] = useState<AdminDominio[]>([]);
  const [dominios, setDominios] = useState<string[]>([]);
  const [editando, setEditando] = useState<AdminDominio | "nuevo" | null>(null);
  const [error, setError] = useState("");

  const cargar = () => api.get<AdminDominio[]>("/admins-dominio").then(setLista).catch((e) => setError(e.message));
  useEffect(() => {
    cargar();
    api.get<{ domain: string }[]>("/domains").then((d) => setDominios(d.map((x) => x.domain))).catch(() => {});
  }, []);

  const eliminar = async (a: AdminDominio) => {
    if (!confirm(`Eliminar al administrador de dominio "${a.username}"? Pierde el acceso al portal al instante. Las cuentas de correo de su dominio no se tocan.`)) return;
    await api.del(`/admins-dominio/${a.id}`);
    cargar();
  };

  if (user?.role !== "superadmin") return <div className="p-8 text-ms-red">Acceso restringido a superadmins</div>;

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-ms-gray-130">Administradores de dominio</h1>
        <SectionHelp titulo="Administradores de dominio" items={[
          { titulo: "Qué es", desc: "Personas que administran SOLO las cuentas y alias de los dominios que se les asignan. Entran por un portal aparte (otro puerto), no por este panel." },
          { titulo: "Qué pueden hacer", desc: "Crear cuentas, editar nombre y cuota, cambiar contraseñas, activar o desactivar cuentas y gestionar alias dentro de sus dominios." },
          { titulo: "Qué no pueden hacer", desc: "Ver otros dominios, eliminar cuentas, leer correo, reenviar fuera de su dominio ni tocar la configuración del servidor." },
          { titulo: "Contraseña inicial", desc: "La que se pone aquí es temporal: el portal obliga a cambiarla en la primera entrada." },
        ]} />
        <button onClick={() => setEditando("nuevo")} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark">+ Nuevo administrador de dominio</button>
      </div>

      {error && <div className="text-ms-red text-sm">{error}</div>}

      <div className="bg-white rounded border border-ms-gray-30 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-ms-gray-20 border-b border-ms-gray-30"><tr>
            <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Usuario</th>
            <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Dominios</th>
            <th className="text-center px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Estado</th>
            <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Última entrada</th>
            <th className="text-right px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Acciones</th>
          </tr></thead>
          <tbody className="divide-y divide-ms-gray-30">
            {lista.map((a) => (
              <tr key={a.id} className="hover:bg-ms-blue-lighter/50">
                <td className="px-4 py-2.5"><div className="font-medium text-ms-gray-130">{a.username}</div><div className="text-xs text-ms-gray-60">{a.display_name}</div></td>
                <td className="px-4 py-2.5 text-xs text-ms-gray-90">{a.dominios.length ? a.dominios.join(", ") : <span className="text-ms-red">Sin dominios</span>}</td>
                <td className="px-4 py-2.5 text-center">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${a.active ? "bg-green-50 text-ms-green" : "bg-red-50 text-ms-red"}`}>{a.active ? "Activo" : "Inactivo"}</span>
                  {a.must_change_password && <div className="text-[10px] text-ms-gray-60 mt-0.5">clave temporal</div>}
                </td>
                <td className="px-4 py-2.5 text-xs text-ms-gray-60">{a.last_login ? new Date(a.last_login).toLocaleString() : "Nunca"}</td>
                <td className="px-4 py-2.5 text-right space-x-3 whitespace-nowrap">
                  <button onClick={() => setEditando(a)} className="text-ms-blue text-xs hover:underline">Editar</button>
                  <button onClick={() => eliminar(a)} className="text-ms-red text-xs hover:underline">Eliminar</button>
                </td>
              </tr>
            ))}
            {!lista.length && <tr><td colSpan={5} className="px-4 py-6 text-center text-ms-gray-60 text-sm">Todavía no hay administradores de dominio.</td></tr>}
          </tbody>
        </table>
      </div>

      {editando && (
        <AdminDominioForm actual={editando === "nuevo" ? null : editando} dominios={dominios}
          onCerrar={() => setEditando(null)} onGuardado={() => { setEditando(null); cargar(); }} />
      )}

      <AuditoriaDominio />
    </div>
  );
}
