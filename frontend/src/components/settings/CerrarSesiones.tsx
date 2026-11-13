/**
 * CerrarSesiones.tsx — Sesiones abiertas de su cuenta (punto 4, agrupadas por equipo).
 *
 * Lista las sesiones vivas (GET /api/auth/sesiones) agrupadas por equipo (equipo_id). De cada
 * sesión muestra su nombre claro, un icono según la clase (navegador / móvil / escritorio), el
 * último uso en lenguaje humano, la ubicación y marca «Este dispositivo» en la actual.
 *
 * Cierres (cada uno pide confirmación):
 *  - una sesión            → DELETE /api/auth/sesiones/{sid}
 *  - todo un equipo        → POST   /api/auth/sesiones/equipo/{equipo_id}
 *  - todas menos la actual → POST   /api/auth/sesiones/otras
 *  - todas, incluida esta  → POST   /api/auth/logout-all
 * Si se cierra la sesión actual, se recarga la página (se cae la sesión).
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../../api/client';
import {
  type Sesion,
  TIPOS_SESION,
  iconoClase,
  ultimoUsoHumano,
  fechaHora,
} from '../../lib/formatoSesiones';

interface Equipo {
  id: string;
  nombre: string;
  aproximado: boolean;
  sesiones: Sesion[];
  tieneActual: boolean;
}

/** Agrupa las sesiones por equipo_id; el equipo de esta sesión queda primero. */
function agruparPorEquipo(sesiones: Sesion[]): Equipo[] {
  const mapa = new Map<string, Equipo>();
  for (const s of sesiones) {
    const id = s.equipo_id || s.sid;
    let eq = mapa.get(id);
    if (!eq) {
      eq = {
        id,
        nombre: s.equipo_nombre || 'Equipo sin identificar',
        aproximado: s.equipo_aproximado,
        sesiones: [],
        tieneActual: false,
      };
      mapa.set(id, eq);
    }
    eq.sesiones.push(s);
    if (s.actual) eq.tieneActual = true;
  }
  return Array.from(mapa.values()).sort((a, b) => Number(b.tieneActual) - Number(a.tieneActual));
}

