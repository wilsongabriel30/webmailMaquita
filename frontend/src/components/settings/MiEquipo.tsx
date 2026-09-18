import { useCallback, useEffect, useState } from 'react';
import { api } from '../../api/client';

// Código autoservicio para activar la app «Mi equipo» en el propio teléfono. Es solo para la
// gestión del equipo (respaldo, ubicación si se autoriza, mensajes de Tecnología); NO da acceso al
// correo: la lectura del correo en la app usa el inicio de sesión normal.

interface Equipo { id: number; nombre?: string; modelo?: string; fabricante?: string; estado: string; modo: string; ultimo_contacto?: string }
interface Estado { tiene_codigo_activo: boolean; prefijo?: string; caduca_en?: string; equipos: Equipo[] }

export function MiEquipo() {
  const [datos, setDatos] = useState<Estado>({ tiene_codigo_activo: false, equipos: [] });
  const [codigo, setCodigo] = useState<string | null>(null);
  const [copiado, setCopiado] = useState(false);
  const [error, setError] = useState('');
  const [ocupado, setOcupado] = useState(false);

  const cargar = useCallback(async () => {
    try { setDatos(await api.get<Estado>('/settings/mi-equipo')); }
    catch (e: any) { setError(e.message); }
  }, []);
  useEffect(() => { cargar(); }, [cargar]);

  const generar = async () => {
    setOcupado(true); setError('');
    try { const r = await api.post<{ codigo: string }>('/settings/mi-equipo', {}); setCodigo(r.codigo); await cargar(); }
    catch (e: any) { setError(e.message); }
    finally { setOcupado(false); }
  };
  const copiar = async () => { if (codigo) { try { await navigator.clipboard.writeText(codigo); setCopiado(true); setTimeout(() => setCopiado(false), 1500); } catch { /* noop */ } } };
  const fecha = (v?: string) => (v ? new Date(v).toLocaleString('es-EC', { dateStyle: 'short', timeStyle: 'short' }) : '');

  return (
    <div className="max-w-2xl">
      <h3 className="text-lg font-semibold">Mi teléfono (app Maquita)</h3>
      <p className="text-sm text-[#605e5c] mt-1">
        Para activar la sección <strong>Mi equipo</strong> de la app en tu teléfono, genera aquí un código y
        escríbelo una vez en la app (Mi equipo → Activar). Sirve para el respaldo, los mensajes de Tecnología y,
        si lo autorizas, la ubicación. <strong>No es para leer el correo</strong>: el correo en la app entra con tu
        usuario y tu contraseña de siempre.
      </p>
      {error && <div className="mt-3 text-sm px-3 py-2 rounded bg-red-50 text-red-700">{error}</div>}

      {codigo && (
        <div className="mt-4 bg-amber-50 border border-amber-200 rounded p-4">
          <div className="text-xs text-amber-800 mb-1">Cópialo ahora: se muestra una sola vez y sirve para un teléfono.</div>
          <div className="flex items-center gap-3">
            <code className="text-2xl font-mono tracking-widest">{codigo}</code>
            <button onClick={copiar} className="text-xs text-[#0078d4] hover:underline">{copiado ? 'Copiado' : 'Copiar'}</button>
          </div>
        </div>
      )}

      <div className="mt-4 flex items-center gap-3">
        <button onClick={generar} disabled={ocupado}
          className="px-4 py-2 rounded bg-[#0078d4] text-white text-sm hover:bg-[#106ebe] disabled:opacity-50">
          {datos.tiene_codigo_activo ? 'Generar un código nuevo' : 'Generar código para mi teléfono'}
        </button>
        {datos.tiene_codigo_activo && !codigo && (
          <span className="text-xs text-[#605e5c]">Tienes un código activo (empieza por <strong>{datos.prefijo}</strong>, vence {fecha(datos.caduca_en)}). Genera uno nuevo si lo perdiste.</span>
        )}
      </div>

      {datos.equipos.length > 0 && (
        <div className="mt-6">
          <div className="text-sm font-medium mb-2">Mis teléfonos activados</div>
          <ul className="text-sm divide-y divide-[#edebe9] border border-[#edebe9] rounded">
            {datos.equipos.map((e) => (
              <li key={e.id} className="px-3 py-2 flex justify-between gap-2">
                <span>{e.nombre || `${e.fabricante || ''} ${e.modelo || 'Teléfono'}`.trim()} <span className="text-xs text-[#605e5c]">· {e.modo === 'propietario' ? 'administrado' : 'modo limitado'}</span></span>
                <span className="text-xs text-[#605e5c]">{e.estado === 'activo' ? `visto ${fecha(e.ultimo_contacto)}` : e.estado}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
