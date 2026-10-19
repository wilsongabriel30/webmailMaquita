/**
 * Archivo → «Información de la cuenta»: datos reales del buzón abierto.
 * Antes el botón mostraba un aviso con un correo de ejemplo fijo (19/10/2026).
 * Muestra: dirección y nombre, alias que entregan aquí, cuentas delegadas, espacio usado
 * (IMAP GETQUOTAROOT vía /mail/stats), conteos de carpetas y accesos a Configuración.
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import { useMailStore } from '../../store/mailStore';
import { useAuthStore } from '../../store/authStore';

interface Stats {
  inbox_total: number; inbox_unread: number; sent_total: number; drafts: number; trash: number;
  storage_used_mb: number; storage_limit_mb?: number | null;
}

function mb(v: number): string {
  return v >= 1024 ? `${(v / 1024).toFixed(2)} GB` : `${Math.round(v)} MB`;
}

export function InfoCuentaModal({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const user = useAuthStore(s => s.user) as { username?: string; is_admin?: boolean } | null;
  const cuentas = useMailStore(s => s.cuentas);
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState('');

  const propia = cuentas.find(c => c.propia) || cuentas[0];
  const correo = propia?.email || user?.username || '';
  const nombre = propia?.nombre || '';
  const alias = propia?.alias || [];
  const delegadas = cuentas.filter(c => !c.propia);

  useEffect(() => {
    api.get<Stats>('/mail/stats').then(setStats).catch(() => setError('No se pudo leer el espacio usado.'));
  }, []);

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', h);
    return () => document.removeEventListener('keydown', h);
  }, [onClose]);

  const limite = stats?.storage_limit_mb || 0;
  const usado = stats?.storage_used_mb || 0;
  const pct = limite > 0 ? Math.min(100, Math.round((usado / limite) * 100)) : 0;
  const fila = 'flex justify-between gap-4 py-1.5 border-b border-[#f3f2f1] dark:border-[#333] text-[13px]';
  const etiqueta = 'text-[#605e5c] dark:text-[#a0a0a0] shrink-0';
  const ir = (tab: string) => { onClose(); navigate(`/settings?tab=${tab}`); };

  return (
    <div className="fixed inset-0 z-[300] flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-labelledby="info-cuenta-titulo"
        className="w-full max-w-[520px] bg-white dark:bg-[#1e1e1e] text-[#323130] dark:text-[#e0e0e0] rounded shadow-xl"
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-3 border-b border-[#edebe9] dark:border-[#333]">
          <h2 id="info-cuenta-titulo" className="text-[15px] font-semibold">Información de la cuenta</h2>
          <button type="button" onClick={onClose} aria-label="Cerrar" className="w-8 h-8 rounded hover:bg-[#f3f2f1] dark:hover:bg-[#333]">✕</button>
        </div>
        <div className="px-5 py-3">
          <div className={fila}><span className={etiqueta}>Correo</span><span className="font-medium break-all text-right">{correo}</span></div>
          {nombre && <div className={fila}><span className={etiqueta}>Nombre</span><span className="text-right">{nombre}</span></div>}
          {alias.length > 0 && (
            <div className={fila}><span className={etiqueta}>Alias (llegan a este buzón)</span><span className="text-right break-all">{alias.join(', ')}</span></div>
          )}
          {delegadas.length > 0 && (
            <div className={fila}><span className={etiqueta}>Cuentas compartidas contigo</span>
              <span className="text-right break-all">{delegadas.map(c => c.email).join(', ')}</span></div>
          )}
          {user?.is_admin && <div className={fila}><span className={etiqueta}>Rol</span><span>Administrador del correo</span></div>}

          <div className="mt-3 text-[13px]">
            <div className="flex justify-between"><span className={etiqueta}>Espacio usado</span>
              <span>{stats ? (limite > 0 ? `${mb(usado)} de ${mb(limite)} (${pct} %)` : mb(usado)) : (error || 'Calculando…')}</span></div>
            {limite > 0 && (
              <div className="h-2 mt-1 rounded bg-[#edebe9] dark:bg-[#333] overflow-hidden" aria-hidden="true">
                <div className={`h-full ${pct >= 90 ? 'bg-[#d13438]' : pct >= 75 ? 'bg-[#ffb900]' : 'bg-[#0078d4]'}`} style={{ width: `${pct}%` }} />
              </div>
            )}
          </div>

          {stats && (
            <div className="grid grid-cols-4 gap-2 mt-3 text-center">
              {[
                ['Bandeja', stats.inbox_total], ['Sin leer', stats.inbox_unread],
                ['Enviados', stats.sent_total], ['Borradores', stats.drafts],
              ].map(([t, v]) => (
                <div key={String(t)} className="rounded bg-[#f3f2f1] dark:bg-[#2a2a2a] py-2">
                  <div className="text-[16px] font-semibold">{v as number}</div>
                  <div className="text-[11px] text-[#605e5c] dark:text-[#a0a0a0]">{t}</div>
                </div>
              ))}
            </div>
          )}

          <div className="flex flex-wrap gap-2 mt-4">
            <button type="button" onClick={() => ir('mailsetup')} className="px-3 py-1.5 text-[12px] rounded border border-[#c8c6c4] hover:bg-[#f3f2f1] dark:hover:bg-[#333]">Configurar en Outlook o celular</button>
            <button type="button" onClick={() => ir('password')} className="px-3 py-1.5 text-[12px] rounded border border-[#c8c6c4] hover:bg-[#f3f2f1] dark:hover:bg-[#333]">Cambiar contraseña</button>
            <button type="button" onClick={() => ir('security')} className="px-3 py-1.5 text-[12px] rounded border border-[#c8c6c4] hover:bg-[#f3f2f1] dark:hover:bg-[#333]">Seguridad</button>
          </div>
        </div>
      </div>
    </div>
  );
}
