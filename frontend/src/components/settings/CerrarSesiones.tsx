/**
 * CerrarSesiones.tsx — Sesiones abiertas de la cuenta (L-01, cuarta revisión).
 *
 * Lista las sesiones vivas (GET /api/auth/sesiones): dispositivo, IP, fecha y tipo, con la
 * actual marcada. Cada una se puede cerrar por su sid (DELETE /api/auth/sesiones/{sid});
 * «Cerrar todas» (POST /api/auth/logout-all) sube la generación de autenticación y cierra
 * webmail, app y chat en todos los dispositivos, incluido este.
 */

import { useCallback, useEffect, useState } from 'react';

interface Sesion {
  sid: string;
  tipo: string;
  dispositivo: string;
  ip: string;
  creada: number;
  vence: number;
  actual: boolean;
}

const TIPOS: Record<string, string> = {
  normal: 'Sesión',
  impersonate: 'Acceso de administración',
  service: 'Servicio',
};

function dispositivoCorto(ua: string): string {
  if (!ua) return 'Dispositivo desconocido';
  const navegador =
    /Edg\//.test(ua) ? 'Edge' :
    /OPR\//.test(ua) ? 'Opera' :
    /Chrome\//.test(ua) ? 'Chrome' :
    /Firefox\//.test(ua) ? 'Firefox' :
    /Safari\//.test(ua) ? 'Safari' :
    /Maquita/i.test(ua) ? 'App Maquita' : ua.slice(0, 40);
  const sistema =
    /Android/.test(ua) ? 'Android' :
    /iPhone|iPad/.test(ua) ? 'iOS' :
    /Windows/.test(ua) ? 'Windows' :
    /Mac OS/.test(ua) ? 'macOS' :
    /Linux/.test(ua) ? 'Linux' : '';
  return sistema ? `${navegador} · ${sistema}` : navegador;
}

function fecha(segundos: number): string {
  if (!segundos) return '';
  return new Date(segundos * 1000).toLocaleString('es-EC', { dateStyle: 'short', timeStyle: 'short' });
}

export function CerrarSesiones() {
  const [sesiones, setSesiones] = useState<Sesion[]>([]);
  const [cargando, setCargando] = useState(true);
  const [trabajando, setTrabajando] = useState('');
  const [error, setError] = useState('');

  const cargar = useCallback(async () => {
    try {
      const r = await fetch('/api/auth/sesiones', { credentials: 'include' });
      if (!r.ok) throw new Error('No se pudo leer las sesiones');
      const datos = (await r.json()) as { sesiones: Sesion[] };
      setSesiones(datos.sesiones || []);
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo leer las sesiones');
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => { cargar(); }, [cargar]);

  const cerrarUna = async (s: Sesion) => {
    if (s.actual && !window.confirm('Esta es tu sesión actual. ¿Cerrarla?')) return;
    setTrabajando(s.sid);
    setError('');
    try {
      const r = await fetch('/api/auth/sesiones/' + encodeURIComponent(s.sid), {
        method: 'DELETE',
        credentials: 'include',
      });
      if (!r.ok) throw new Error('No se pudo cerrar la sesión');
      if (s.actual) { window.location.reload(); return; }
      await cargar();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo cerrar la sesión');
    } finally {
      setTrabajando('');
    }
  };

  const cerrarTodas = async () => {
    if (!window.confirm('Se cerrará tu sesión en todos los dispositivos, incluido este. ¿Continuar?')) return;
    setTrabajando('*');
    setError('');
    try {
      const r = await fetch('/api/auth/logout-all', { method: 'POST', credentials: 'include' });
      if (!r.ok) throw new Error('No se pudo cerrar las sesiones');
      window.location.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo cerrar las sesiones');
      setTrabajando('');
    }
  };

  return (
    <div className="mt-6 border-t border-[#edebe9] pt-4">
      <h3 className="text-[13px] font-semibold text-[#323130]">Sesiones abiertas</h3>
      <p className="mt-1 text-[12px] text-[#605e5c]">
        Dispositivos con tu cuenta abierta ahora mismo (webmail, app y chat). Si no reconoces
        alguno, ciérralo; si perdiste un equipo o sospechas que alguien más entró, cierra todas.
      </p>
      {error && <p className="mt-2 text-[12px] text-[#d13438]">{error}</p>}
      {cargando ? (
        <p className="mt-2 text-[12px] text-[#605e5c]">Cargando…</p>
      ) : (
        <ul className="mt-3 divide-y divide-[#edebe9] rounded border border-[#edebe9]">
          {sesiones.map((s) => (
            <li key={s.sid} className="flex items-center justify-between gap-3 px-3 py-2">
              <div className="min-w-0">
                <div className="truncate text-[13px] text-[#323130]" title={s.dispositivo}>
                  {dispositivoCorto(s.dispositivo)}
                  {s.actual && (
                    <span className="ml-2 rounded bg-[#dff6dd] px-1.5 py-[1px] text-[11px] text-[#107c10]">
                      esta sesión
                    </span>
                  )}
                  {s.tipo !== 'normal' && (
                    <span className="ml-2 rounded bg-[#fff4ce] px-1.5 py-[1px] text-[11px] text-[#8a6d00]">
                      {TIPOS[s.tipo] || s.tipo}
                    </span>
                  )}
                </div>
                <div className="text-[11px] text-[#605e5c]">
                  {s.ip && <span>IP {s.ip} · </span>}
                  <span>desde {fecha(s.creada)}</span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => cerrarUna(s)}
                disabled={trabajando !== ''}
                className="shrink-0 rounded border border-[#8a8886] px-2 py-[3px] text-[12px] text-[#323130] hover:bg-[#f3f2f1] disabled:opacity-50"
              >
                {trabajando === s.sid ? 'Cerrando…' : 'Cerrar'}
              </button>
            </li>
          ))}
          {sesiones.length === 0 && (
            <li className="px-3 py-2 text-[12px] text-[#605e5c]">No hay sesiones registradas.</li>
          )}
        </ul>
      )}
      <button
        type="button"
        onClick={cerrarTodas}
        disabled={trabajando !== ''}
        className="mt-3 rounded border border-[#d13438] px-3 py-[5px] text-[13px] text-[#d13438] hover:bg-[#fde7e9] disabled:opacity-50"
      >
        {trabajando === '*' ? 'Cerrando…' : 'Cerrar todas las sesiones'}
      </button>
    </div>
  );
}