export function CerrarSesiones() {
  const [sesiones, setSesiones] = useState<Sesion[]>([]);
  const [cargando, setCargando] = useState(true);
  const [trabajando, setTrabajando] = useState('');
  const [error, setError] = useState('');
  // Aviso por correo al abrirse la cuenta en un equipo nuevo (encendido por omisión).
  const [avisoNuevo, setAvisoNuevo] = useState<boolean | null>(null);
  useEffect(() => {
    api.get<{ activado: boolean }>('/auth/sesiones/aviso-nuevo-dispositivo')
      .then((r) => setAvisoNuevo(!!r.activado))
      .catch(() => setAvisoNuevo(null));
  }, []);
  const cambiarAviso = async (valor: boolean) => {
    const anterior = avisoNuevo;
    setAvisoNuevo(valor);
    try {
      await api.post('/auth/sesiones/aviso-nuevo-dispositivo', { activado: valor });
    } catch {
      setAvisoNuevo(anterior);
      setError('No se pudo guardar la preferencia del aviso. Inténtelo de nuevo.');
    }
  };

  const cargar = useCallback(async () => {
    try {
      const datos = await api.get<{ sesiones: Sesion[] }>('/auth/sesiones');
      setSesiones(datos.sesiones || []);
      setError('');
    } catch {
      setError('No se pudieron leer las sesiones. Inténtelo de nuevo.');
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => { cargar(); }, [cargar]);

  const equipos = useMemo(() => agruparPorEquipo(sesiones), [sesiones]);
  const hayOtras = sesiones.some((s) => !s.actual);

  const cerrarUna = async (s: Sesion) => {
    const aviso = s.actual
      ? 'Esta es su sesión actual. Si la cierra, se cerrará la sesión en este dispositivo. ¿Desea continuar?'
      : `¿Desea cerrar la sesión «${s.nombre}»?`;
    if (!window.confirm(aviso)) return;
    setTrabajando(s.sid);
    setError('');
    try {
      await api.del('/auth/sesiones/' + encodeURIComponent(s.sid));
      if (s.actual) { window.location.reload(); return; }
      await cargar();
    } catch {
      setError('No se pudo cerrar la sesión. Inténtelo de nuevo.');
    } finally {
      setTrabajando('');
    }
  };

  const cerrarEquipo = async (eq: Equipo) => {
    const aviso = eq.tieneActual
      ? `Se cerrarán todas las sesiones de «${eq.nombre}», incluida la de este dispositivo. ¿Desea continuar?`
      : `Se cerrarán todas las sesiones de «${eq.nombre}». ¿Desea continuar?`;
    if (!window.confirm(aviso)) return;
    setTrabajando('equipo:' + eq.id);
    setError('');
    try {
      await api.post('/auth/sesiones/equipo/' + encodeURIComponent(eq.id));
      if (eq.tieneActual) { window.location.reload(); return; }
      await cargar();
    } catch {
      setError('No se pudieron cerrar las sesiones de este equipo. Inténtelo de nuevo.');
    } finally {
      setTrabajando('');
    }
  };

  const cerrarOtras = async () => {
    if (!window.confirm('Se cerrarán todas las demás sesiones. Esta sesión seguirá abierta. ¿Desea continuar?')) return;
    setTrabajando('otras');
    setError('');
    try {
      await api.post('/auth/sesiones/otras');
      await cargar();
    } catch {
      setError('No se pudieron cerrar las demás sesiones. Inténtelo de nuevo.');
    } finally {
      setTrabajando('');
    }
  };

  const cerrarTodas = async () => {
    if (!window.confirm('Se cerrará su sesión en todos los dispositivos, incluido este. ¿Desea continuar?')) return;
    setTrabajando('todas');
    setError('');
    try {
      await api.post('/auth/logout-all');
      window.location.reload();
    } catch {
      setError('No se pudieron cerrar las sesiones. Inténtelo de nuevo.');
      setTrabajando('');
    }
  };

  const ocupado = trabajando !== '';

  return (
    <div className="mt-6 border-t border-[#edebe9] pt-4">
      <h3 className="text-[13px] font-semibold text-[#323130]">Sesiones abiertas</h3>
      <p className="mt-1 text-[12px] text-[#605e5c]">
        Dispositivos con su cuenta abierta ahora mismo (correo web, aplicación y chat), agrupados por
        equipo. Si no reconoce alguno, ciérrelo; si perdió un equipo o sospecha que alguien más
        entró, cierre todas las sesiones.
      </p>
      {avisoNuevo !== null && (
        <label className="mt-3 flex items-start gap-2 text-[12px] text-[#323130]">
          <input type="checkbox" className="mt-[2px]" checked={avisoNuevo} onChange={(e) => cambiarAviso(e.target.checked)} />
          <span>
            Avisarme por correo cuando mi cuenta se abra en un equipo que no había usado antes.
            <span className="block text-[#605e5c]">Recomendado: si no fue usted, podrá cerrar esa sesión y cambiar su contraseña.</span>
          </span>
        </label>
      )}
      {error && <p className="mt-2 text-[12px] text-[#d13438]">{error}</p>}

      {cargando ? (
        <p className="mt-2 text-[12px] text-[#605e5c]">Cargando…</p>
      ) : equipos.length === 0 ? (
        <p className="mt-3 text-[12px] text-[#605e5c]">No hay sesiones registradas.</p>
      ) : (
        <div className="mt-3 space-y-3">
          {equipos.map((eq) => (
            <div key={eq.id} className="rounded border border-[#edebe9]">
              <div className="flex items-center justify-between gap-3 border-b border-[#edebe9] bg-[#faf9f8] px-3 py-2">
                <div className="min-w-0">
                  <div className="truncate text-[13px] font-semibold text-[#323130]">
                    {eq.nombre}
                    {eq.tieneActual && (
                      <span className="ml-2 rounded bg-[#dff6dd] px-1.5 py-[1px] text-[11px] font-normal text-[#107c10]">
                        este equipo
                      </span>
                    )}
                    {eq.aproximado && (
                      <span
                        className="ml-2 rounded bg-[#f3f2f1] px-1.5 py-[1px] text-[11px] font-normal text-[#605e5c]"
                        title="Identificación aproximada: varias sesiones de navegador pueden parecer el mismo equipo."
                      >
                        aproximado
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] text-[#605e5c]">
                    {eq.sesiones.length === 1 ? '1 sesión' : `${eq.sesiones.length} sesiones`}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => cerrarEquipo(eq)}
                  disabled={ocupado}
                  className="shrink-0 rounded border border-[#8a8886] px-2 py-[3px] text-[12px] text-[#323130] hover:bg-[#f3f2f1] disabled:opacity-50"
                >
                  {trabajando === 'equipo:' + eq.id ? 'Cerrando…' : 'Cerrar todo en este equipo'}
                </button>
              </div>

              <ul className="divide-y divide-[#edebe9]">
                {eq.sesiones.map((s) => (
                  <li key={s.sid} className="flex items-center justify-between gap-3 px-3 py-2">
                    <div className="flex min-w-0 items-start gap-2.5">
                      <svg
                        className="mt-[2px] h-4 w-4 shrink-0 text-[#605e5c]"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                        aria-hidden="true"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={iconoClase(s.clase)} />
                      </svg>
                      <div className="min-w-0">
                        <div className="truncate text-[13px] text-[#323130]" title={s.dispositivo}>
                          {s.nombre}
                          {s.actual && (
                            <span className="ml-2 rounded bg-[#dff6dd] px-1.5 py-[1px] text-[11px] text-[#107c10]">
                              Este dispositivo
                            </span>
                          )}
                          {s.tipo !== 'normal' && (
                            <span className="ml-2 rounded bg-[#fff4ce] px-1.5 py-[1px] text-[11px] text-[#8a6d00]">
                              {TIPOS_SESION[s.tipo] || s.tipo}
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-[#605e5c]">
                          <span title={fechaHora(s.ultimo_uso)}>Último uso: {ultimoUsoHumano(s.ultimo_uso)}</span>
                          {s.ubicacion && <span> · {s.ubicacion}</span>}
                          {s.ip && <span> · IP {s.ip}</span>}
                        </div>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => cerrarUna(s)}
                      disabled={ocupado}
                      className="shrink-0 rounded border border-[#8a8886] px-2 py-[3px] text-[12px] text-[#323130] hover:bg-[#f3f2f1] disabled:opacity-50"
                    >
                      {trabajando === s.sid ? 'Cerrando…' : 'Cerrar'}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        {hayOtras && (
          <button
            type="button"
            onClick={cerrarOtras}
            disabled={ocupado || cargando}
            className="rounded border border-[#8a8886] px-3 py-[5px] text-[13px] text-[#323130] hover:bg-[#f3f2f1] disabled:opacity-50"
          >
            {trabajando === 'otras' ? 'Cerrando…' : 'Cerrar todas las demás'}
          </button>
        )}
        <button
          type="button"
          onClick={cerrarTodas}
          disabled={ocupado || cargando}
          className="rounded border border-[#d13438] px-3 py-[5px] text-[13px] text-[#d13438] hover:bg-[#fde7e9] disabled:opacity-50"
        >
          {trabajando === 'todas' ? 'Cerrando…' : 'Cerrar todas las sesiones'}
        </button>
      </div>
    </div>
  );
}
