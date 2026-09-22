import { useCallback, useEffect, useState } from 'react';
import { api } from '../../api/client';
import { MiTelefonoExtraviado } from './MiTelefonoExtraviado';

// «Mi teléfono»: solo lectura desde el 22/09/2026. El código de enrolamiento lo asigna Tecnología desde
// el panel; aquí la persona solo lo ve (para escribirlo en la app si hace falta), con su vencimiento, y
// sus teléfonos activados. No se genera ni se anula nada desde aquí. La app Maquita Mail consulta este
// mismo dato y activa con un toque. NO da acceso al correo: es solo para la gestión del equipo.

interface Equipo { id: number; nombre?: string; modelo?: string; fabricante?: string; estado: string; modo: string; ultimo_contacto?: string }
interface Estado { tiene_codigo_activo: boolean; prefijo?: string; caduca_en?: string; codigo?: string | null; equipos: Equipo[] }

export function MiEquipo() {
  const [datos, setDatos] = useState<Estado | null>(null);
  const [copiado, setCopiado] = useState(false);
  const [error, setError] = useState('');

  const cargar = useCallback(async () => {
    try { setDatos(await api.get<Estado>('/settings/mi-equipo')); }
    catch (e: any) { setError(e.message); }
  }, []);
  useEffect(() => { cargar(); }, [cargar]);

  const copiar = async () => { if (datos?.codigo) { try { await navigator.clipboard.writeText(datos.codigo); setCopiado(true); setTimeout(() => setCopiado(false), 1500); } catch { /* noop */ } } };
  const fecha = (v?: string) => (v ? new Date(v).toLocaleString('es-EC', { dateStyle: 'short', timeStyle: 'short' }) : '');

  return (
    <div className="max-w-2xl">
      <h3 className="text-lg font-semibold">Mi teléfono (app Maquita)</h3>
      <p className="text-sm text-[#605e5c] mt-1">
        Para activar la sección <strong>Mi equipo</strong> de la app en tu teléfono hace falta un código de enrolamiento.
        Si tienes uno asignado, la app lo toma sola al tocar «Activar»; también puedes escribirlo a mano desde aquí.
        Sirve para el respaldo, los mensajes de Tecnología y, si lo autorizas, la ubicación. <strong>No es para leer el
        correo</strong>: el correo en la app entra con tu usuario y tu contraseña de siempre.
      </p>
      {error && <div className="mt-3 text-sm px-3 py-2 rounded bg-red-50 text-red-700">{error}</div>}

      {datos?.codigo ? (
        <div className="mt-4 bg-amber-50 border border-amber-200 rounded p-4">
          <div className="text-xs text-amber-800 mb-1">Tu código de enrolamiento (vence {fecha(datos.caduca_en)}). Escríbelo en la app: Mi equipo → Activar.</div>
          <div className="flex items-center gap-3">
            <code className="text-2xl font-mono tracking-widest">{datos.codigo}</code>
            <button onClick={copiar} className="text-xs text-[#0078d4] hover:underline">{copiado ? 'Copiado' : 'Copiar'}</button>
          </div>
        </div>
      ) : datos?.tiene_codigo_activo ? (
        <div className="mt-4 text-sm px-3 py-2 rounded bg-[#f3f2f1] text-[#323130]">
          Tienes un código vigente (empieza por <strong>{datos.prefijo}</strong>, vence {fecha(datos.caduca_en)}), pero no se puede mostrar aquí. Pídeselo a Tecnología.
        </div>
      ) : datos ? (
        <div className="mt-4 text-sm px-3 py-2 rounded bg-[#f3f2f1] text-[#323130]">No tienes un código asignado en este momento.</div>
      ) : null}
      <p className="mt-2 text-xs text-[#605e5c]">Este código lo asigna Tecnología. Si no tienes uno o venció, pídeselo.</p>

      {datos && datos.equipos.length > 0 && (
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
      <MiTelefonoExtraviado />
    </div>
  );
}
