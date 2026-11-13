/**
 * SesionesAdmin.tsx — Sesiones abiertas de todas las cuentas (punto 5, solo administradores).
 *
 * Vista de Tecnología dentro del panel de administración del correo. Muestra las sesiones vivas
 * de todas las cuentas con filtro por persona, clase de dispositivo y antigüedad, un botón para
 * cerrar todas las sesiones de una cuenta, y un panel-resumen (cuentas con muchas sesiones,
 * sesiones sin uso en 30 días y sesiones de aplicación por versión).
 *
 * NO muestra contenido de correos: solo metadatos de la sesión (dispositivo, ubicación, uso).
 *
 * Backend (lo provee la sesión principal; si la forma difiere al integrar, ajustar las llamadas):
 *   GET  /api/admin/sesiones?persona=&clase=&antiguedad=
 *   POST /api/admin/sesiones/cuenta/{username}/cerrar-todas
 *   GET  /api/admin/sesiones/resumen
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../../api/client';
import {
  type Sesion,
  CLASES_SESION,
  iconoClase,
  ultimoUsoHumano,
  fechaHora,
} from '../../lib/formatoSesiones';

interface CuentaSesiones {
  username: string;
  nombre?: string;
  sesiones: Sesion[];
}

interface ResumenAppVersion {
  version: string;
  total: number;
}

interface Resumen {
  cuentas_con_muchas_sesiones: number;
  sin_uso_30_dias: number;
  app_por_version: ResumenAppVersion[] | Record<string, number>;
}

const CLASES_FILTRO: { valor: string; etiqueta: string }[] = [
  { valor: '', etiqueta: 'Todas las clases' },
  { valor: 'navegador', etiqueta: 'Navegador web' },
  { valor: 'app_movil', etiqueta: 'Aplicación móvil' },
  { valor: 'app_escritorio', etiqueta: 'Aplicación de escritorio' },
  { valor: 'otro', etiqueta: 'Otro dispositivo' },
];

const ANTIGUEDAD_FILTRO: { valor: string; etiqueta: string }[] = [
  { valor: '', etiqueta: 'Cualquier antigüedad' },
  { valor: '7', etiqueta: 'Sin uso en 7 días' },
  { valor: '30', etiqueta: 'Sin uso en 30 días' },
  { valor: '90', etiqueta: 'Sin uso en 90 días' },
];

/** Normaliza app_por_version a lista ordenada de mayor a menor, venga como objeto o como lista. */
function normalizarVersiones(datos: Resumen['app_por_version'] | undefined): ResumenAppVersion[] {
  if (!datos) return [];
  const lista = Array.isArray(datos)
    ? datos
    : Object.entries(datos).map(([version, total]) => ({ version, total }));
  return [...lista].sort((a, b) => b.total - a.total);
}

