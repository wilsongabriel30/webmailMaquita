import { useEffect, useState } from 'react';
import { api } from '../../api/client';

interface Alias {
  address: string;
  goto: string;
  domain: string;
  active: boolean;
  created: string;
}

interface Domain {
  domain: string;
}

export function AliasManager() {
  const [aliases, setAliases] = useState<Alias[]>([]);
  const [domains, setDomains] = useState<Domain[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterDomain, setFilterDomain] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editAlias, setEditAlias] = useState<Alias | null>(null);
  const [form, setForm] = useState({ address: '', goto: '', active: true });

  const load = () => {
    setLoading(true);
    const url = filterDomain ? `/admin/aliases?domain=${filterDomain}` : '/admin/aliases';
    api.get<Alias[]>(url).then(setAliases).catch(() => {}).finally(() => setLoading(false));
  };

  useEffect(() => {
    api.get<Domain[]>('/admin/domains').then(setDomains).catch(() => {});
  }, []);

  useEffect(() => { load(); }, [filterDomain]);

  const openCreate = () => {
    setEditAlias(null);
    setForm({ address: '', goto: '', active: true });
    setShowForm(true);
  };

  const openEdit = (a: Alias) => {
    setEditAlias(a);
    setForm({ address: a.address, goto: a.goto, active: a.active });
    setShowForm(true);
  };

  const save = async () => {
    try {
      if (editAlias) {
        await api.put(`/admin/aliases/${editAlias.address}`, { goto: form.goto, active: form.active });
      } else {
        await api.post('/admin/aliases', form);
      }
      setShowForm(false);
      load();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Error');
    }
  };

  const remove = async (address: string) => {
    if (!confirm(`Eliminar alias ${address}?`)) return;
    try {
      await api.del(`/admin/aliases/${address}`);
      load();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Error');
    }
  };

  return (
    <div className="p-8 max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-800">Alias</h1>
        <div className="flex items-center gap-3">
          <select value={filterDomain} onChange={(e) => setFilterDomain(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm">
            <option value="">Todos los dominios</option>
            {domains.map((d) => <option key={d.domain} value={d.domain}>{d.domain}</option>)}
          </select>
          <button onClick={openCreate} className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 text-sm font-medium">
            Nuevo alias
          </button>
        </div>
      </div>

      {showForm && (
        <div className="mb-6 border border-slate-200 rounded-xl p-6 bg-slate-50">
          <h3 className="font-semibold mb-4">{editAlias ? 'Editar' : 'Crear'} alias</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Dirección</label>
              <input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })}
                disabled={!!editAlias} placeholder="alias@dominio.com"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm disabled:bg-slate-100" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Destino</label>
              <input value={form.goto} onChange={(e) => setForm({ ...form, goto: e.target.value })}
                placeholder="destino@dominio.com"
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
              <th className="pb-3 font-medium">Dirección</th>
              <th className="pb-3 font-medium">Destino</th>
              <th className="pb-3 font-medium">Dominio</th>
              <th className="pb-3 font-medium text-center">Estado</th>
              <th className="pb-3 font-medium text-right">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {aliases.map((a) => (
              <tr key={a.address} className="border-b border-slate-100 hover:bg-slate-50">
                <td className="py-3 font-medium text-slate-800 text-sm">{a.address}</td>
                <td className="py-3 text-sm text-slate-600">{a.goto}</td>
                <td className="py-3 text-sm text-slate-600">{a.domain}</td>
                <td className="py-3 text-center">
                  <span className={`text-xs px-2 py-1 rounded-full ${a.active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                    {a.active ? 'Activo' : 'Inactivo'}
                  </span>
                </td>
                <td className="py-3 text-right">
                  <button onClick={() => openEdit(a)} className="text-sm text-blue-600 hover:text-blue-800 mr-3">Editar</button>
                  <button onClick={() => remove(a.address)} className="text-sm text-red-600 hover:text-red-800">Eliminar</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p className="mt-4 text-sm text-slate-400">{aliases.length} alias(es)</p>
    </div>
  );
}
