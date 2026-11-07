/**
 * RemitentesBloqueados.tsx — Configuración → Remitentes bloqueados (05/11/2026).
 *
 * Su correo va siempre a «Correo no deseado». La lista se llena sola al pulsar «Marcar como spam»
 * y se vacía con «No es spam»; aquí se puede ver, buscar, agregar y quitar a mano.
 * Bloquear no borra nada: el correo sigue llegando, pero a No deseado.
 * API: GET/POST /api/mail/remitentes-bloqueados, DELETE ?correo=.
 */

import { useCallback, useEffect, useState } from 'react';
import { api } from '../../api/client';
import { showToast } from '../common/Toast';

interface Listado {
  remitentes: string[];
  maximo: number;
}

export function RemitentesBloqueados() {
  const [datos, setDatos] = useState<Listado>({ remitentes: [], maximo: 500 });
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState(false);
  const [nuevo, setNuevo] = useState('');
  const [filtro, setFiltro] = useState('');
  const [error, setError] = useState('');
  const [ocupado, setOcupado] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    setErrorCarga(false);
    try { setDatos(await api.get<Listado>('/mail/remitentes-bloqueados')); }
    catch { setErrorCarga(true); }
    finally { setCargando(false); }
  }, []);

  useEffect(() => { cargar(); }, [cargar]);

  const agregar = async () => {
    setError('');
    const correo = nuevo.trim().toLowerCase();
    if (!correo.includes('@')) { setError('Escribe el correo completo del remitente'); return; }
    setOcupado(true);
    try {
      const r = await api.post<{ remitentes: string[] }>('/mail/remitentes-bloqueados', { correo });
      setDatos(d => ({ ...d, remitentes: r.remitentes }));
      setNuevo('');
      showToast(`${correo} bloqueado: sus correos irán a Correo no deseado`);
    } catch (e: unknown) {
      setError(e instanceof Error && e.message ? e.message : 'No se pudo bloquear');
    } finally { setOcupado(false); }
  };

  const quitar = async (correo: string) => {
    if (!window.confirm(`¿Desbloquear a ${correo}?\n\nSus próximos correos volverán a pasar por el filtro normal.`)) return;
    try {
      const r = await api.del<{ remitentes: string[] }>(`/mail/remitentes-bloqueados?correo=${encodeURIComponent(correo)}`);
      setDatos(d => ({ ...d, remitentes: r.remitentes }));
      showToast(`${correo} desbloqueado`);
    } catch { showToast('No se pudo desbloquear. Inténtelo de nuevo.', undefined, { fijo: true }); }
  };

  const visibles = datos.remitentes.filter(r => r.includes(filtro.trim().toLowerCase()));

  return (
    <div className="space-y-4">
      <div className="bg-[#deecf9] p-3 rounded text-sm text-[#323130]">
        <p className="font-medium mb-1">Remitentes bloqueados</p>
        <p className="text-xs text-[#605e5c]">
          Los correos de estas direcciones van siempre a «Correo no deseado». Se agregan solos cuando marcas un
          correo como spam. No se borra nada: si bloqueaste a alguien por error, quítalo de aquí o abre su correo
          en No deseado y pulsa «No es spam».
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-2 sm:items-end">
        <label className="flex-1 text-sm text-[#605e5c]">
          Bloquear un remitente
          <input value={nuevo} onChange={e => setNuevo(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') agregar(); }}
            placeholder="boletines@ejemplo.com" maxLength={320} aria-label="Correo del remitente a bloquear"
            className="mt-1 w-full px-3 py-2 border border-[#8a8886] rounded text-sm text-[#323130] focus:outline-none focus:border-[#0078d4]" />
        </label>
        <button onClick={agregar} disabled={ocupado || !nuevo.trim() || datos.remitentes.length >= datos.maximo}
          className="px-4 py-2 rounded bg-[#0078d4] text-white text-sm hover:bg-[#106ebe] disabled:opacity-50">
          {ocupado ? 'Bloqueando…' : 'Bloquear'}
        </button>
      </div>
      {error && <div className="text-sm text-[#a4262c]">{error}</div>}

      {cargando ? (
        <div className="text-sm text-[#605e5c]" role="status">Cargando remitentes bloqueados…</div>
      ) : errorCarga ? (
        <div role="alert" className="p-4 rounded border border-[#a4262c] bg-[#fde7e9] text-[#323130]">
          <p className="text-sm font-semibold text-[#a4262c]">No se pudo cargar la lista</p>
          <p className="text-sm mt-1">No se ha borrado nada: solo no pudimos leerla en este momento.</p>
          <button type="button" onClick={cargar}
            className="mt-3 px-4 py-2 bg-[#0078d4] text-white text-sm rounded hover:bg-[#106ebe]">
            Reintentar
          </button>
        </div>
      ) : datos.remitentes.length === 0 ? (
        <div className="text-center py-12 text-[#a19f9d]">
          <p className="text-sm font-medium">No tienes remitentes bloqueados</p>
          <p className="text-xs mt-1">Cuando marques un correo como spam, su remitente aparecerá aquí</p>
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm text-[#605e5c]">
              {datos.remitentes.length} remitente{datos.remitentes.length !== 1 ? 's' : ''} bloqueado{datos.remitentes.length !== 1 ? 's' : ''}
            </span>
            {datos.remitentes.length > 8 && (
              <input value={filtro} onChange={e => setFiltro(e.target.value)} placeholder="Buscar…" aria-label="Buscar remitente bloqueado"
                className="px-3 py-1.5 border border-[#8a8886] rounded text-sm focus:outline-none focus:border-[#0078d4] w-48" />
            )}
          </div>
          <ul className="divide-y divide-[#f3f2f1] border border-[#edebe9] rounded">
            {visibles.map(r => (
              <li key={r} className="flex items-center justify-between px-3 py-2 hover:bg-[#faf9f8]">
                <span className="text-sm text-[#323130] truncate" title={r}>{r}</span>
                <button onClick={() => quitar(r)}
                  className="text-[13px] text-[#0078d4] hover:bg-[#deecf9] px-2 py-1 rounded shrink-0">
                  Desbloquear
                </button>
              </li>
            ))}
            {visibles.length === 0 && (
              <li className="px-3 py-3 text-sm text-[#a19f9d]">Ningún remitente coincide con «{filtro}»</li>
            )}
          </ul>
        </>
      )}
    </div>
  );
}
