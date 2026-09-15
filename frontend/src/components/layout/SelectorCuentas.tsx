// Cuentas de la persona (como en Outlook): la principal y las que le asignaron en el panel.
// Al elegir otra, TODO el webmail pasa a esa cuenta (correo, calendario, contactos, drive...):
// el servidor abre una sesión completa de esa cuenta y la página se recarga. La activa se
// marca con su color; el mismo color acompaña como franja mientras se trabaja en ella.
import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { showToast } from '../common/Toast';

interface CuentaSesion { email: string; nombre: string; principal: boolean; activa: boolean }

const PALETA = ['#0078d4', '#107c10', '#8661c5', '#d83b01', '#c239b3', '#038387', '#ca5010', '#4f6bed'];

/** Color estable por cuenta (mismo correo, mismo color siempre). */
export function colorDeCuenta(email: string): string {
  let h = 0;
  for (const ch of email.toLowerCase()) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return PALETA[h % PALETA.length];
}

function iniciales(c: CuentaSesion): string {
  const base = c.nombre || c.email.split('@')[0];
  return base.split(/[\s.]+/).filter(Boolean).slice(0, 2).map(p => p[0]).join('').toUpperCase();
}

export function SelectorCuentas() {
  const [cuentas, setCuentas] = useState<CuentaSesion[]>([]);
  const [cambiando, setCambiando] = useState<string | null>(null);

  useEffect(() => {
    api.get<{ cuentas: CuentaSesion[] }>('/auth/cuentas').then(r => setCuentas(r.cuentas)).catch(() => {});
  }, []);

  const activa = cuentas.find(c => c.activa);
  useEffect(() => {
    // Franja de color de la cuenta activa (la usa el resto de la interfaz vía CSS)
    const color = activa ? colorDeCuenta(activa.email) : '';
    document.documentElement.style.setProperty('--cuenta-activa', color || '#0078d4');
  }, [activa?.email]);

  if (cuentas.length < 2) return null;

  const cambiar = async (c: CuentaSesion) => {
    if (c.activa || cambiando) return;
    setCambiando(c.email);
    try {
      await api.post('/auth/cuentas/cambiar', { cuenta: c.email });
      // Sesión nueva en las cookies: se recarga para que correo, calendario, drive... sean de esa cuenta.
      window.location.href = '/webmail/';
    } catch (e: any) {
      showToast(e?.message || 'No se pudo cambiar de cuenta');
      setCambiando(null);
    }
  };

  return (
    <div className="px-2 pt-2 pb-1 border-b border-[#edebe9]" style={{ borderTop: `3px solid ${activa ? colorDeCuenta(activa.email) : '#0078d4'}` }}>
      <div className="px-1 pb-1 text-[10px] font-semibold text-[#605e5c] uppercase tracking-wide">Cuentas</div>
      {cuentas.map(c => {
        const color = colorDeCuenta(c.email);
        return (
          <button key={c.email} onClick={() => cambiar(c)} disabled={!!cambiando}
            title={c.activa ? `Cuenta activa: ${c.email}` : `Cambiar a ${c.email}${c.principal ? ' (tu cuenta)' : ' (asignada)'}: correo, calendario y archivos de esa cuenta`}
            className={`w-full flex items-center gap-2 px-2 py-[5px] rounded-sm text-left transition-colors ${c.activa ? 'bg-white shadow-sm' : 'hover:bg-[#f3f2f1]'}`}
            style={c.activa ? { borderLeft: `3px solid ${color}` } : { borderLeft: '3px solid transparent' }}>
            <span className="w-6 h-6 rounded-full flex items-center justify-center text-white text-[10px] font-semibold shrink-0"
              style={{ backgroundColor: color, opacity: c.activa ? 1 : 0.75 }}>{iniciales(c)}</span>
            <span className="min-w-0 flex-1">
              <span className={`block truncate text-[12px] ${c.activa ? 'font-semibold text-[#201f1e]' : 'text-[#323130]'}`}>{c.nombre || c.email.split('@')[0]}</span>
              <span className="block truncate text-[10px] text-[#605e5c]">{c.email}</span>
            </span>
            {c.activa && <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: color }} title="Activa" />}
            {cambiando === c.email && <span className="w-3 h-3 border-2 border-[#0078d4] border-t-transparent rounded-full animate-spin" />}
          </button>
        );
      })}
    </div>
  );
}
