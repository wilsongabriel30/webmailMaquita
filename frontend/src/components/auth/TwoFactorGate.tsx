import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { TwoFactorSetup } from '../settings/TwoFactorSetup';

/**
 * Puerta de 2FA obligatorio (2026-08-28; no bloqueante desde 2026-11-26).
 * Si el panel admin marca el 2FA como obligatorio y el usuario no lo tiene,
 * muestra un aviso para activarlo. Por decisión de Maquita el aviso es SIEMPRE
 * descartable («Más tarde, ir a mi correo»): nunca deja a nadie fuera de su
 * correo, ni siquiera pasado el plazo; es un recordatorio, no un bloqueo.
 */
interface Policy { required: boolean; deadline: string | null; enrolled: boolean; must_enroll: boolean; blocked: boolean; }

export function TwoFactorGate() {
  const [pol, setPol] = useState<Policy | null>(null);
  const [hidden, setHidden] = useState(() => { try { return sessionStorage.getItem('twofa_gate_dismissed') === '1'; } catch { return false; } });
  const [org, setOrg] = useState('Tu organización');

  const load = () => api.get<Policy>('/auth/2fa-policy/status').then(setPol).catch(() => {});
  useEffect(() => {
    load();
    fetch('/api/branding').then(r => r.json()).then(b => { if (b && b.org_name) setOrg(b.org_name); }).catch(() => {});
  }, []);

  if (!pol || !pol.must_enroll) return null;
  if (hidden) return null;

  const fecha = pol.deadline ? new Date(pol.deadline + 'T00:00:00').toLocaleDateString('es-EC', { dateStyle: 'long' }) : null;
  const dismiss = () => { try { sessionStorage.setItem('twofa_gate_dismissed', '1'); } catch { /* */ } setHidden(true); };

  return (
    <div className="fixed inset-0 z-[9999] bg-black/60 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto p-6">
        <h2 className="text-lg font-semibold mb-2">🔐 Active la verificación en dos pasos</h2>
        <p className="text-sm text-gray-700 mb-3">
          {`Para proteger su cuenta, ${org} pide activar la verificación en dos pasos en todas las cuentas${fecha ? `, de preferencia antes del ${fecha}` : ''}. Puede activarla ahora (también desde Configuración → Seguridad) o seguir a su correo y hacerlo más tarde.`}
        </p>
        <p className="text-xs text-gray-500 mb-4">Necesita una app como Google Authenticator o Microsoft Authenticator en su celular. Guarde los códigos de respaldo en un lugar seguro.</p>
        {/* alActivar: al terminar la activación el aviso se cierra solo (antes seguía en pantalla
            hasta pulsar «Ya la activé»). */}
        <TwoFactorSetup alActivar={load} />
        <div className="flex justify-end gap-2 mt-4">
          {/* «Más tarde» siempre disponible: el 2FA se pide pero nunca se bloquea el correo;
              quien no quiere o no puede hacerlo ahora sigue a su correo sin dudar. */}
          <button onClick={load} className="px-4 py-2 text-[14px] rounded border">Comprobar de nuevo</button>
          <button onClick={dismiss} className="px-4 py-2 text-[14px] rounded bg-blue-600 text-white">Más tarde, ir a mi correo</button>
        </div>
      </div>
    </div>
  );
}
