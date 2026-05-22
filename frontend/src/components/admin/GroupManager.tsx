import { useEffect, useState } from 'react';
import { api } from '../../api/client';

interface GroupMember {
  id: number;
  member_email: string;
  member_name: string;
  can_send: boolean;
  receive: boolean;
}

interface Group {
  id: number;
  address: string;
  name: string;
  description: string;
  domain: string;
  active: boolean;
  allow_external: boolean;
  member_count: number;
  members?: GroupMember[];
}

interface Domain {
  domain: string;
}

export function GroupManager() {
  const [groups, setGroups] = useState<Group[]>([]);
  const [domains, setDomains] = useState<Domain[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterDomain, setFilterDomain] = useState('');
  const [search, setSearch] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editGroup, setEditGroup] = useState<Group | null>(null);
  const [form, setForm] = useState({ address: '', name: '', description: '', domain: '', active: true, allow_external: false });
  const [selectedGroup, setSelectedGroup] = useState<Group | null>(null);
  const [members, setMembers] = useState<GroupMember[]>([]);
  const [loadingMembers, setLoadingMembers] = useState(false);
  const [newMember, setNewMember] = useState('');

  const load = () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (filterDomain) params.set('domain', filterDomain);
    if (search) params.set('search', search);
    const url = `/admin/groups${params.toString() ? '?' + params.toString() : ''}`;
    api.get<Group[]>(url).then(setGroups).catch(() => {}).finally(() => setLoading(false));
  };

  useEffect(() => {
    api.get<Domain[]>('/admin/domains').then(setDomains).catch(() => {});
  }, []);

  useEffect(() => { load(); }, [filterDomain, search]);

  const openCreate = () => {
    setEditGroup(null);
    setForm({ address: '', name: '', description: '', domain: domains[0]?.domain || '', active: true, allow_external: false });
    setShowForm(true);
    setSelectedGroup(null);
  };

  const openEdit = (g: Group) => {
    setEditGroup(g);
    setForm({ address: g.address, name: g.name, description: g.description, domain: g.domain, active: g.active, allow_external: g.allow_external });
    setShowForm(true);
    setSelectedGroup(null);
  };

  const save = async () => {
    try {
      if (editGroup) {
        await api.put(`/admin/groups/${editGroup.id}`, { name: form.name, description: form.description, active: form.active, allow_external: form.allow_external });
      } else {
        const address = form.address.includes('@') ? form.address : `${form.address}@${form.domain}`;
        await api.post('/admin/groups', { ...form, address });
      }
      setShowForm(false);
      load();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Error');
    }
  };

  const remove = async (g: Group) => {
    if (!confirm(`Eliminar grupo ${g.address}? Se eliminaran todos sus miembros.`)) return;
    try {
      await api.del(`/admin/groups/${g.id}`);
      if (selectedGroup?.id === g.id) setSelectedGroup(null);
      load();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Error');
    }
  };

  const toggleActive = async (g: Group) => {
    try {
      await api.put(`/admin/groups/${g.id}`, { active: !g.active });
      load();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Error');
    }
  };

  const viewMembers = async (g: Group) => {
    setSelectedGroup(g);
    setShowForm(false);
    setLoadingMembers(true);
    try {
      const data = await api.get<GroupMember[]>(`/admin/groups/${g.id}/members`);
      setMembers(data);
    } catch {
      setMembers([]);
    } finally {
      setLoadingMembers(false);
    }
  };

  const addMember = async () => {
    if (!selectedGroup || !newMember.trim()) return;
    try {
      await api.post(`/admin/groups/${selectedGroup.id}/members`, { member_email: newMember.trim() });
      setNewMember('');
      viewMembers(selectedGroup);
      load();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Error');
    }
  };

  const removeMember = async (memberId: number, email: string) => {
    if (!selectedGroup || !confirm(`Quitar ${email} del grupo?`)) return;
    try {
      await api.del(`/admin/groups/${selectedGroup.id}/members/${memberId}`);
      viewMembers(selectedGroup);
      load();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Error');
    }
  };

  return (
    <div className="p-8 max-w-6xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Grupos de Distribucion</h1>
          <p className="text-sm text-slate-500 mt-1">{groups.length} grupo(s) — {groups.reduce((s, g) => s + g.member_count, 0)} miembros total</p>
        </div>
        <div className="flex items-center gap-3">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar grupo..."
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm w-48"
          />
          <select value={filterDomain} onChange={(e) => setFilterDomain(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm">
            <option value="">Todos los dominios</option>
            {domains.map((d) => <option key={d.domain} value={d.domain}>{d.domain}</option>)}
          </select>
          <button onClick={openCreate} className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 text-sm font-medium">
            Nuevo grupo
          </button>
        </div>
      </div>

      {showForm && (
        <div className="mb-6 border border-slate-200 rounded-xl p-6 bg-slate-50">
          <h3 className="font-semibold mb-4">{editGroup ? 'Editar' : 'Crear'} grupo</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Direccion</label>
              <input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })}
                disabled={!!editGroup} placeholder="grupo@dominio.com"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm disabled:bg-slate-100" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Nombre</label>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Nombre del grupo"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" />
            </div>
            <div className="col-span-2">
              <label className="block text-sm font-medium text-slate-700 mb-1">Descripcion</label>
              <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Descripcion del grupo"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" />
            </div>
            {!editGroup && (
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Dominio</label>
                <select value={form.domain} onChange={(e) => setForm({ ...form, domain: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm">
                  {domains.map((d) => <option key={d.domain} value={d.domain}>{d.domain}</option>)}
                </select>
              </div>
            )}
            <div className="flex items-end gap-6">
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={form.active} onChange={(e) => setForm({ ...form, active: e.target.checked })}
                  className="w-4 h-4 text-orange-600 rounded" />
                <span className="text-sm text-slate-700">Activo</span>
              </label>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={form.allow_external} onChange={(e) => setForm({ ...form, allow_external: e.target.checked })}
                  className="w-4 h-4 text-orange-600 rounded" />
                <span className="text-sm text-slate-700">Permitir remitentes externos</span>
              </label>
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button onClick={save} className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 text-sm">Guardar</button>
            <button onClick={() => setShowForm(false)} className="px-4 py-2 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 text-sm">Cancelar</button>
          </div>
        </div>
      )}

      <div className="flex gap-6">
        {/* Groups table */}
        <div className={selectedGroup ? 'w-1/2' : 'w-full'}>
          {loading ? (
            <div className="text-center py-8 text-slate-400">Cargando...</div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-200 text-left text-sm text-slate-500">
                  <th className="pb-3 font-medium">Grupo</th>
                  <th className="pb-3 font-medium">Miembros</th>
                  <th className="pb-3 font-medium text-center">Estado</th>
                  <th className="pb-3 font-medium text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {groups.map((g) => (
                  <tr key={g.id} className={`border-b border-slate-100 hover:bg-slate-50 cursor-pointer ${selectedGroup?.id === g.id ? 'bg-orange-50' : ''}`}
                    onClick={() => viewMembers(g)}>
                    <td className="py-3">
                      <div className="font-medium text-slate-800 text-sm">{g.address}</div>
                      <div className="text-xs text-slate-500">{g.name}{g.description ? ` — ${g.description}` : ''}</div>
                    </td>
                    <td className="py-3">
                      <span className="text-sm font-medium text-slate-700 bg-slate-100 px-2 py-0.5 rounded-full">{g.member_count}</span>
                    </td>
                    <td className="py-3 text-center">
                      <button onClick={(e) => { e.stopPropagation(); toggleActive(g); }}
                        className={`text-xs px-2 py-1 rounded-full ${g.active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                        {g.active ? 'Activo' : 'Inactivo'}
                      </button>
                    </td>
                    <td className="py-3 text-right" onClick={(e) => e.stopPropagation()}>
                      <button onClick={() => openEdit(g)} className="text-sm text-blue-600 hover:text-blue-800 mr-3">Editar</button>
                      <button onClick={() => remove(g)} className="text-sm text-red-600 hover:text-red-800">Eliminar</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Members panel */}
        {selectedGroup && (
          <div className="w-1/2 border-l border-slate-200 pl-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="font-semibold text-slate-800">{selectedGroup.address}</h3>
                <p className="text-xs text-slate-500">{selectedGroup.name}</p>
              </div>
              <button onClick={() => setSelectedGroup(null)} className="text-sm text-slate-400 hover:text-slate-600">Cerrar</button>
            </div>

            <div className="flex gap-2 mb-4">
              <input value={newMember} onChange={(e) => setNewMember(e.target.value)}
                placeholder="email@dominio.com"
                onKeyDown={(e) => e.key === 'Enter' && addMember()}
                className="flex-1 px-3 py-2 border border-slate-300 rounded-lg text-sm" />
              <button onClick={addMember} className="px-3 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 text-sm">
                Agregar
              </button>
            </div>

            {loadingMembers ? (
              <div className="text-center py-4 text-slate-400 text-sm">Cargando miembros...</div>
            ) : (
              <div className="space-y-1 max-h-96 overflow-y-auto">
                {members.length === 0 ? (
                  <p className="text-sm text-slate-400 py-4 text-center">Sin miembros</p>
                ) : (
                  members.map((m) => (
                    <div key={m.id} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-slate-50 group">
                      <div>
                        <span className="text-sm text-slate-800">{m.member_email}</span>
                        {m.member_name && m.member_name !== m.member_email.split('@')[0] && (
                          <span className="text-xs text-slate-400 ml-2">{m.member_name}</span>
                        )}
                      </div>
                      <button onClick={() => removeMember(m.id, m.member_email)}
                        className="text-red-500 hover:text-red-700 opacity-0 group-hover:opacity-100 transition-opacity">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  ))
                )}
              </div>
            )}
            <p className="mt-3 text-xs text-slate-400">{members.length} miembro(s)</p>
          </div>
        )}
      </div>
    </div>
  );
}
