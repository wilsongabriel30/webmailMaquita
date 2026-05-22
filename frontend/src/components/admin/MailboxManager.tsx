import { useEffect, useState } from 'react';
import { api } from '../../api/client';

interface Mailbox {
  username: string;
  name: string;
  domain: string;
  quota: number;
  active: boolean;
  local_part: string;
  phone: string;
  email_other: string;
  created: string;
  quota_usage?: { used: number; limit: number; percent: number } | null;
}

interface Domain {
  domain: string;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

export function MailboxManager() {
  const [mailboxes, setMailboxes] = useState<Mailbox[]>([]);
  const [domains, setDomains] = useState<Domain[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterDomain, setFilterDomain] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editMbox, setEditMbox] = useState<Mailbox | null>(null);
  const [form, setForm] = useState({ username: '', password: '', name: '', domain: '', quota: 0, active: true });

  const load = () => {
    setLoading(true);
    const url = filterDomain ? `/admin/mailboxes?domain=${filterDomain}` : '/admin/mailboxes';
    api.get<Mailbox[]>(url).then(setMailboxes).catch(() => {}).finally(() => setLoading(false));
  };

  useEffect(() => {
    api.get<Domain[]>('/admin/domains').then(setDomains).catch(() => {});
  }, []);

  useEffect(() => { load(); }, [filterDomain]);

  const openCreate = () => {
    setEditMbox(null);
    setForm({ username: '', password: '', name: '', domain: domains[0]?.domain || '', quota: 0, active: true });
    setShowForm(true);
  };

  const openEdit = (m: Mailbox) => {
    setEditMbox(m);
    setForm({ username: m.username, password: '', name: m.name, domain: m.domain, quota: m.quota, active: m.active });
    setShowForm(true);
  };

  const save = async () => {
    try {
      if (editMbox) {
        const data: Record<string, unknown> = { name: form.name, quota: form.quota, active: form.active };
        if (form.password) data.password = form.password;
        await api.put(`/admin/mailboxes/${editMbox.username}`, data);
      } else {
        await api.post('/admin/mailboxes', {
          username: form.username.includes('@') ? form.username : `${form.username}@${form.domain}`,
          password: form.password,
          name: form.name,
          quota: form.quota,
          active: form.active,
        });
      }
      setShowForm(false);
      load();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Error');
    }
  };

  const toggleActive = async (username: string) => {
    try {
      await api.post(`/admin/mailboxes/${username}/toggle-active`, {});
      load();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Error');
    }
  };

  const unlockAccount = async (username: string) => {
    try {
      const res = await api.post<{ cleared: string[] }>(`/admin/mailboxes/${username}/unlock`, {});
      alert(`Cuenta ${username} desbloqueada. Limpiados: ${res.cleared.join(', ') || 'ninguno'}`);
      load();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Error');
    }
  };

  const remove = async (username: string) => {
    if (!confirm(`Eliminar buzón ${username}? Esta acción es irreversible.`)) return;
    try {
      await api.del(`/admin/mailboxes/${username}`);
      load();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Error');
    }
  };

  return (
    <div className="p-8 max-w-6xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-800">Buzones</h1>
        <div className="flex items-center gap-3">
          <select value={filterDomain} onChange={(e) => setFilterDomain(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm">
            <option value="">Todos los dominios</option>
            {domains.map((d) => <option key={d.domain} value={d.domain}>{d.domain}</option>)}
          </select>
          <button onClick={openCreate} className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 text-sm font-medium">
            Nuevo buzón
          </button>
        </div>
      </div>

      {showForm && (
        <div className="mb-6 border border-slate-200 rounded-xl p-6 bg-slate-50">
          <h3 className="font-semibold mb-4">{editMbox ? 'Editar' : 'Crear'} buzón</h3>
          <div className="grid grid-cols-2 gap-4">
            {!editMbox && (
              <>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Usuario</label>
                  <input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })}
                    placeholder="usuario" className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Dominio</label>
                  <select value={form.domain} onChange={(e) => setForm({ ...form, domain: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm">
                    {domains.map((d) => <option key={d.domain} value={d.domain}>{d.domain}</option>)}
                  </select>
                </div>
              </>
            )}
            {editMbox && (
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Usuario</label>
                <input value={form.username} disabled className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-slate-100" />
              </div>
            )}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Contraseña {editMbox && '(dejar vacío para no cambiar)'}
              </label>
              <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Nombre</label>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Quota (MB, 0 = sin límite)</label>
              <input type="number" value={form.quota} onChange={(e) => setForm({ ...form, quota: +e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" />
            </div>
            <div className="flex items-end">
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={form.active} onChange={(e) => setForm({ ...form, active: e.target.checked })}
                  className="w-4 h-4 text-orange-600 rounded" />
                <span className="text-sm text-slate-700">Activo</span>
              </label>
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button onClick={save} className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 text-sm">Guardar</button>
            <button onClick={() => setShowForm(false)} className="px-4 py-2 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 text-sm">Cancelar</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-center py-8 text-slate-400">Cargando...</div>
      ) : (
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-200 text-left text-sm text-slate-500">
              <th className="pb-3 font-medium">Usuario</th>
              <th className="pb-3 font-medium">Nombre</th>
              <th className="pb-3 font-medium">Dominio</th>
              <th className="pb-3 font-medium text-center">Quota</th>
              <th className="pb-3 font-medium text-center">Estado</th>
              <th className="pb-3 font-medium text-right">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {mailboxes.map((m) => (
              <tr key={m.username} className="border-b border-slate-100 hover:bg-slate-50">
                <td className="py-3 font-medium text-slate-800 text-sm">{m.username}</td>
                <td className="py-3 text-sm text-slate-600">{m.name}</td>
                <td className="py-3 text-sm text-slate-600">{m.domain}</td>
                <td className="py-3 text-sm text-center text-slate-600">
                  {m.quota ? formatBytes(m.quota * 1024 * 1024) : 'Sin límite'}
                </td>
                <td className="py-3 text-center">
                  <button onClick={() => toggleActive(m.username)}
                    className={`text-xs px-2 py-1 rounded-full cursor-pointer ${m.active ? 'bg-green-100 text-green-700 hover:bg-green-200' : 'bg-red-100 text-red-700 hover:bg-red-200'}`}>
                    {m.active ? 'Activo' : 'Bloqueado'}
                  </button>
                </td>
                <td className="py-3 text-right">
                  <button onClick={() => unlockAccount(m.username)} className="text-sm text-amber-600 hover:text-amber-800 mr-3" title="Desbloquear rate limit">Desbloquear</button>
                  <button onClick={() => openEdit(m)} className="text-sm text-blue-600 hover:text-blue-800 mr-3">Editar</button>
                  <button onClick={() => remove(m.username)} className="text-sm text-red-600 hover:text-red-800">Eliminar</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p className="mt-4 text-sm text-slate-400">{mailboxes.length} buzón(es)</p>
    </div>
  );
}