export function SesionesAdmin() {
  const [cuentas, setCuentas] = useState<CuentaSesiones[]>([]);
  const [resumen, setResumen] = useState<Resumen | null>(null);
  const [cargando, setCargando] = useState(true);
  const [trabajando, setTrabajando] = useState('');
  const [error, setError] = useState('');

  const [persona, setPersona] = useState('');
  const [clase, setClase] = useState('');
  const [antiguedad, setAntiguedad] = useState('');

  const cargar = useCallback(async () => {
    setCargando(true);
    setError('');
    try {
      const params = new URLSearchParams();
      if (persona) params.set('persona', persona);
      if (clase) params.set('clase', clase);
      if (antiguedad) params.set('antiguedad', antiguedad);
      const sufijo = params.toString() ? `?${params.toString()}` : '';
      const datos = await api.get<{ cuentas: CuentaSesiones[] }>(`/admin/sesiones${sufijo}`);
      setCuentas(datos.cuentas || []);
    } catch {
      setError('No se pudieron leer las sesiones. Inténtelo de nuevo.');
    } finally {
      setCargando(false);
    }
  }, [persona, clase, antiguedad]);

  const cargarResumen = useCallback(async () => {
    try {
      setResumen(await api.get<Resumen>('/admin/sesiones/resumen'));
    } catch {
      // El resumen es complementario: si falla, la lista sigue siendo útil.
      setResumen(null);
    }
  }, []);

  // Debounce ligero del filtro por persona para no pedir en cada tecla (conexiones lentas).
  useEffect(() => {
    const t = setTimeout(() => { cargar(); }, 300);
    return () => clearTimeout(t);
  }, [cargar]);

  useEffect(() => { cargarResumen(); }, [cargarResumen]);

  const versiones = useMemo(() => normalizarVersiones(resumen?.app_por_version), [resumen]);
  const totalSesiones = useMemo(
    () => cuentas.reduce((suma, c) => suma + (c.sesiones?.length || 0), 0),
    [cuentas],
  );

  const cerrarCuenta = async (c: CuentaSesiones) => {
    const nombre = c.nombre || c.username;
    if (!window.confirm(
      `Se cerrarán todas las sesiones de «${nombre}» (${c.sesiones.length}). ` +
      'La persona tendrá que volver a iniciar sesión. ¿Desea continuar?',
    )) return;
    setTrabajando(c.username);
    setError('');
    try {
      await api.post(`/admin/sesiones/cuenta/${encodeURIComponent(c.username)}/cerrar-todas`);
      await cargar();
      await cargarResumen();
    } catch {
      setError(`No se pudieron cerrar las sesiones de ${nombre}. Inténtelo de nuevo.`);
    } finally {
      setTrabajando('');
    }
  };

  return (
    <div className="p-8 max-w-5xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800">Sesiones por dispositivo</h1>
        <p className="text-sm text-slate-500 mt-1">
          Sesiones abiertas de todas las cuentas. Aquí solo se ven los datos de la sesión
          (dispositivo, ubicación y uso); nunca el contenido de los correos.
        </p>
      </div>

      {/* Panel-resumen */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <p className="text-xs text-slate-500">Cuentas con muchas sesiones</p>
          <p className="mt-1 text-2xl font-semibold text-slate-800">
            {resumen ? resumen.cuentas_con_muchas_sesiones : '—'}
          </p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <p className="text-xs text-slate-500">Sesiones sin uso en 30 días</p>
          <p className="mt-1 text-2xl font-semibold text-slate-800">
            {resumen ? resumen.sin_uso_30_dias : '—'}
          </p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <p className="text-xs text-slate-500">Sesiones de la aplicación por versión</p>
          {versiones.length === 0 ? (
            <p className="mt-1 text-sm text-slate-400">Sin datos</p>
          ) : (
            <ul className="mt-1 space-y-0.5">
              {versiones.map((v) => (
                <li key={v.version} className="flex justify-between text-sm text-slate-700">
                  <span className="truncate">{v.version || 'sin versión'}</span>
                  <span className="font-medium">{v.total}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Filtros */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <input
          value={persona}
          onChange={(e) => setPersona(e.target.value)}
          placeholder="Buscar por persona o cuenta…"
          className="px-3 py-2 border border-slate-300 rounded-lg text-sm w-64"
        />
        <select
          value={clase}
          onChange={(e) => setClase(e.target.value)}
          className="px-3 py-2 border border-slate-300 rounded-lg text-sm"
        >
          {CLASES_FILTRO.map((o) => (
            <option key={o.valor} value={o.valor}>{o.etiqueta}</option>
          ))}
        </select>
        <select
          value={antiguedad}
          onChange={(e) => setAntiguedad(e.target.value)}
          className="px-3 py-2 border border-slate-300 rounded-lg text-sm"
        >
          {ANTIGUEDAD_FILTRO.map((o) => (
            <option key={o.valor} value={o.valor}>{o.etiqueta}</option>
          ))}
        </select>
      </div>

      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      {cargando ? (
        <div className="text-center py-8 text-slate-400">Cargando…</div>
      ) : cuentas.length === 0 ? (
        <div className="text-center py-12 text-slate-400">No hay sesiones que coincidan con el filtro.</div>
      ) : (
        <>
          <p className="text-sm text-slate-400 mb-3">
            {cuentas.length === 1 ? '1 cuenta' : `${cuentas.length} cuentas`} · {totalSesiones} sesiones
          </p>
          <div className="space-y-4">
            {cuentas.map((c) => (
              <div key={c.username} className="rounded-lg border border-slate-200">
                <div className="flex items-center justify-between gap-3 border-b border-slate-200 bg-slate-50 px-4 py-3 rounded-t-lg">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-slate-800">
                      {c.nombre || c.username}
                    </p>
                    {c.nombre && <p className="truncate text-xs text-slate-500">{c.username}</p>}
                    <p className="text-xs text-slate-500">
                      {c.sesiones.length === 1 ? '1 sesión' : `${c.sesiones.length} sesiones`}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => cerrarCuenta(c)}
                    disabled={trabajando !== ''}
                    className="shrink-0 rounded-lg border border-red-300 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 disabled:opacity-50"
                  >
                    {trabajando === c.username ? 'Cerrando…' : 'Cerrar todas las de esta cuenta'}
                  </button>
                </div>
                <ul className="divide-y divide-slate-100">
                  {c.sesiones.map((s) => (
                    <li key={s.sid} className="flex items-start gap-3 px-4 py-2.5">
                      <svg
                        className="mt-[2px] h-4 w-4 shrink-0 text-slate-400"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                        aria-hidden="true"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={iconoClase(s.clase)} />
                      </svg>
                      <div className="min-w-0">
                        <p className="truncate text-sm text-slate-700" title={s.dispositivo}>
                          {s.nombre}
                          <span className="ml-2 text-xs text-slate-400">
                            {CLASES_SESION[s.clase] || s.clase}
                          </span>
                        </p>
                        <p className="text-xs text-slate-500">
                          <span title={fechaHora(s.ultimo_uso)}>Último uso: {ultimoUsoHumano(s.ultimo_uso)}</span>
                          {s.ubicacion && <span> · {s.ubicacion}</span>}
                          {s.ip && <span> · IP {s.ip}</span>}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
