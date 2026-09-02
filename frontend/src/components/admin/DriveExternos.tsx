import { useEffect, useState } from 'react';
import { api } from '../../api/client';

interface CuentaExterna {
  id: number;
  email: string;
  full_name: string | null;
  active: boolean;
  activado: boolean;
  cuota_mb: number | null;
  proveedor: string;
  creado_por: string | null;
  creado: string | null;
}

/**
 * Gestion de CUENTAS DRIVE EXTERNAS (colaboradores/aliados con un correo que NO es buzon
 * del servidor). Usa los endpoints del Almacen (/api/almacen/externos/*), solo para admins.
 */
export function DriveExternos() {
  const [cuentas, setCuentas] = useState<CuentaExterna[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');
  const [form, setForm] = useState({ email: '', nombre: '' });

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const d = await api.get<{ cuentas: CuentaExterna[] }>('/almacen/externos');
      setCuentas(d.cuentas || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo cargar (¿eres administrador del Drive?)');
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  const invitar = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(''); setAviso('');
    if (!form.email.trim()) return;
    try {
      const r = await api.post<{ ok: boolean; link: string }>('/almacen/externos/invitar',
        { email: form.email.trim(), nombre: form.nombre.trim() });
      setAviso('Invitación enviada a ' + form.email.trim() + '. Enlace: ' + r.link);
      setForm({ email: '', nombre: '' });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo invitar');
    }
  };

  const accion = async (id: number, a: string) => {
    setError('');
    try { await api.post(`/almacen/externos/${id}/${a}`, {}); load(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Error'); }
  };
  const reinvitar = async (id: number) => {
    setError(''); setAviso('');
    try { const r = await api.post<{ link: string }>(`/almacen/externos/${id}/reinvitar`, {}); setAviso('Reinvitada. Enlace: ' + r.link); }
    catch (e) { setError(e instanceof Error ? e.message : 'Error'); }
  };
  const fijarCuota = async (id: number) => {
    const v = prompt('Cuota en MB (0 = usar la de la organización):');
    if (v === null) return;
    setError('');
    try { await api.post(`/almacen/externos/${id}/cuota`, { cuota_mb: parseInt(v || '0', 10) }); load(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Error'); }
  };
  const eliminar = async (id: number, em: string) => {
    if (!confirm(`¿Eliminar la cuenta ${em}? Revoca su acceso al Drive. No borra sus archivos (los conserva un master).`)) return;
    setError('');
    try { await api.del(`/almacen/externos/${id}`); load(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Error'); }
  };

  const estado = (c: CuentaExterna) =>
    !c.active ? <span className="px-2 py-0.5 rounded text-xs bg-red-100 text-red-700">inactiva</span>
      : c.activado ? <span className="px-2 py-0.5 rounded text-xs bg-green-100 text-green-700">activa</span>
        : <span className="px-2 py-0.5 rounded text-xs bg-yellow-100 text-yellow-800">sin activar</span>;

  return (
    <div className="p-6 max-w-5xl">
      <h1 className="text-xl font-semibold text-[#323130] mb-1">Cuentas Drive externas</h1>
      <p className="text-sm text-[#605e5c] mb-4">
        Da acceso al Drive a colaboradores (pasantes, aliados) con un correo que <b>no</b> es buzón
        del servidor. Reciben una invitación por correo para activar su cuenta.
      </p>

      <form onSubmit={invitar} className="flex flex-wrap gap-2 items-end bg-white border border-[#edebe9] rounded p-4 mb-4">
        <div>
          <label className="block text-xs text-[#605e5c] mb-1">Correo externo</label>
          <input type="email" required value={form.email} onChange={e => setForm({ ...form, email: e.target.value })}
            placeholder="persona@externo.com" className="border border-[#c8c6c4] rounded px-3 py-2 text-sm w-64" />
        </div>
        <div>
          <label className="block text-xs text-[#605e5c] mb-1">Nombre (opcional)</label>
          <input type="text" value={form.nombre} onChange={e => setForm({ ...form, nombre: e.target.value })}
            className="border border-[#c8c6c4] rounded px-3 py-2 text-sm w-48" />
        </div>
        <button type="submit" className="bg-[#0078d4] text-white rounded px-4 py-2 text-sm font-medium">Crear e invitar</button>
      </form>

      {aviso && <div className="mb-3 text-sm bg-[#dff6dd] text-[#0b6a0b] rounded px-3 py-2 break-all">{aviso}</div>}
      {error && <div className="mb-3 text-sm bg-[#fde7e9] text-[#d13438] rounded px-3 py-2">{error}</div>}

      {loading ? <p className="text-sm text-[#605e5c]">Cargando…</p> : (
        <div className="overflow-x-auto bg-white border border-[#edebe9] rounded">
          <table className="w-full text-sm">
            <thead><tr className="bg-[#f3f2f1] text-left text-[#605e5c]">
              <th className="px-3 py-2">Correo</th><th className="px-3 py-2">Nombre</th>
              <th className="px-3 py-2">Estado</th><th className="px-3 py-2">Cuota</th>
              <th className="px-3 py-2">Creada</th><th className="px-3 py-2">Acciones</th>
            </tr></thead>
            <tbody>
              {cuentas.length === 0 && <tr><td colSpan={6} className="px-3 py-4 text-center text-[#605e5c]">Aún no hay cuentas externas.</td></tr>}
              {cuentas.map(c => (
                <tr key={c.id} className="border-t border-[#edebe9]">
                  <td className="px-3 py-2">{c.email}</td>
                  <td className="px-3 py-2">{c.full_name || '—'}</td>
                  <td className="px-3 py-2">{estado(c)}</td>
                  <td className="px-3 py-2">{c.cuota_mb ? c.cuota_mb + ' MB' : '—'}</td>
                  <td className="px-3 py-2">{c.creado || '—'}</td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    {c.active
                      ? <button onClick={() => accion(c.id, 'desactivar')} className="text-xs px-2 py-1 rounded bg-[#edebe9] mr-1">Desactivar</button>
                      : <button onClick={() => accion(c.id, 'activar')} className="text-xs px-2 py-1 rounded bg-[#edebe9] mr-1">Activar</button>}
                    <button onClick={() => reinvitar(c.id)} className="text-xs px-2 py-1 rounded bg-[#edebe9] mr-1">Reinvitar</button>
                    <button onClick={() => fijarCuota(c.id)} className="text-xs px-2 py-1 rounded bg-[#edebe9] mr-1">Cuota</button>
                    <button onClick={() => eliminar(c.id, c.email)} className="text-xs px-2 py-1 rounded bg-[#d13438] text-white">Eliminar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
