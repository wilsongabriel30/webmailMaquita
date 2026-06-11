import { useEffect, useState } from "react";
import { api } from "../api/client";

interface Mailbox { username: string; name: string; domain: string; quota: number; active: boolean; phone: string; email_other: string; created: string }

export function Mailboxes() {
  const [mailboxes, setMailboxes] = useState<Mailbox[]>([]);
  const [quotas, setQuotas] = useState<Record<string, any>>({});
  const [filter, setFilter] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ username: "", password: "", password2: "", name: "", quota_mb: 0 });
  const [editPw, setEditPw] = useState<string | null>(null);
  const [newPw, setNewPw] = useState("");
  const [newPw2, setNewPw2] = useState("");

  // Grupos del usuario
  const [groupsUser, setGroupsUser] = useState<string | null>(null);
  const [userGroups, setUserGroups] = useState<any[]>([]);
  const [groupsLoading, setGroupsLoading] = useState(false);

  const loadUserGroups = async (username: string) => {
    if (groupsUser === username) { setGroupsUser(null); return; }
    setGroupsUser(username);
    setGroupsLoading(true);
    try {
      const data = await api.get<any[]>(`/groups/by-member?email=${encodeURIComponent(username)}`);
      setUserGroups(data);
    } catch { setUserGroups([]); }
    setGroupsLoading(false);
  };

  // Cambiar titular
  const [titularUser, setTitularUser] = useState<string | null>(null);
  const [titularForm, setTitularForm] = useState({ new_name: "", new_password: "", new_password2: "", new_cargo: "", new_phone: "", send_notification: true, notification_message: "" });
  const [titularLoading, setTitularLoading] = useState(false);
  const [titularResult, setTitularResult] = useState<any>(null);

  const load = () => { api.get<Mailbox[]>("/mailboxes").then(setMailboxes); api.get<Record<string, any>>("/mailboxes/quota/all").then(setQuotas).catch(() => {}); };
  useEffect(() => { load(); }, []);

  const [createError, setCreateError] = useState("");
  const [createNc, setCreateNc] = useState(true);
  const [ncStatus, setNcStatus] = useState<string>("");
  const create = async () => {
    setCreateError("");
    if (!form.username || !form.username.includes("@")) { setCreateError("Ingrese una dirección valida: usuario@dominio.com"); return; }
    if (!form.name.trim()) { setCreateError("El nombre completo es obligatorio"); return; }
    if (form.password.length < 6) { setCreateError("La contraseña debe tener mínimo 6 caracteres"); return; }
    if (form.password !== form.password2) { setCreateError("Las contraseñas no coinciden"); return; }
    try {
      await api.post("/mailboxes", { username: form.username, password: form.password, name: form.name, quota: form.quota_mb * 1048576 });
      // Crear cuenta Nextcloud si el switch esta activo
      if (createNc) {
        try {
          const local = form.username.split("@")[0];
          const ncUserId = local.replace(/[^a-zA-Z0-9._-]/g, "").toLowerCase();
          await api.post("/nextcloud/users", {
            userid: ncUserId,
            password: form.password,
            displayName: form.name,
            email: form.username,
            quota: "5 GB",
          });
          setNcStatus("Cuenta Nextcloud creada: " + ncUserId);
        } catch (ncErr: any) {
          setNcStatus("Buzon creado, pero Nextcloud fallo: " + (ncErr?.message || "error"));
        }
      }
      setShowForm(false); setForm({ username: "", password: "", password2: "", name: "", quota_mb: 0 }); load();
    } catch (e: any) {
      setCreateError(e.message || "Error al crear el buzón");
    }
  };
  const toggle = async (u: string) => { await api.post(`/mailboxes/${u}/toggle-active`); load(); };
  const del = async (u: string) => { if (confirm(`PRECAUCION EXTREMA: Se eliminara el buzón ${u} y TODOS sus correos permanentemente. Esta accion NO se puede deshacer. Continuar?`)) { await api.del(`/mailboxes/${u}`); load(); } };
  const changePw = async (u: string) => {
    if (newPw.length < 6) { alert("Mínimo 6 caracteres"); return; }
    if (newPw !== newPw2) { alert("Las contraseñas no coinciden. Escriba la misma contraseña en ambos campos."); return; }
    try {
      await api.put(`/mailboxes/${encodeURIComponent(u)}`, { password: newPw });
      setEditPw(null); setNewPw(""); setNewPw2(""); alert("Contraseña actualizada correctamente para: " + u);
    } catch (e: any) {
      alert("Error al cambiar contraseña: " + (e.message || "Error desconocido"));
    }
  };

  const impersonate = async (u: string) => {
    try {
      const res: any = await api.post(`/mailboxes/${u}/impersonate`);
      // Open webmail with impersonate token as query param
      // The webmail login page will detect the token and auto-authenticate
      const token = encodeURIComponent(res.token);
      const user = encodeURIComponent(u);
      window.open(
        `${window.location.protocol}//${window.location.hostname}/webmail/?impersonate=${token}&user=${user}`,
        "_blank"
      );
    } catch (e: any) {
      alert("Error: " + (e.message || "No se pudo impersonar"));
    }
  };

  const cambiarTitular = async () => {
    if (!titularUser) return;
    if (!titularForm.new_name.trim()) { alert("El nombre del nuevo titular es obligatorio"); return; }
    if (titularForm.new_password.length < 6) { alert("La contraseña debe tener mínimo 6 caracteres"); return; }
    if (titularForm.new_password !== titularForm.new_password2) { alert("Las contraseñas no coinciden"); return; }
    if (!confirm(
      `Va a cambiar el titular de ${titularUser}.\n\n` +
      `Esto hara:\n` +
      `- Cambiar el nombre visible a: ${titularForm.new_name}\n` +
      `- Cambiar la contraseña (el anterior titular perdera acceso)\n` +
      `- Actualizar la firma si tiene plantilla\n` +
      (titularForm.send_notification ? `- Enviar correo de notificación a contactos internos\n` : "") +
      `\nTodo queda registrado en auditoria. Continuar?`
    )) return;

    setTitularLoading(true);
    try {
      const res: any = await api.post(`/mailboxes/${titularUser}/cambiar-titular`, {
        new_name: titularForm.new_name,
        new_password: titularForm.new_password,
        new_cargo: titularForm.new_cargo,
        new_phone: titularForm.new_phone,
        send_notification: titularForm.send_notification,
        notification_message: titularForm.notification_message,
      });
      setTitularResult(res);
      load();
    } catch (e: any) {
      alert(`Error: ${e.message}`);
    }
    setTitularLoading(false);
  };

  const closeTitular = () => {
    setTitularUser(null);
    setTitularForm({ new_name: "", new_password: "", new_password2: "", new_cargo: "", new_phone: "", send_notification: true, notification_message: "" });
    setTitularResult(null);
  };

  const filtered = mailboxes.filter((m) => !filter || m.username.toLowerCase().includes(filter.toLowerCase()) || m.name?.toLowerCase().includes(filter.toLowerCase()));
  const formatQuota = (q: number) => q > 0 ? `${(q / 1048576).toFixed(0)} MB` : "Sin límite";

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ms-gray-130">Buzones ({mailboxes.length})</h1>
        <button onClick={() => setShowForm(!showForm)} title="Crea un nuevo buzón de correo. El usuario podra enviar y recibir correos inmediatamente. Se registra en auditoria." className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark">+ Nuevo buzón</button>
      </div>

      <input placeholder="Buscar por nombre o email..." value={filter} onChange={(e) => setFilter(e.target.value)} title="Filtra la lista de buzones por nombre o dirección de correo."
        className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm bg-white focus:outline-none focus:border-ms-blue focus:ring-1 focus:ring-ms-blue" />

      {showForm && (
        <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-4">
          {createError && (
            <div className="bg-red-50 border border-red-200 rounded p-3 text-sm text-red-700">{createError}</div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-ms-gray-90 mb-1 block">Dirección de correo *</label>
              <input placeholder="usuario@ejemplo.com" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value.toLowerCase() })}
                className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
              <span className="text-[10px] text-ms-gray-60 mt-0.5 block">Ejemplo: juan.perez@ejemplo.com</span>
            </div>
            <div>
              <label className="text-xs font-medium text-ms-gray-90 mb-1 block">Nombre completo *</label>
              <input placeholder="Juan Perez" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
              <span className="text-[10px] text-ms-gray-60 mt-0.5 block">Aparece como remitente en los correos</span>
            </div>
            <div>
              <label className="text-xs font-medium text-ms-gray-90 mb-1 block">Contraseña *</label>
              <input type="password" autoComplete="new-password" placeholder="Mínimo 6 caracteres" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })}
                className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
            </div>
            <div>
              <label className="text-xs font-medium text-ms-gray-90 mb-1 block">Confirmar contraseña *</label>
              <input type="password" autoComplete="new-password" placeholder="Repita la contraseña" value={form.password2} onChange={(e) => setForm({ ...form, password2: e.target.value })}
                className={`w-full px-3 py-2 border rounded text-sm focus:outline-none focus:border-ms-blue ${form.password2 && form.password !== form.password2 ? "border-red-400 bg-red-50" : "border-ms-gray-40"}`} />
              {form.password2 && form.password !== form.password2 && (
                <span className="text-[10px] text-red-500 mt-0.5 block">Las contraseñas no coinciden</span>
              )}
            </div>
            <div>
              <label className="text-xs font-medium text-ms-gray-90 mb-1 block">Cuota (MB)</label>
              <input type="number" placeholder="0" value={form.quota_mb} onChange={(e) => setForm({ ...form, quota_mb: +e.target.value })}
                className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
              <span className="text-[10px] text-ms-gray-60 mt-0.5 block">0 = sin límite. Ej: 2048 = 2 GB</span>
            </div>
            <div className="flex items-center gap-3 pt-2">
              <label className="flex items-center gap-2 text-sm text-ms-gray-130 cursor-pointer">
                <div className="relative">
                  <input type="checkbox" checked={createNc} onChange={(e) => setCreateNc(e.target.checked)}
                    className="sr-only" />
                  <div className={`w-10 h-5 rounded-full transition-colors ${createNc ? "bg-ms-blue" : "bg-ms-gray-40"}`}>
                    <div className={`w-4 h-4 bg-white rounded-full shadow transform transition-transform mt-0.5 ${createNc ? "translate-x-5 ml-0.5" : "translate-x-0.5"}`} />
                  </div>
                </div>
                <div>
                  <span className="text-xs font-medium">Crear cuenta Nextcloud</span>
                  <span className="text-[10px] text-ms-gray-60 block">Acceso a nube.ejemplo.com con 5 GB de almacenamiento</span>
                </div>
              </label>
            </div>
          </div>
          <div className="flex gap-2 pt-1">
            <button onClick={create} className="px-4 py-2 bg-ms-blue text-white rounded text-sm font-medium hover:bg-ms-blue-dark">Crear buzón</button>
            <button onClick={() => { setShowForm(false); setForm({ username: "", password: "", password2: "", name: "", quota_mb: 0 }); setCreateError(""); }} className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90">Cancelar</button>
          </div>
        </div>
      )}

      {ncStatus && (
        <div className={`px-4 py-3 rounded text-sm flex items-center justify-between ${ncStatus.includes("fallo") ? "bg-yellow-50 border border-yellow-200 text-yellow-800" : "bg-green-50 border border-green-200 text-green-700"}`}>
          <span>{ncStatus}</span>
          <button onClick={() => setNcStatus("")} className="text-xs hover:underline ml-2">Cerrar</button>
        </div>
      )}

      {/* Panel de grupos del usuario */}
      {groupsUser && (
        <div className="bg-white rounded border-2 border-purple-300 p-5 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-purple-700">Membresía en grupos</h2>
              <p className="text-xs text-ms-gray-90 mt-0.5">Correo: <span className="font-semibold text-ms-gray-130">{groupsUser}</span></p>
            </div>
            <button onClick={() => setGroupsUser(null)} className="text-ms-gray-60 hover:text-ms-gray-130 text-xs">Cerrar</button>
          </div>

          {groupsLoading ? (
            <div className="text-center text-ms-gray-60 text-sm py-4">Cargando...</div>
          ) : userGroups.length === 0 ? (
            <div className="text-center text-ms-gray-60 text-sm py-4">
              Este correo no pertenece a ningún grupo de distribución.
            </div>
          ) : (
            <div className="space-y-1">
              <p className="text-xs text-ms-gray-90">Miembro de <span className="font-bold text-purple-700">{userGroups.length}</span> grupo(s):</p>
              <table className="w-full text-sm">
                <thead className="bg-purple-50 border-b border-purple-200">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium text-purple-800 text-xs">Grupo</th>
                    <th className="text-left px-3 py-2 font-medium text-purple-800 text-xs">Nombre</th>
                    <th className="text-center px-3 py-2 font-medium text-purple-800 text-xs">Enviar</th>
                    <th className="text-center px-3 py-2 font-medium text-purple-800 text-xs">Recibir</th>
                    <th className="text-center px-3 py-2 font-medium text-purple-800 text-xs">Estado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ms-gray-30">
                  {userGroups.map((g: any) => (
                    <tr key={g.id} className="hover:bg-purple-50/50">
                      <td className="px-3 py-2 text-ms-blue font-medium">{g.address}</td>
                      <td className="px-3 py-2 text-ms-gray-60">{g.name || "-"}</td>
                      <td className="px-3 py-2 text-center">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${g.can_send ? "bg-green-50 text-ms-green" : "bg-red-50 text-ms-red"}`}>
                          {g.can_send ? "Sí" : "No"}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-center">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${g.receive ? "bg-green-50 text-ms-green" : "bg-red-50 text-ms-red"}`}>
                          {g.receive ? "Sí" : "No"}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-center">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${g.active ? "bg-green-50 text-ms-green" : "bg-red-50 text-ms-red"}`}>
                          {g.active ? "Activo" : "Inactivo"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Panel de cambiar titular */}
      {titularUser && (
        <div className="bg-white rounded border-2 border-ms-orange p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-ms-orange">Cambiar titular de cuenta</h2>
              <p className="text-xs text-ms-gray-90 mt-0.5">Buzón: <span className="font-semibold text-ms-gray-130">{titularUser}</span> — Titular actual: <span className="font-semibold">{mailboxes.find(m => m.username === titularUser)?.name || "-"}</span></p>
            </div>
            <button onClick={closeTitular} title="Cierra el panel sin hacer cambios." className="text-ms-gray-60 hover:text-ms-gray-130 text-xs">Cerrar</button>
          </div>

          <div className="bg-yellow-50 border border-yellow-200 rounded p-3 text-xs text-yellow-800">
            <strong>Que hace esta funcion:</strong> Cuando un colaborador sale de la empresa y otro toma su correo, esta funcion cambia el nombre, la contraseña, actualiza la firma y notifica a los contactos para que sus clientes de correo actualicen el nombre en cache.
          </div>

          {titularResult ? (
            <div className="bg-green-50 border border-green-200 rounded p-4 space-y-2">
              <h3 className="text-sm font-semibold text-ms-green">Cambio de titular completado</h3>
              <div className="text-xs text-ms-gray-130 space-y-1">
                <p>Nombre anterior: <span className="line-through text-ms-gray-60">{titularResult.old_name}</span></p>
                <p>Nombre nuevo: <span className="font-semibold">{titularResult.new_name}</span></p>
                <p>Contraseña: <span className="font-semibold text-ms-green">Cambiada</span></p>
                <p>Firma: {titularResult.signature_updated ? <span className="text-ms-green font-semibold">Actualizada</span> : <span className="text-ms-gray-60">Sin plantilla asignada</span>}</p>
                <p>Notificacion: {titularResult.notification_sent ? <span className="text-ms-green font-semibold">Enviada a {titularResult.recipients_count} contactos</span> : <span className="text-ms-gray-60">No enviada</span>}</p>
              </div>
              <p className="text-[10px] text-ms-gray-60 mt-2">Todo registrado en auditoria. Puede revertir restaurando el nombre anterior desde esta misma página.</p>
              <button onClick={closeTitular} className="px-3 py-1.5 bg-ms-blue text-white rounded text-xs mt-2">Cerrar</button>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[10px] font-medium text-ms-gray-90 mb-1 block">Nombre del nuevo titular *</label>
                <input value={titularForm.new_name} onChange={(e) => setTitularForm({ ...titularForm, new_name: e.target.value })}
                  placeholder="Nombre completo del nuevo titular"
                  title="Nombre que aparecera como remitente en los correos. Obligatorio."
                  className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
              </div>
              <div>
                <label className="text-[10px] font-medium text-ms-gray-90 mb-1 block">Cargo</label>
                <input value={titularForm.new_cargo} onChange={(e) => setTitularForm({ ...titularForm, new_cargo: e.target.value })}
                  placeholder="Ej: Coordinador de Proyectos"
                  title="Cargo del nuevo titular. Se usa en la firma si tiene plantilla."
                  className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
              </div>
              <div>
                <label className="text-[10px] font-medium text-ms-gray-90 mb-1 block">Nueva contraseña *</label>
                <input type="password" autoComplete="new-password" value={titularForm.new_password} onChange={(e) => setTitularForm({ ...titularForm, new_password: e.target.value })}
                  placeholder="Mínimo 6 caracteres"
                  title="Contraseña para el nuevo titular. El anterior titular perdera acceso inmediatamente."
                  className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
              </div>
              <div>
                <label className="text-[10px] font-medium text-ms-gray-90 mb-1 block">Confirmar contraseña *</label>
                <input type="password" autoComplete="new-password" value={titularForm.new_password2} onChange={(e) => setTitularForm({ ...titularForm, new_password2: e.target.value })}
                  placeholder="Repita la contraseña"
                  title="Escriba la misma contraseña para verificar que no hay errores de escritura."
                  className={`w-full px-3 py-2 border rounded text-sm focus:outline-none focus:border-ms-blue ${titularForm.new_password2 && titularForm.new_password !== titularForm.new_password2 ? "border-ms-red bg-red-50" : "border-ms-gray-40"}`} />
                {titularForm.new_password2 && titularForm.new_password !== titularForm.new_password2 && (
                  <span className="text-[10px] text-ms-red">Las contraseñas no coinciden</span>
                )}
              </div>
              <div>
                <label className="text-[10px] font-medium text-ms-gray-90 mb-1 block">Teléfono</label>
                <input value={titularForm.new_phone} onChange={(e) => setTitularForm({ ...titularForm, new_phone: e.target.value })}
                  placeholder="Ej: +593 99 123 4567"
                  title="Teléfono del nuevo titular. Se usa en la firma si tiene plantilla."
                  className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
              </div>
              <div className="flex items-end pb-2">
                <label className="flex items-center gap-2 text-sm text-ms-gray-130">
                  <input type="checkbox" checked={titularForm.send_notification} onChange={(e) => setTitularForm({ ...titularForm, send_notification: e.target.checked })}
                    title="Envia un correo a todos los companeros informando el cambio de titular. Esto fuerza a los clientes de correo a actualizar el nombre en cache."
                    className="accent-ms-blue" />
                  <span className="text-xs">Notificar a contactos internos</span>
                </label>
              </div>
              {titularForm.send_notification && (
                <div className="col-span-2">
                  <label className="text-[10px] font-medium text-ms-gray-90 mb-1 block">Mensaje personalizado (opcional)</label>
                  <textarea value={titularForm.notification_message} onChange={(e) => setTitularForm({ ...titularForm, notification_message: e.target.value })}
                    rows={3} placeholder="Dejar vacio para usar el mensaje predeterminado: 'Les informamos que el buzón ha sido asignado a [nombre]...'"
                    title="Si deja vacio, se envia un mensaje estandar informando el cambio. Si escribe algo, se usa este texto."
                    className="w-full px-3 py-2 border border-ms-gray-40 rounded text-xs focus:outline-none focus:border-ms-blue" />
                </div>
              )}
              <div className="col-span-2 flex gap-2 pt-2">
                <button onClick={cambiarTitular} disabled={titularLoading}
                  title="Ejecuta el cambio de titular: nombre, contraseña, firma y notificación. TODO queda registrado en auditoria para poder revertirlo."
                  className="px-4 py-2 bg-ms-orange text-white rounded text-sm font-medium hover:bg-orange-700 disabled:opacity-50">
                  {titularLoading ? "Procesando..." : "Cambiar titular"}
                </button>
                <button onClick={closeTitular} title="Cancela sin hacer cambios." className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90">Cancelar</button>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="bg-white rounded border border-ms-gray-30 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-ms-gray-20 border-b border-ms-gray-30">
            <tr>
              <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Email</th>
              <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Nombre</th>
              <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Dominio</th>
              <th className="text-center px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Cuota</th>
              <th className="text-center px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Uso</th>
              <th className="text-center px-4 py-2.5 font-medium text-ms-gray-90 text-xs" title="Activo = puede enviar/recibir. Inactivo = bloqueado.">Estado</th>
              <th className="text-right px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ms-gray-30">
            {filtered.map((m) => (
              <tr key={m.username} className="hover:bg-ms-blue-lighter/50">
                <td className="px-4 py-2.5 font-medium text-ms-gray-130">{m.username}</td>
                <td className="px-4 py-2.5 text-ms-gray-60">{m.name || "-"}</td>
                <td className="px-4 py-2.5 text-ms-gray-60">{m.domain}</td>
                <td className="px-4 py-2.5 text-center text-xs">{formatQuota(m.quota)}</td>
                <td className="px-4 py-2.5 text-center text-xs">
                  {quotas[m.username] ? (
                    <div title={`${quotas[m.username].messages} mensajes`}>
                      <span className={`font-medium ${quotas[m.username].percent > 90 ? "text-ms-red" : quotas[m.username].percent > 70 ? "text-yellow-600" : "text-ms-gray-90"}`}>
                        {(quotas[m.username].used_bytes / 1048576).toFixed(0)} MB
                      </span>
                      {quotas[m.username].limit_bytes > 0 && (
                        <div className="w-16 h-1.5 bg-ms-gray-30 rounded-full mt-0.5 mx-auto">
                          <div className={`h-full rounded-full ${quotas[m.username].percent > 90 ? "bg-ms-red" : quotas[m.username].percent > 70 ? "bg-yellow-500" : "bg-ms-green"}`} style={{width: `${Math.min(quotas[m.username].percent, 100)}%`}} />
                        </div>
                      )}
                    </div>
                  ) : <span className="text-ms-gray-40">—</span>}
                </td>
                <td className="px-4 py-2.5 text-center">
                  <button onClick={() => toggle(m.username)} title={m.active ? "Clic para DESACTIVAR. El usuario no podra enviar ni recibir. Se registra en auditoria." : "Clic para ACTIVAR. El usuario podra enviar y recibir. Se registra en auditoria."} className={`px-2 py-0.5 rounded text-[10px] font-medium ${m.active ? "bg-green-50 text-ms-green" : "bg-red-50 text-ms-red"}`}>
                    {m.active ? "Activo" : "Inactivo"}
                  </button>
                </td>
                <td className="px-4 py-2.5 text-right space-x-1">
                  <button onClick={() => impersonate(m.username)}
                    title="Abrir el buzón de este usuario en el webmail como administrador"
                    className="text-green-600 hover:underline text-xs font-medium">Abrir buzón</button>
                  <button onClick={() => toggle(m.username)}
                    title={m.active ? "Bloquear cuenta: no podrá enviar ni recibir" : "Desbloquear cuenta"}
                    className={`${m.active ? "text-yellow-600" : "text-green-600"} hover:underline text-xs`}>{m.active ? "Bloquear" : "Activar"}</button>
                  <button onClick={() => { setEditPw(editPw === m.username ? null : m.username); setNewPw(""); setNewPw2(""); }}
                    className="text-ms-blue hover:underline text-xs">Contraseña</button>
                  <button onClick={() => loadUserGroups(m.username)}
                    title="Ver en qué grupos de distribución está este correo"
                    className={`${groupsUser === m.username ? "text-purple-700 font-semibold" : "text-purple-600"} hover:underline text-xs`}>Grupos</button>
                  <button onClick={() => { setTitularUser(titularUser === m.username ? null : m.username); setTitularResult(null); setTitularForm({ new_name: "", new_password: "", new_password2: "", new_cargo: "", new_phone: "", send_notification: true, notification_message: "" }); }}
                    className="text-ms-orange hover:underline text-xs">Titular</button>
                  <button onClick={() => del(m.username)}
                    title="Elimina el buzón y TODOS sus correos permanentemente"
                    className="text-ms-red hover:underline text-xs">Eliminar</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {editPw && (
          <form onSubmit={(e) => { e.preventDefault(); changePw(editPw); }} className="p-4 bg-ms-blue-lighter border-t border-ms-gray-30 space-y-2">
            <span className="text-sm font-medium text-ms-gray-130">Cambiar contraseña de: {editPw}</span>
            <input type="hidden" name="username" autoComplete="username" value={editPw || ""} />
            <div className="flex items-center gap-3">
              <input type="password" placeholder="Nueva contraseña" value={newPw} onChange={(e) => setNewPw(e.target.value)}
                autoComplete="new-password" title="Escriba la nueva contraseña. Mínimo 6 caracteres."
                className="px-3 py-1.5 border border-ms-gray-40 rounded text-sm flex-1 focus:outline-none focus:border-ms-blue" />
              <input type="password" placeholder="Confirmar contraseña" value={newPw2} onChange={(e) => setNewPw2(e.target.value)}
                autoComplete="new-password" title="Repita la contraseña para confirmar."
                className={`px-3 py-1.5 border rounded text-sm flex-1 focus:outline-none focus:border-ms-blue ${newPw2 && newPw !== newPw2 ? "border-ms-red bg-red-50" : "border-ms-gray-40"}`} />
              <button type="submit"
                title="Aplica la nueva contraseña inmediatamente. Se registra en auditoria."
                className="px-4 py-1.5 bg-ms-blue text-white rounded text-sm">Cambiar</button>
              <button onClick={() => setEditPw(null)}
                title="Cancela sin cambiar la contraseña."
                className="px-4 py-1.5 border border-ms-gray-40 rounded text-sm text-ms-gray-90">Cancelar</button>
            </div>
            {newPw2 && newPw !== newPw2 && <span className="text-[10px] text-ms-red">Las contraseñas no coinciden</span>}
          </form>
        )}
      </div>
    </div>
  );
}
