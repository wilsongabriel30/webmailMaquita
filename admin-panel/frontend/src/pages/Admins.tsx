import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../api/auth";

interface Admin { id: number; username: string; display_name: string; role: string; active: boolean; created_at: string; last_login: string }

export function Admins() {
  const { user } = useAuth();
  const [admins, setAdmins] = useState<Admin[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ username: "", password: "", display_name: "", role: "admin" });

  const load = () => api.get<Admin[]>("/auth/admins").then(setAdmins).catch(() => {});
  useEffect(() => { load(); }, []);

  const create = async () => {
    if (!confirm(`Crear administrador "${form.username}" con rol "${form.role}"? Tendra acceso al panel segun el rol asignado. Se registra en auditoria.`)) return;
    await api.post("/auth/admins", form);
    setShowForm(false); setForm({ username: "", password: "", display_name: "", role: "admin" }); load();
  };
  const del = async (id: number, name: string) => {
    if (!confirm(`PRECAUCION: Eliminar administrador "${name}"? Perdera acceso al panel inmediatamente. Esta accion no se puede deshacer. Se registra en auditoria.`)) return;
    await api.del(`/auth/admins/${id}`); load();
  };

  const roleColors: Record<string, string> = {
    superadmin: "bg-red-50 text-ms-red", admin: "bg-ms-blue-lighter text-ms-blue", viewer: "bg-ms-gray-20 text-ms-gray-90",
  };

  if (user?.role !== "superadmin") return <div className="p-8 text-ms-red">Acceso restringido a superadmins</div>;

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ms-gray-130" title="Gestion de administradores del panel. Solo accesible por superadmins.">Administradores</h1>
        <button onClick={() => setShowForm(!showForm)} title="Crea un nuevo usuario administrador del panel. Tendra acceso segun el rol asignado. Se registra en auditoria." className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark">+ Nuevo admin</button>
      </div>

      {showForm && (
        <div className="bg-white rounded border border-ms-gray-30 p-5 grid grid-cols-2 gap-3">
          <input placeholder="username" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} title="Nombre de usuario para el nuevo administrador. Debe ser unico." className="px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
          <input type="password" placeholder="Contraseña (min 8)" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} title="Contraseña del nuevo administrador. Mínimo 8 caracteres." className="px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
          <input placeholder="Nombre para mostrar" value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} title="Nombre visible del administrador en el panel." className="px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} title="superadmin: control total. admin: gestion sin configuración critica. viewer: solo lectura." className="px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue">
            <option value="viewer">Viewer (solo lectura)</option>
            <option value="admin">Admin (gestion)</option>
            <option value="superadmin">Superadmin (total)</option>
          </select>
          <div className="col-span-2 flex gap-2">
            <button onClick={create} title="Crea un nuevo usuario administrador del panel. Tendra acceso segun el rol asignado. Se registra en auditoria." className="px-4 py-2 bg-ms-blue text-white rounded text-sm">Crear administrador</button>
            <button onClick={() => setShowForm(false)} title="Cancela la creación del nuevo administrador. No se guarda nada." className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90">Cancelar</button>
          </div>
        </div>
      )}

      <div className="bg-white rounded border border-ms-gray-30 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-ms-gray-20 border-b border-ms-gray-30"><tr>
            <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Usuario</th>
            <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Nombre</th>
            <th className="text-center px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Rol</th>
            <th className="text-center px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Estado</th>
            <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Último login</th>
            <th className="text-right px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Acciones</th>
          </tr></thead>
          <tbody className="divide-y divide-ms-gray-30">
            {admins.map((a) => (
              <tr key={a.id} className="hover:bg-ms-blue-lighter/50">
                <td className="px-4 py-2.5 font-medium text-ms-gray-130">{a.username}</td>
                <td className="px-4 py-2.5 text-ms-gray-60">{a.display_name}</td>
                <td className="px-4 py-2.5 text-center"><span className={`px-2 py-0.5 rounded text-[10px] font-medium ${roleColors[a.role]}`} title={`Rol: ${a.role}. superadmin: control total. admin: gestion sin configuración critica. viewer: solo lectura.`}>{a.role}</span></td>
                <td className="px-4 py-2.5 text-center"><span className={`px-2 py-0.5 rounded text-[10px] font-medium ${a.active ? "bg-green-50 text-ms-green" : "bg-red-50 text-ms-red"}`} title={a.active ? "El administrador esta activo y puede acceder al panel." : "El administrador esta inactivo y no puede acceder al panel."}>{a.active ? "Activo" : "Inactivo"}</span></td>
                <td className="px-4 py-2.5 text-xs text-ms-gray-60">{a.last_login ? new Date(a.last_login).toLocaleString() : "Nunca"}</td>
                <td className="px-4 py-2.5 text-right">{a.id !== user?.id && <button onClick={() => del(a.id, a.username)} title="PRECAUCION: Elimina el administrador. Perdera acceso al panel inmediatamente. Se registra en auditoria." className="text-ms-red text-xs hover:underline">Eliminar</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="bg-ms-blue-lighter rounded border border-ms-blue/20 p-4 text-sm text-ms-blue" title="Descripcion de los roles de administrador disponibles en el panel.">
        <strong>Roles:</strong> <span className="text-xs">Viewer = solo lectura | Admin = gestiona buzónes, alias, dominios | Superadmin = todo + gestionar admins + eliminar</span>
      </div>
    </div>
  );
}
