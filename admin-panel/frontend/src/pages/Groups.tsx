import { useEffect, useState, useRef } from "react";
import { api } from "../api/client";

interface Group { id: number; address: string; name: string; description: string; domain: string; active: boolean; allow_external: boolean; allowed_senders: string; member_count: number; external_count?: number; nested_group_count?: number }
interface Member { id: number; member_email: string; member_name: string; can_send: boolean; receive: boolean; member_type?: "internal" | "external" | "group" }
interface Suggestion { username: string; name: string }
interface GroupWarning { type: string; severity: string; message: string; emails?: string[]; groups?: string[] }
interface GroupStats { total: number; internal: number; external: number; nested_groups: number }
interface AuditData { external_issues: any[]; nested_issues: any[]; total_external: number; total_nested: number; groups_with_external: number; groups_with_nested: number }

export function Groups() {
  const [groups, setGroups] = useState<Group[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [groupDetail, setGroupDetail] = useState<Group | null>(null);
  const [warnings, setWarnings] = useState<GroupWarning[]>([]);
  const [stats, setStats] = useState<GroupStats | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ address: "", name: "", description: "", allow_external: false });
  const [memberForm, setMemberForm] = useState({ email: "", name: "", can_send: true, receive: true });
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [showSugg, setShowSugg] = useState(false);
  const [showAudit, setShowAudit] = useState(false);
  const [auditData, setAuditData] = useState<AuditData | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const [addError, setAddError] = useState("");
  const [pendingConfirm, setPendingConfirm] = useState<{ type: string; message: string; email: string; name: string } | null>(null);
  const timerRef = useRef<any>(null);
  const [groupSearch, setGroupSearch] = useState("");
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState({ name: "", description: "", allow_external: false, active: true });
  const [memberSearch, setMemberSearch] = useState("");

  const load = () => api.get<Group[]>("/groups").then(setGroups).catch(() => {});
  useEffect(() => { load(); }, []);

  const selectGroup = async (id: number) => {
    setSelected(id);
    setAddError("");
    setPendingConfirm(null);
    setEditing(false);
    setMemberSearch("");
    const res: any = await api.get(`/groups/${id}`);
    setGroupDetail(res.group);
    setMembers(res.members || []);
    setWarnings(res.warnings || []);
    setStats(res.stats || null);
  };

  const createGroup = async () => {
    await api.post("/groups", form);
    setShowForm(false); setForm({ address: "", name: "", description: "", allow_external: false }); load();
  };

  const deleteGroup = async (id: number) => {
    if (!confirm("PRECAUCIÓN: Esto eliminará el grupo y TODOS sus miembros permanentemente. Esta acción se registra en auditoría. ¿Continuar?")) return;
    await api.del(`/groups/${id}`);
    setSelected(null); setGroupDetail(null); setMembers([]); setWarnings([]); setStats(null); load();
  };

  const searchUsers = (q: string) => {
    setMemberForm({ ...memberForm, email: q });
    setAddError("");
    setPendingConfirm(null);
    if (timerRef.current) clearTimeout(timerRef.current);
    if (q.length < 2) { setSuggestions([]); setShowSugg(false); return; }
    timerRef.current = setTimeout(() => {
      api.get<Suggestion[]>(`/mailboxes/search/autocomplete?q=${encodeURIComponent(q)}&limit=8`)
        .then((d) => { setSuggestions(d); setShowSugg(d.length > 0); })
        .catch(() => {});
    }, 300);
  };

  const addMember = async (force = false) => {
    if (!selected || !memberForm.email) return;
    setAddError("");
    try {
      await api.post(`/groups/${selected}/members`, { ...memberForm, force });
      setMemberForm({ email: "", name: "", can_send: true, receive: true });
      setPendingConfirm(null);
      selectGroup(selected);
      load(); // Actualizar contadores
    } catch (e: any) {
      const detail = e?.detail || e?.message || "";
      // Manejar respuestas de confirmación del backend
      if (typeof detail === "object" && detail.requires_confirmation) {
        setPendingConfirm({
          type: detail.type,
          message: detail.message,
          email: memberForm.email,
          name: memberForm.name,
        });
        return;
      }
      if (typeof detail === "object" && detail.type === "external_blocked") {
        setAddError(detail.message);
        return;
      }
      setAddError(typeof detail === "string" ? detail : detail?.message || "Error al agregar miembro");
    }
  };

  const confirmAdd = () => addMember(true);
  const cancelConfirm = () => setPendingConfirm(null);

  const removeMember = async (memberId: number) => {
    if (!selected) return;
    if (!confirm("¿Remover este miembro del grupo? Dejará de recibir correos del grupo. Se registra en auditoría.")) return;
    await api.del(`/groups/${selected}/members/${memberId}`);
    selectGroup(selected);
    load();
  };

  const startEdit = () => {
    if (!groupDetail) return;
    setEditForm({
      name: groupDetail.name || "",
      description: groupDetail.description || "",
      allow_external: groupDetail.allow_external,
      active: groupDetail.active,
    });
    setEditing(true);
  };

  const saveEdit = async () => {
    if (!selected) return;
    try {
      await api.put(`/groups/${selected}`, editForm);
      setEditing(false);
      selectGroup(selected);
      load();
    } catch (e: any) {
      const msg = e?.detail || e?.message || "Error al guardar";
      alert(typeof msg === "object" ? msg.message || JSON.stringify(msg) : msg);
    }
  };

  const cancelEdit = () => setEditing(false);

  const togglePerm = async (memberId: number, field: "can_send" | "receive", value: boolean) => {
    if (!selected) return;
    await api.put(`/groups/${selected}/members/${memberId}`, { [field]: value });
    selectGroup(selected);
  };

  const runAudit = async () => {
    setAuditLoading(true);
    try {
      const data = await api.get<AuditData>("/groups/audit");
      setAuditData(data);
      setShowAudit(true);
    } catch { setAuditData(null); }
    setAuditLoading(false);
  };

  // Helpers de estilo por tipo
  const memberTypeStyle = (type?: string) => {
    switch (type) {
      case "external": return "bg-red-50 text-ms-red border border-ms-red/20";
      case "group": return "bg-purple-50 text-purple-700 border border-purple-200";
      default: return "";
    }
  };
  const memberTypeBadge = (type?: string) => {
    switch (type) {
      case "external": return <span className="ml-1.5 px-1.5 py-0.5 rounded text-[9px] font-bold bg-red-100 text-ms-red border border-ms-red/30">EXTERNO</span>;
      case "group": return <span className="ml-1.5 px-1.5 py-0.5 rounded text-[9px] font-bold bg-purple-100 text-purple-700 border border-purple-200">GRUPO</span>;
      default: return null;
    }
  };

  // Indicadores en la lista de grupos
  const groupAlerts = (g: Group) => {
    const alerts = [];
    if ((g.external_count || 0) > 0)
      alerts.push(<span key="ext" className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-red-100 text-ms-red" title={`${g.external_count} miembro(s) externo(s) — correos llegan fuera de la organización`}>{g.external_count} ext.</span>);
    if ((g.nested_group_count || 0) > 0)
      alerts.push(<span key="nest" className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-purple-100 text-purple-700" title={`${g.nested_group_count} subgrupo(s) anidado(s) — expansión recursiva de destinatarios`}>{g.nested_group_count} subgr.</span>);
    return alerts;
  };

  const hasIssues = (g: Group) => (g.external_count || 0) > 0 || (g.nested_group_count || 0) > 0;

  const filteredGroups = groupSearch.trim()
    ? groups.filter(g =>
        g.address.toLowerCase().includes(groupSearch.toLowerCase()) ||
        g.name.toLowerCase().includes(groupSearch.toLowerCase()) ||
        (g.description || '').toLowerCase().includes(groupSearch.toLowerCase())
      )
    : groups;

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ms-gray-130">Grupos de distribución</h1>
        <div className="flex gap-2">
          <button onClick={runAudit} disabled={auditLoading}
            className="px-3 py-1.5 border border-yellow-400 text-yellow-700 bg-yellow-50 rounded text-sm hover:bg-yellow-100 disabled:opacity-50"
            title="Ejecuta una auditoría completa de todos los grupos: detecta miembros externos y grupos anidados que pueden causar fugas de información.">
            {auditLoading ? "Auditando..." : "Auditar grupos"}
          </button>
          <button onClick={() => setShowForm(!showForm)} className="px-3 py-1.5 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark" title="Crea un nuevo grupo de distribución.">+ Nuevo grupo</button>
        </div>
      </div>

      {/* Panel de auditoría */}
      {showAudit && auditData && (
        <div className="bg-white rounded border border-yellow-300 p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-yellow-800 flex items-center gap-2">
              <span className="text-lg">⚠</span> Resultado de auditoría de grupos
            </h2>
            <button onClick={() => setShowAudit(false)} className="text-ms-gray-60 text-xs hover:text-ms-gray-130">Cerrar</button>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className={`rounded border p-3 ${auditData.total_external > 0 ? "bg-red-50 border-ms-red/30" : "bg-green-50 border-green-200"}`}>
              <p className="text-[10px] font-medium uppercase opacity-75">Miembros externos</p>
              <p className="text-2xl font-bold">{auditData.total_external}</p>
              <p className="text-[10px] opacity-75">en {auditData.groups_with_external} grupo(s)</p>
            </div>
            <div className={`rounded border p-3 ${auditData.total_nested > 0 ? "bg-purple-50 border-purple-200" : "bg-green-50 border-green-200"}`}>
              <p className="text-[10px] font-medium uppercase opacity-75">Grupos anidados</p>
              <p className="text-2xl font-bold">{auditData.total_nested}</p>
              <p className="text-[10px] opacity-75">en {auditData.groups_with_nested} grupo(s)</p>
            </div>
          </div>

          {auditData.external_issues.length > 0 && (
            <div>
              <h3 className="text-xs font-bold text-ms-red mb-2">Miembros externos detectados:</h3>
              <div className="max-h-40 overflow-auto">
                <table className="w-full text-xs">
                  <thead className="bg-red-50"><tr>
                    <th className="text-left px-2 py-1 font-medium">Grupo</th>
                    <th className="text-left px-2 py-1 font-medium">Email externo</th>
                  </tr></thead>
                  <tbody className="divide-y divide-ms-gray-30">
                    {auditData.external_issues.map((r, i) => (
                      <tr key={i} className="hover:bg-red-50/50">
                        <td className="px-2 py-1 text-ms-gray-130">{r.address}</td>
                        <td className="px-2 py-1 text-ms-red font-medium">{r.member_email}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {auditData.nested_issues.length > 0 && (
            <div>
              <h3 className="text-xs font-bold text-purple-700 mb-2">Grupos anidados detectados:</h3>
              <div className="max-h-40 overflow-auto">
                <table className="w-full text-xs">
                  <thead className="bg-purple-50"><tr>
                    <th className="text-left px-2 py-1 font-medium">Grupo padre</th>
                    <th className="text-left px-2 py-1 font-medium">Subgrupo</th>
                    <th className="text-right px-2 py-1 font-medium">Miembros del subgrupo</th>
                  </tr></thead>
                  <tbody className="divide-y divide-ms-gray-30">
                    {auditData.nested_issues.map((r, i) => (
                      <tr key={i} className="hover:bg-purple-50/50">
                        <td className="px-2 py-1 text-ms-gray-130">{r.parent_address}</td>
                        <td className="px-2 py-1 text-purple-700 font-medium">{r.nested_address}</td>
                        <td className="px-2 py-1 text-right">{r.nested_member_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {auditData.total_external === 0 && auditData.total_nested === 0 && (
            <div className="text-center text-ms-green text-sm font-medium py-4">
              Todos los grupos están limpios — sin miembros externos ni grupos anidados.
            </div>
          )}
        </div>
      )}

      {showForm && (
        <div className="bg-white rounded border border-ms-gray-30 p-5 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <input placeholder="grupo@dominio.com" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} className="px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" title="Dirección de correo del grupo." />
            <input placeholder="Nombre del grupo" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" title="Nombre descriptivo del grupo." />
          </div>
          <input placeholder="Descripción" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
          <label className="flex items-center gap-2 text-sm text-ms-gray-130">
            <input type="checkbox" checked={form.allow_external} onChange={(e) => setForm({ ...form, allow_external: e.target.checked })} className="accent-ms-blue" />
            Permitir miembros externos (correos fuera de @maquita.com.ec)
          </label>
          {form.allow_external && (
            <div className="px-3 py-2 bg-yellow-50 border border-yellow-300 rounded text-xs text-yellow-800">
              <strong>Advertencia:</strong> Al activar esta opción, se podrán agregar miembros con correos externos (gmail, hotmail, etc.). Los correos enviados a este grupo llegarán a personas fuera de la organización.
            </div>
          )}
          <div className="flex gap-2">
            <button onClick={createGroup} className="px-4 py-2 bg-ms-blue text-white rounded text-sm">Crear grupo</button>
            <button onClick={() => setShowForm(false)} className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90">Cancelar</button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Group list */}
        <div className="bg-white rounded border border-ms-gray-30 overflow-hidden">
          <div className="px-4 py-3 bg-ms-gray-20 border-b border-ms-gray-30 space-y-2">
            <span className="text-sm font-semibold text-ms-gray-130">Grupos ({groups.length})</span>
            <input
              type="text"
              placeholder="Buscar grupo..."
              value={groupSearch}
              onChange={(e) => setGroupSearch(e.target.value)}
              className="w-full px-2.5 py-1.5 border border-ms-gray-40 rounded text-xs focus:outline-none focus:border-ms-blue bg-white"
              title="Buscar por dirección, nombre o descripción del grupo"
            />
          </div>
          <div className="divide-y divide-ms-gray-30 max-h-[500px] overflow-auto">
            {filteredGroups.map((g) => (
              <button key={g.id} onClick={() => selectGroup(g.id)}
                className={`w-full text-left p-3 hover:bg-ms-blue-lighter/50 ${selected === g.id ? "bg-ms-blue-lighter border-l-3 border-ms-blue" : ""} ${hasIssues(g) ? "border-l-3 border-l-yellow-400" : ""}`}>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-ms-gray-130 truncate">{g.name || g.address}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${g.active ? "bg-green-50 text-ms-green" : "bg-red-50 text-ms-red"}`}>{g.active ? "Activo" : "Inactivo"}</span>
                </div>
                <p className="text-xs text-ms-gray-60">{g.address}</p>
                <div className="flex items-center gap-1.5 mt-1">
                  <span className="text-[10px] text-ms-gray-60">{g.member_count} miembros</span>
                  {groupAlerts(g)}
                </div>
              </button>
            ))}
            {groups.length === 0 && <div className="p-6 text-center text-ms-gray-60 text-sm">Sin grupos</div>}
          </div>
        </div>

        {/* Group detail + members */}
        <div className="lg:col-span-2 space-y-4">
          {groupDetail ? (
            <>
              <div className="bg-white rounded border border-ms-gray-30 p-5">
                {editing ? (
                  <div className="space-y-3">
                    <h3 className="text-sm font-semibold text-ms-gray-130">Editar grupo</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-ms-gray-90 mb-1">Nombre</label>
                        <input value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                          className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-ms-gray-90 mb-1">Dirección</label>
                        <input value={groupDetail.address} disabled
                          className="w-full px-3 py-2 border border-ms-gray-30 rounded text-sm bg-ms-gray-10 text-ms-gray-60" />
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-ms-gray-90 mb-1">Descripción</label>
                      <input value={editForm.description} onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                        className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
                    </div>
                    <div className="flex items-center gap-4">
                      <label className="flex items-center gap-2 text-xs text-ms-gray-130">
                        <input type="checkbox" checked={editForm.active} onChange={(e) => setEditForm({ ...editForm, active: e.target.checked })} className="accent-ms-blue" />
                        Grupo activo
                      </label>
                      <label className="flex items-center gap-2 text-xs text-ms-gray-130">
                        <input type="checkbox" checked={editForm.allow_external} onChange={(e) => setEditForm({ ...editForm, allow_external: e.target.checked })} className="accent-ms-blue" />
                        Permitir miembros externos
                      </label>
                    </div>
                    {editForm.allow_external && (
                      <div className="px-3 py-2 bg-yellow-50 border border-yellow-300 rounded text-xs text-yellow-800">
                        <strong>Advertencia:</strong> Los correos enviados a este grupo llegarán a personas fuera de la organización.
                      </div>
                    )}
                    <div className="flex gap-2">
                      <button onClick={saveEdit} className="px-4 py-2 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark">Guardar</button>
                      <button onClick={cancelEdit} className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90">Cancelar</button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <h2 className="text-lg font-semibold text-ms-gray-130">{groupDetail.name}</h2>
                        <p className="text-sm text-ms-blue">{groupDetail.address}</p>
                        {groupDetail.description && <p className="text-xs text-ms-gray-60 mt-1">{groupDetail.description}</p>}
                      </div>
                      <div className="flex gap-2">
                        <button onClick={startEdit} className="px-3 py-1.5 border border-ms-blue text-ms-blue rounded text-xs hover:bg-ms-blue-lighter">Editar</button>
                        <button onClick={() => deleteGroup(groupDetail.id)} className="px-3 py-1.5 border border-ms-red text-ms-red rounded text-xs hover:bg-red-50">Eliminar</button>
                      </div>
                    </div>
                    <div className="flex gap-3 text-xs">
                      <span className={`px-2 py-0.5 rounded ${groupDetail.allow_external ? "bg-yellow-50 text-yellow-700 border border-yellow-300" : "bg-green-50 text-ms-green"}`}>
                        {groupDetail.allow_external ? "Permite miembros externos" : "Solo miembros internos"}
                      </span>
                      <span className={`px-2 py-0.5 rounded ${groupDetail.active ? "bg-green-50 text-ms-green" : "bg-red-50 text-ms-red"}`}>
                        {groupDetail.active ? "Activo" : "Inactivo"}
                      </span>
                    </div>
                  </>
                )}

                {/* Stats */}
                {stats && (
                  <div className="flex gap-3 mt-3">
                    <span className="text-[10px] px-2 py-1 rounded bg-ms-gray-10 text-ms-gray-90">{stats.total} total</span>
                    <span className="text-[10px] px-2 py-1 rounded bg-green-50 text-ms-green">{stats.internal} internos</span>
                    {stats.external > 0 && <span className="text-[10px] px-2 py-1 rounded bg-red-50 text-ms-red font-bold">{stats.external} externos</span>}
                    {stats.nested_groups > 0 && <span className="text-[10px] px-2 py-1 rounded bg-purple-50 text-purple-700 font-bold">{stats.nested_groups} subgrupos</span>}
                  </div>
                )}
              </div>

              {/* Warnings */}
              {warnings.map((w, i) => (
                <div key={i} className={`rounded border p-4 ${w.severity === "high" ? "bg-red-50 border-ms-red/30" : "bg-yellow-50 border-yellow-300"}`}>
                  <div className="flex items-start gap-2">
                    <span className="text-lg">{w.severity === "high" ? "🚨" : "⚠"}</span>
                    <div>
                      <p className={`text-sm font-medium ${w.severity === "high" ? "text-ms-red" : "text-yellow-800"}`}>{w.message}</p>
                      {w.emails && w.emails.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {w.emails.map((e) => (
                            <span key={e} className="px-2 py-0.5 rounded text-[10px] font-medium bg-red-100 text-ms-red">{e}</span>
                          ))}
                        </div>
                      )}
                      {w.groups && w.groups.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {w.groups.map((g) => (
                            <span key={g} className="px-2 py-0.5 rounded text-[10px] font-medium bg-purple-100 text-purple-700">{g}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}

              {/* Add member */}
              <div className="bg-white rounded border border-ms-gray-30 p-4">
                <h3 className="text-sm font-semibold text-ms-gray-130 mb-3">Agregar miembro</h3>

                {addError && (
                  <div className="mb-3 px-3 py-2 bg-red-50 border border-ms-red/30 rounded text-sm text-ms-red">
                    {addError}
                  </div>
                )}

                {pendingConfirm && (
                  <div className={`mb-3 px-4 py-3 rounded border ${pendingConfirm.type === "external_warning" ? "bg-red-50 border-ms-red/30" : "bg-yellow-50 border-yellow-300"}`}>
                    <p className={`text-sm font-medium mb-2 ${pendingConfirm.type === "external_warning" ? "text-ms-red" : "text-yellow-800"}`}>
                      {pendingConfirm.message}
                    </p>
                    <div className="flex gap-2">
                      <button onClick={confirmAdd}
                        className={`px-4 py-1.5 rounded text-sm text-white font-medium ${pendingConfirm.type === "external_warning" ? "bg-ms-red hover:bg-red-700" : "bg-yellow-600 hover:bg-yellow-700"}`}>
                        Sí, agregar de todos modos
                      </button>
                      <button onClick={cancelConfirm}
                        className="px-4 py-1.5 border border-ms-gray-40 rounded text-sm text-ms-gray-90 hover:bg-ms-gray-10">
                        Cancelar
                      </button>
                    </div>
                  </div>
                )}

                <div className="flex gap-2 relative">
                  <div className="relative flex-1">
                    <input value={memberForm.email} onChange={(e) => searchUsers(e.target.value)}
                      onFocus={() => suggestions.length > 0 && setShowSugg(true)}
                      onKeyDown={(e) => e.key === "Enter" && (setShowSugg(false), addMember())}
                      placeholder="Email del miembro..." className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
                    {showSugg && suggestions.length > 0 && (
                      <div className="absolute z-10 w-full mt-1 bg-white border border-ms-gray-30 rounded shadow-lg max-h-40 overflow-auto">
                        {suggestions.map((s) => (
                          <button key={s.username} onClick={() => { setMemberForm({ ...memberForm, email: s.username, name: s.name }); setShowSugg(false); }}
                            className="w-full text-left px-3 py-2 hover:bg-ms-blue-lighter text-sm flex justify-between">
                            <span className="font-medium">{s.username}</span>
                            {s.name && <span className="text-ms-gray-60 text-xs">{s.name}</span>}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-xs">
                    <label className="flex items-center gap-1 text-ms-gray-90">
                      <input type="checkbox" checked={memberForm.can_send} onChange={(e) => setMemberForm({ ...memberForm, can_send: e.target.checked })} className="accent-ms-blue" />
                      Enviar
                    </label>
                    <label className="flex items-center gap-1 text-ms-gray-90">
                      <input type="checkbox" checked={memberForm.receive} onChange={(e) => setMemberForm({ ...memberForm, receive: e.target.checked })} className="accent-ms-blue" />
                      Recibir
                    </label>
                  </div>
                  <button onClick={() => addMember()} className="px-4 py-2 bg-ms-blue text-white rounded text-sm shrink-0">Agregar</button>
                </div>
              </div>

              {/* Members table */}
              <div className="bg-white rounded border border-ms-gray-30 overflow-hidden">
                <div className="px-4 py-2.5 bg-ms-gray-20 border-b border-ms-gray-30 flex items-center gap-3">
                  <span className="text-sm font-medium text-ms-gray-130 shrink-0">{members.length} miembros</span>
                  {members.length > 15 && (
                    <input
                      type="text"
                      placeholder="Buscar miembro..."
                      value={memberSearch}
                      onChange={(e) => setMemberSearch(e.target.value)}
                      className="flex-1 px-2.5 py-1 border border-ms-gray-40 rounded text-xs focus:outline-none focus:border-ms-blue bg-white"
                      title="Filtra miembros por email o nombre"
                    />
                  )}
                </div>
                <table className="w-full text-sm">
                  <thead className="bg-ms-gray-10 border-b border-ms-gray-30"><tr>
                    <th className="text-left px-4 py-2 font-medium text-ms-gray-90 text-xs">Email</th>
                    <th className="text-left px-4 py-2 font-medium text-ms-gray-90 text-xs">Nombre</th>
                    <th className="text-center px-4 py-2 font-medium text-ms-gray-90 text-xs">Tipo</th>
                    <th className="text-center px-4 py-2 font-medium text-ms-gray-90 text-xs">Enviar</th>
                    <th className="text-center px-4 py-2 font-medium text-ms-gray-90 text-xs">Recibir</th>
                    <th className="text-right px-4 py-2 font-medium text-ms-gray-90 text-xs">Acciones</th>
                  </tr></thead>
                  <tbody className="divide-y divide-ms-gray-30">
                    {(memberSearch.trim()
                      ? members.filter(m =>
                          m.member_email.toLowerCase().includes(memberSearch.toLowerCase()) ||
                          (m.member_name || "").toLowerCase().includes(memberSearch.toLowerCase())
                        )
                      : members
                    ).map((m) => (
                      <tr key={m.id} className={`hover:bg-ms-blue-lighter/50 ${memberTypeStyle(m.member_type)}`}>
                        <td className="px-4 py-2 text-ms-gray-130">
                          {m.member_email}
                          {memberTypeBadge(m.member_type)}
                        </td>
                        <td className="px-4 py-2 text-ms-gray-60">{m.member_name || "-"}</td>
                        <td className="px-4 py-2 text-center">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                            m.member_type === "external" ? "bg-red-100 text-ms-red" :
                            m.member_type === "group" ? "bg-purple-100 text-purple-700" :
                            "bg-green-50 text-ms-green"
                          }`}>
                            {m.member_type === "external" ? "Externo" : m.member_type === "group" ? "Grupo" : "Interno"}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-center">
                          <button onClick={() => togglePerm(m.id, "can_send", !m.can_send)}
                            className={`px-2 py-0.5 rounded text-[10px] font-medium ${m.can_send ? "bg-green-50 text-ms-green" : "bg-red-50 text-ms-red"}`}>
                            {m.can_send ? "Sí" : "No"}
                          </button>
                        </td>
                        <td className="px-4 py-2 text-center">
                          <button onClick={() => togglePerm(m.id, "receive", !m.receive)}
                            className={`px-2 py-0.5 rounded text-[10px] font-medium ${m.receive ? "bg-green-50 text-ms-green" : "bg-red-50 text-ms-red"}`}>
                            {m.receive ? "Sí" : "No"}
                          </button>
                        </td>
                        <td className="px-4 py-2 text-right">
                          <button onClick={() => removeMember(m.id)} className="text-ms-red text-xs hover:underline">Quitar</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {members.length === 0 && <div className="p-6 text-center text-ms-gray-60 text-sm">Sin miembros — agrega al menos uno</div>}
              </div>
            </>
          ) : (
            <div className="bg-white rounded border border-ms-gray-30 p-12 text-center text-ms-gray-60">
              Selecciona un grupo para ver sus miembros y configuración
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
