import { useEffect, useState } from 'react';
import { api } from '../../api/client';

interface Domain {
  domain: string;
  description: string;
  aliases: number;
  mailboxes: number;
  maxquota: number;
  active: boolean;
  mailbox_count: number;
  alias_count: number;
  created: string;
}

export function DomainsManager() {
  const [domains, setDomains] = useState<Domain[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editDomain, setEditDomain] = useState<Domain | null>(null);
  const [form, setForm] = useState({ domain: '', description: '', mailboxes: 0, aliases: 0, maxquota: 0, active: true });

  const load = () => {
    setLoading(true);
    api.get<Domain[]>('/admin/domains')
      .then(setDomains)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const openCreate = () => {
    setEditDomain(null);
    setForm({ domain: '', description: '', mailboxes: 0, aliases: 0, maxquota: 0, active: true });
    setShowForm(true);
  };

  const openEdit = (d: Domain) => {
    setEditDomain(d);
    setForm({ domain: d.domain, description: d.description, mailboxes: d.mailboxes, aliases: d.aliases, maxquota: d.maxquota, active: d.active });
    setShowForm(true);
  };

  const save = async () => {
    try {
      if (editDomain) {
        await api.put(`/admin/domains/${editDomain.domain}`, form);
      } else {
        await api.post('/admin/domains', form);
      }
      setShowForm(false);
      load();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Error');
    }
  };

  const remove = async (domain: string) => {
    if (!confirm(`Eliminar dominio ${domain}?`)) return;
    try {
      await api.del(`/admin/domains/${domain}`);
      load();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Error');
    }
  };

  return (
    <div className="p-8 max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-800">Dominios</h1>
        <button onClick={openCreate} className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 text-sm font-medium">
          Nuevo dominio
        </button>
      </div>

      {showForm && (
        <div className="mb-6 border border-slate-200 rounded-xl p-6 bg-slate-50">
          <h3 className="font-semibold mb-4">{editDomain ? 'Editar' : 'Crear'} dominio</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Dominio</label>
              <input value={form.domain} onChange={(e) => setForm({ ...form, domain: e.target.value })}
                disabled={!!editDomain}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm disabled:bg-slate-100" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Descripción</label>
              <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Máx buzones (0 = sin límite)</label>
              <input type="number" value={form.mailboxes} onChange={(e) => setForm({ ...form, mailboxes: +e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Máx aliases (0 = sin límite)</label>
              <input type="number" value={form.aliases} onChange={(e) => setForm({ ...form, aliases: +e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Máx quota por buzón (MB, 0 = sin límite)</label>
              <input type="number" value={form.maxquota} onChange={(e) => setForm({ ...form, maxquota: +e.target.value })}
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
              <th className="pb-3 font-medium">Dominio</th>
              <th className="pb-3 font-medium">Descripción</th>
              <th className="pb-3 font-medium text-center">Buzones</th>
              <th className="pb-3 font-medium text-center">Aliases</th>
              <th className="pb-3 font-medium text-center">Estado</th>
              <th className="pb-3 font-medium text-right">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {domains.map((d) => (
              <tr key={d.domain} className="border-b border-slate-100 hover:bg-slate-50">
                <td className="py-3 font-medium text-slate-800">{d.domain}</td>
                <td className="py-3 text-sm text-slate-600">{d.description}</td>
                <td className="py-3 text-sm text-center">{d.mailbox_count}</td>
                <td className="py-3 text-sm text-center">{d.alias_count}</td>
                <td className="py-3 text-center">
                  <span className={`text-xs px-2 py-1 rounded-full ${d.active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                    {d.active ? 'Activo' : 'Inactivo'}
                  </span>
                </td>
                <td className="py-3 text-right">
                  <button onClick={() => openEdit(d)} className="text-sm text-blue-600 hover:text-blue-800 mr-3">Editar</button>
                  <button onClick={() => remove(d.domain)} className="text-sm text-red-600 hover:text-red-800">Eliminar</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
