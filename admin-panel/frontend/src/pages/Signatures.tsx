import { useEffect, useState } from "react";
import { api } from "../api/client";

interface Template { id: number; name: string; description: string; html_content: string; text_content: string; is_default: boolean; domain: string }
interface UserSig { id: number; username: string; signature_id: number; custom_name: string; custom_title: string; custom_phone: string; template_name: string; user_fullname: string }

export function Signatures() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [userSigs, setUserSigs] = useState<UserSig[]>([]);
  const [tab, setTab] = useState<"templates" | "users">("templates");
  const [editing, setEditing] = useState<Template | null>(null);
  const [form, setForm] = useState({ name: "", description: "", html_content: "", domain: "", is_default: false });
  const [preview, setPreview] = useState("");
  const [assignForm, setAssignForm] = useState({ username: "", signature_id: 0, custom_name: "", custom_title: "", custom_phone: "" });

  const loadTemplates = () => api.get<Template[]>("/signatures/templates").then(setTemplates).catch(() => {});
  const loadUsers = () => api.get<UserSig[]>("/signatures/users").then(setUserSigs).catch(() => {});
  useEffect(() => { loadTemplates(); loadUsers(); }, []);

  const saveTemplate = async () => {
    if (!form.name.trim()) {
      alert("El nombre de la plantilla es obligatorio.");
      return;
    }
    if (editing) {
      await api.put(`/signatures/templates/${editing.id}`, form);
    } else {
      await api.post("/signatures/templates", form);
    }
    setEditing(null); setForm({ name: "", description: "", html_content: "", domain: "", is_default: false });
    loadTemplates();
  };

  const editTemplate = (t: Template) => {
    setEditing(t);
    setForm({ name: t.name, description: t.description, html_content: t.html_content, domain: t.domain, is_default: t.is_default });
    setTab("templates");
  };

  const deleteTemplate = async (id: number) => {
    if (!confirm("PRECAUCION: Esto eliminara la plantilla permanentemente. Los usuarios asignados perderan su firma. Esta accion se registra en auditoria. ¿Continuar?")) return;
    await api.del(`/signatures/templates/${id}`);
    loadTemplates();
  };

  const assign = async () => {
    await api.post("/signatures/users", assignForm);
    setAssignForm({ username: "", signature_id: 0, custom_name: "", custom_title: "", custom_phone: "" });
    loadUsers();
  };

  const showPreview = async (sigId: number) => {
    const res: any = await api.get(`/signatures/preview/${sigId}`);
    setPreview(res.html);
  };

  const defaultSig = `<table style="font-family:Arial,sans-serif;font-size:12px;color:#333;border-top:2px solid #0078d4;padding-top:10px;margin-top:20px">
<tr>
  <td style="padding-right:15px;border-right:2px solid #0078d4">
    <img src="LOGO_URL" alt="Logo" style="width:80px">
  </td>
  <td style="padding-left:15px">
    <p style="margin:0;font-size:14px;font-weight:bold;color:#0078d4">{{nombre}}</p>
    <p style="margin:2px 0;font-size:11px;color:#666">{{cargo}}</p>
    <p style="margin:2px 0;font-size:11px">{{email}}</p>
    <p style="margin:2px 0;font-size:11px">{{teléfono}}</p>
    <p style="margin:8px 0 0;font-size:10px;color:#999">Maquita Cushunchic MCCH</p>
  </td>
</tr>
</table>`;

  return (
    <div className="p-6 space-y-5">
      <h1 className="text-xl font-semibold text-ms-gray-130">Firmas de correo</h1>

      <div className="flex border-b border-ms-gray-30">
        <button onClick={() => setTab("templates")} className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px ${tab === "templates" ? "border-ms-blue text-ms-blue" : "border-transparent text-ms-gray-90"}`} title="Ver y administrar las plantillas de firma HTML disponibles.">Plantillas</button>
        <button onClick={() => setTab("users")} className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px ${tab === "users" ? "border-ms-blue text-ms-blue" : "border-transparent text-ms-gray-90"}`} title="Ver y administrar las asignaciones de firmas a usuarios.">Asignaciones</button>
      </div>

      {tab === "templates" && (
        <div className="space-y-4">
          {/* Editor */}
          <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-3">
            <h2 className="text-sm font-semibold text-ms-gray-130">{editing ? "Editar plantilla" : "Nueva plantilla"}</h2>
            <div className="grid grid-cols-3 gap-3">
              <input placeholder="Nombre de la plantilla" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" title="Nombre identificador de la plantilla. Ejemplo: Firma corporativa, Firma comercial." />
              <input placeholder="Descripcion" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" title="Descripcion opcional para identificar el uso de esta plantilla." />
              <input placeholder="Dominio (opcional)" value={form.domain} onChange={(e) => setForm({ ...form, domain: e.target.value })} className="px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" title="Si especifica un dominio, la plantilla solo estara disponible para usuarios de ese dominio. Dejar vacio para todos." />
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-medium text-ms-gray-90">Contenido HTML</label>
                <button onClick={() => setForm({ ...form, html_content: defaultSig })} className="text-[10px] text-ms-blue hover:underline" title="Carga un HTML de ejemplo con el formato de firma corporativa. Puede editarlo despues. Reemplazara el contenido actual del editor.">Usar plantilla ejemplo</button>
              </div>
              <textarea value={form.html_content} onChange={(e) => setForm({ ...form, html_content: e.target.value })}
                rows={8} placeholder="HTML de la firma... Variables: {{nombre}}, {{email}}, {{cargo}}, {{teléfono}}, {{dominio}}"
                className="w-full px-3 py-2 border border-ms-gray-40 rounded text-xs font-mono focus:outline-none focus:border-ms-blue" title="Ingrese el codigo HTML de la firma. Use las variables {{nombre}}, {{email}}, {{cargo}}, {{teléfono}}, {{dominio}} para personalizacion automatica por usuario." />
            </div>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-1.5 text-sm text-ms-gray-130" title="Si marca como default, se asignara automaticamente a nuevos usuarios del dominio. Solo puede haber una plantilla por defecto por dominio.">
                <input type="checkbox" checked={form.is_default} onChange={(e) => setForm({ ...form, is_default: e.target.checked })} className="accent-ms-blue" title="Si marca como default, se asignara automaticamente a nuevos usuarios del dominio. Solo puede haber una plantilla por defecto por dominio." />
                Plantilla por defecto
              </label>
            </div>
            <div className="flex gap-2">
              <button onClick={saveTemplate} className="px-4 py-2 bg-ms-blue text-white rounded text-sm" title={editing ? "Guarda los cambios realizados en la plantilla. Los usuarios asignados veran la firma actualizada. Se registra en auditoria." : "Crea una nueva plantilla de firma HTML. Use las variables {{nombre}}, {{email}}, etc. para personalizacion automatica. Se registra en auditoria."}>{editing ? "Guardar cambios" : "Crear plantilla"}</button>
              {editing && <button onClick={() => { setEditing(null); setForm({ name: "", description: "", html_content: "", domain: "", is_default: false }); }} className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90" title="Cancela la edicion y limpia el formulario. Los cambios no guardados se perderan.">Cancelar</button>}
            </div>
          </div>

          {/* Preview - NOTA: Se usa dangerouslySetInnerHTML para renderizar la vista previa del HTML de firma.
              El contenido proviene del formulario del administrador, no de usuarios externos. */}
          {form.html_content && (
            <div className="bg-white rounded border border-ms-gray-30 p-4">
              <h3 className="text-xs font-semibold text-ms-gray-90 mb-2">Vista previa</h3>
              <p className="text-[10px] text-yellow-600 mb-2">Nota: Esta vista previa renderiza HTML directamente. Asegurese de que el contenido sea confiable.</p>
              <div className="border border-ms-gray-30 rounded p-3" dangerouslySetInnerHTML={{ __html: form.html_content }} />
            </div>
          )}

          {/* Template list */}
          <div className="bg-white rounded border border-ms-gray-30 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-ms-gray-20 border-b border-ms-gray-30"><tr>
                <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Nombre</th>
                <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Descripcion</th>
                <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Dominio</th>
                <th className="text-center px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Default</th>
                <th className="text-right px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Acciones</th>
              </tr></thead>
              <tbody className="divide-y divide-ms-gray-30">
                {templates.map((t) => (
                  <tr key={t.id} className="hover:bg-ms-blue-lighter/50">
                    <td className="px-4 py-2.5 font-medium text-ms-gray-130">{t.name || <span className="text-ms-red text-xs italic">Sin nombre (editar para corregir)</span>}</td>
                    <td className="px-4 py-2.5 text-ms-gray-60 text-xs">{t.description || "-"}</td>
                    <td className="px-4 py-2.5 text-ms-gray-60 text-xs">{t.domain || "Todos"}</td>
                    <td className="px-4 py-2.5 text-center">{t.is_default && <span className="text-[10px] px-1.5 py-0.5 bg-ms-blue-lighter text-ms-blue rounded" title="Esta plantilla se asigna automaticamente a nuevos usuarios del dominio.">Default</span>}</td>
                    <td className="px-4 py-2.5 text-right space-x-2">
                      <button onClick={() => editTemplate(t)} className="text-ms-blue text-xs hover:underline" title="Abre esta plantilla en el editor para modificar su contenido HTML, nombre o configuración. Se registra en auditoria.">Editar</button>
                      <button onClick={() => deleteTemplate(t.id)} className="text-ms-red text-xs hover:underline" title="PRECAUCION: Elimina la plantilla permanentemente. Los usuarios asignados perderan su firma. Se registra en auditoria. Se pedira confirmación.">Eliminar</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {templates.length === 0 && <div className="p-6 text-center text-ms-gray-60 text-sm">Sin plantillas. Crea la primera.</div>}
          </div>
        </div>
      )}

      {tab === "users" && (
        <div className="space-y-4">
          <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-3">
            <h2 className="text-sm font-semibold text-ms-gray-130">Asignar firma a usuario</h2>
            <div className="grid grid-cols-2 gap-3">
              <input placeholder="usuario@dominio" value={assignForm.username} onChange={(e) => setAssignForm({ ...assignForm, username: e.target.value })} className="px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" title="Email completo del usuario al que se asignara la firma. Ejemplo: jperez@dominio.com" />
              <select value={assignForm.signature_id} onChange={(e) => setAssignForm({ ...assignForm, signature_id: +e.target.value })} className="px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" title="Seleccione la plantilla de firma que se asignara al usuario. Debe crear plantillas primero en la pestana Plantillas.">
                <option value={0}>Seleccionar plantilla...</option>
                {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
              <input placeholder="Nombre personalizado" value={assignForm.custom_name} onChange={(e) => setAssignForm({ ...assignForm, custom_name: e.target.value })} className="px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" title="Nombre que aparecera en la firma. Si se deja vacio, se usara el nombre del usuario en el sistema." />
              <input placeholder="Cargo" value={assignForm.custom_title} onChange={(e) => setAssignForm({ ...assignForm, custom_title: e.target.value })} className="px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" title="Cargo o titulo del usuario que aparecera en la firma. Ejemplo: Gerente Comercial." />
              <input placeholder="Teléfono" value={assignForm.custom_phone} onChange={(e) => setAssignForm({ ...assignForm, custom_phone: e.target.value })} className="px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" title="Número de teléfono que aparecera en la firma del usuario." />
              <button onClick={assign} className="px-4 py-2 bg-ms-blue text-white rounded text-sm" title="Asigna esta plantilla de firma al usuario seleccionado. Se aplicara automaticamente en sus correos. Se registra en auditoria.">Asignar firma</button>
            </div>
          </div>

          <div className="bg-white rounded border border-ms-gray-30 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-ms-gray-20 border-b border-ms-gray-30"><tr>
                <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Usuario</th>
                <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Nombre</th>
                <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Plantilla</th>
                <th className="text-left px-4 py-2.5 font-medium text-ms-gray-90 text-xs">Cargo</th>
              </tr></thead>
              <tbody className="divide-y divide-ms-gray-30">
                {userSigs.map((u) => (
                  <tr key={u.id} className="hover:bg-ms-blue-lighter/50">
                    <td className="px-4 py-2.5 font-medium text-ms-gray-130">{u.username}</td>
                    <td className="px-4 py-2.5 text-ms-gray-60">{u.custom_name || u.user_fullname || "-"}</td>
                    <td className="px-4 py-2.5 text-xs"><span className="px-1.5 py-0.5 bg-ms-blue-lighter text-ms-blue rounded">{u.template_name || "-"}</span></td>
                    <td className="px-4 py-2.5 text-ms-gray-60 text-xs">{u.custom_title || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {userSigs.length === 0 && <div className="p-6 text-center text-ms-gray-60 text-sm">Sin firmas asignadas</div>}
          </div>
        </div>
      )}

      <div className="bg-ms-blue-lighter rounded border border-ms-blue/20 p-4 text-xs text-ms-blue" title="Referencia rapida de variables disponibles para usar en las plantillas de firma HTML.">
        <strong>Variables disponibles:</strong> {"{{nombre}}"}, {"{{email}}"}, {"{{cargo}}"}, {"{{teléfono}}"}, {"{{dominio}}"} - Se reemplazan automaticamente con los datos del usuario
      </div>
    </div>
  );
}
