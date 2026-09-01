import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { TwoFactorSetup } from '../settings/TwoFactorSetup';

/**
 * Puerta de 2FA obligatorio (2026-08-28).
 * Si el panel admin marca el 2FA como obligatorio y el usuario no lo tiene,
 * muestra un aviso: descartable hasta la fecha límite, bloqueante después.
 */
interface Policy { required: boolean; deadline: string | null; enrolled: boolean; must_enroll: boolean; blocked: boolean; }

export function TwoFactorGate() {
  const [pol, setPol] = useState<Policy | null>(null);
  const [hidden, setHidden] = useState(false);

  const load = () => api.get<Policy>('/auth/2fa-policy/status').then(setPol).catch(() => {});
  useEffect(() => {
    load();
    try { if (sessionStorage.getItem('twofa_gate_dismissed') === '1') setHidden(true); } catch { /* sin storage */ }
  }, []);

  if (!pol || !pol.must_enroll) return null;
  if (hidden && !pol.blocked) return null;

  const fecha = pol.deadline ? new Date(pol.deadline + 'T00:00:00').toLocaleDateString('es-EC', { dateStyle: 'long' }) : null;
  const dismiss = () => { try { sessionStorage.setItem('twofa_gate_dismissed', '1'); } catch { /* */ } setHidden(true); };

  return (
    <div className="fixed inset-0 z-[9999] bg-black/60 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto p-6">
        <h2 className="text-lg font-semibold mb-2">🔐 Verificación en dos pasos obligatoria</h2>
        <p className="text-sm text-gray-700 mb-3">
          {pol.blocked
            ? 'Para proteger tu cuenta, Fundación Maquita exige la verificación en dos pasos. Debes activarla ahora para seguir usando el correo.'
            : `Fundación Maquita exige la verificación en dos pasos para todas las cuentas. Actívala ahora; a partir del ${fecha ?? 'plazo indicado'} será obligatoria para entrar.`}
        </p>
        <p className="text-xs text-gray-500 mb-4">Necesitas una app como Google Authenticator o Microsoft Authenticator en tu celular. Guarda los códigos de respaldo en un lugar seguro.</p>
        <TwoFactorSetup />
        <div className="flex justify-end gap-2 mt-4">
          <button onClick={load} className="px-3 py-2 text-sm rounded bg-blue-600 text-white">Ya la activé</button>
          {!pol.blocked && <button onClick={dismiss} className="px-3 py-2 text-sm rounded border">Más tarde</button>}
        </div>
      </div>
    </div>
  );
}
