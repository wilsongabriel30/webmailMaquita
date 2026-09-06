import { useState, useCallback, useEffect } from 'react';
import { api } from '../../api/client';
import { showToast } from '../common/Toast';

interface TotpStatus {
  enabled: boolean;
  verified_at?: string;
  backup_codes_remaining?: number;
}

interface SetupData {
  secret: string;
  qr_code: string;
  backup_codes: string[];
  uri: string;
}

export function TwoFactorSetup() {
  const [status, setStatus] = useState<TotpStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [setupData, setSetupData] = useState<SetupData | null>(null);
  const [verifyCode, setVerifyCode] = useState('');
  const [disableCode, setDisableCode] = useState('');
  const [showDisable, setShowDisable] = useState(false);
  const [step, setStep] = useState<'idle' | 'setup' | 'backup'>('idle');
  const [askPassword, setAskPassword] = useState(false);
  const [setupPassword, setSetupPassword] = useState('');
  const [regenCode, setRegenCode] = useState('');
  const [showRegen, setShowRegen] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await api.get('/auth/totp/status');
      setStatus(res as TotpStatus);
    } catch {
      setStatus({ enabled: false });
    }
  }, []);

  // Fetch on mount
  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  const startSetup = useCallback(async () => {
    if (!setupPassword.trim()) { showToast('Ingresa tu contraseña actual'); return; }
    setLoading(true);
    try {
      const res = await api.post('/auth/totp/setup', { password: setupPassword });
      setSetupData(res as SetupData);
      setStep('setup');
      setAskPassword(false);
      setSetupPassword('');
    } catch (e) {
      showToast(e instanceof Error && e.message ? e.message : 'Error al configurar 2FA');
    } finally {
      setLoading(false);
    }
  }, [setupPassword]);

  const handleVerify = useCallback(async () => {
    if (!verifyCode.trim()) return;
    setLoading(true);
    try {
      await api.post('/auth/totp/verify', { code: verifyCode.trim() });
      showToast('2FA activado correctamente');
      setStep('backup');
      fetchStatus();
    } catch (e) {
      showToast(e instanceof Error && e.message ? e.message : 'Código inválido');
    } finally {
      setLoading(false);
    }
  }, [verifyCode, fetchStatus]);

  const handleDisable = useCallback(async () => {
    if (!disableCode.trim()) return;
    setLoading(true);
    try {
      await api.post('/auth/totp/disable', { code: disableCode.trim() });
      showToast('2FA desactivado');
      setSetupData(null);
      setStep('idle');
      setShowDisable(false);
      setDisableCode('');
      fetchStatus();
    } catch (e) {
      showToast(e instanceof Error && e.message ? e.message : 'Código inválido');
    } finally {
      setLoading(false);
    }
  }, [disableCode, fetchStatus]);

  // [H-03] Códigos de respaldo nuevos (los anteriores dejan de valer); exige un TOTP vigente.
  const handleRegenerar = useCallback(async () => {
    if (regenCode.length !== 6) return;
    setLoading(true);
    try {
      const res = (await api.post('/auth/totp/backup-codes', { code: regenCode })) as { backup_codes: string[] };
      setSetupData({ secret: '', qr_code: '', uri: '', backup_codes: res.backup_codes });
      setStep('backup');
      setShowRegen(false);
      setRegenCode('');
      fetchStatus();
    } catch (e) {
      showToast(e instanceof Error && e.message ? e.message : 'Código inválido');
    } finally {
      setLoading(false);
    }
  }, [regenCode, fetchStatus]);

  if (!status) {
    return <div className="p-4 text-[13px] text-[#605e5c]">Cargando estado 2FA...</div>;
  }

  return (
    <div className="p-4 max-w-[480px]">
      <h3 className="text-[15px] font-semibold text-[#323130] dark:text-[#e0e0e0] mb-1">
        Autenticación de dos factores (2FA)
      </h3>
      <p className="text-[12px] text-[#605e5c] dark:text-[#999] mb-4">
        Agrega una capa extra de seguridad a tu cuenta usando Google Authenticator, Authy u otra app TOTP.
      </p>

      {/* Status badge */}
      <div className="flex items-center gap-2 mb-4">
        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium ${
          status.enabled
            ? 'bg-[#dff6dd] text-[#107c10] dark:bg-[#1a3a1a] dark:text-[#6ccb5f]'
            : 'bg-[#fed9cc] text-[#d83b01] dark:bg-[#3a1a1a] dark:text-[#f1707b]'
        }`}>
          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
            {status.enabled
              ? <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              : <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            }
          </svg>
          {status.enabled ? 'Activado' : 'Desactivado'}
        </span>
        {status.enabled && status.backup_codes_remaining !== undefined && (
          <span className="text-[11px] text-[#605e5c]">
            {status.backup_codes_remaining} códigos de respaldo restantes
          </span>
        )}
      </div>

      {/* If not enabled: show setup button */}
      {!status.enabled && step === 'idle' && !askPassword && (
        <button
          onClick={() => setAskPassword(true)}
          disabled={loading}
          className="px-4 py-2 bg-[#0078d4] text-white text-[13px] rounded hover:bg-[#106ebe] disabled:opacity-50 transition-colors"
        >
          Activar 2FA
        </button>
      )}
      {!status.enabled && step === 'idle' && askPassword && (
        <div className="space-y-2">
          <p className="text-[12px] text-[#323130] dark:text-[#e0e0e0]">
            Por seguridad, confirma tu contraseña actual:
          </p>
          <div className="flex gap-2">
            <input
              type="password"
              value={setupPassword}
              onChange={e => setSetupPassword(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && startSetup()}
              placeholder="Contraseña actual"
              autoFocus
              className="w-[220px] px-3 py-1.5 text-[13px] border border-[#e1dfdd] dark:border-[#555] rounded bg-white dark:bg-[#1e1e1e] text-[#323130] dark:text-[#e0e0e0] outline-none focus:border-[#0078d4]"
            />
            <button
              onClick={startSetup}
              disabled={loading || !setupPassword.trim()}
              className="px-4 py-1.5 bg-[#0078d4] text-white text-[13px] rounded hover:bg-[#106ebe] disabled:opacity-50 transition-colors"
            >
              {loading ? 'Configurando...' : 'Continuar'}
            </button>
            <button
              onClick={() => { setAskPassword(false); setSetupPassword(''); }}
              className="px-3 py-1.5 text-[13px] text-[#605e5c] dark:text-[#999] hover:bg-[#e1dfdd] dark:hover:bg-[#383838] rounded"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      {/* Setup step: show QR and verify */}
      {step === 'setup' && setupData && (
        <div className="space-y-4">
          <div className="bg-[#faf9f8] dark:bg-[#2d2d2d] border border-[#edebe9] dark:border-[#444] rounded p-4">
            <p className="text-[12px] text-[#323130] dark:text-[#e0e0e0] mb-3">
              1. Escanea este código QR con tu app de autenticación:
            </p>
            <div className="flex justify-center mb-3">
              <img src={setupData.qr_code} alt="QR Code" className="w-[200px] h-[200px] rounded" />
            </div>
            <p className="text-[11px] text-[#605e5c] dark:text-[#999] mb-1">
              O ingresa esta clave manualmente:
            </p>
            <div className="bg-white dark:bg-[#1e1e1e] border border-[#e1dfdd] dark:border-[#555] rounded px-3 py-1.5 font-mono text-[13px] text-[#0078d4] select-all break-all">
              {setupData.secret}
            </div>
          </div>

          <div>
            <p className="text-[12px] text-[#323130] dark:text-[#e0e0e0] mb-2">
              2. Ingresa el código de 6 dígitos de tu app:
            </p>
            <div className="flex gap-2">
              <input
                type="text"
                value={verifyCode}
                onChange={e => setVerifyCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                onKeyDown={e => e.key === 'Enter' && handleVerify()}
                placeholder="000000"
                className="w-[140px] px-3 py-1.5 text-[14px] font-mono text-center border border-[#e1dfdd] dark:border-[#555] rounded bg-white dark:bg-[#1e1e1e] text-[#323130] dark:text-[#e0e0e0] outline-none focus:border-[#0078d4] tracking-[0.3em]"
                maxLength={6}
                autoFocus
              />
              <button
                onClick={handleVerify}
                disabled={loading || verifyCode.length !== 6}
                className="px-4 py-1.5 bg-[#0078d4] text-white text-[13px] rounded hover:bg-[#106ebe] disabled:opacity-50 transition-colors"
              >
                {loading ? 'Verificando...' : 'Verificar'}
              </button>
            </div>
          </div>

          <button
            onClick={() => { setStep('idle'); setSetupData(null); setVerifyCode(''); }}
            className="text-[12px] text-[#605e5c] hover:text-[#323130] underline"
          >
            Cancelar
          </button>
        </div>
      )}

      {/* Backup codes step */}
      {step === 'backup' && setupData && (
        <div className="space-y-4">
          <div className="bg-[#fff4ce] dark:bg-[#3a3520] border border-[#ffb900] dark:border-[#665d1e] rounded p-4">
            <p className="text-[13px] font-semibold text-[#323130] dark:text-[#e0e0e0] mb-2">
              Guarda estos códigos de respaldo
            </p>
            <p className="text-[12px] text-[#605e5c] dark:text-[#999] mb-3">
              Usa estos codigos si pierdes acceso a tu app de autenticacion. Cada codigo solo se puede usar una vez.
            </p>
            <div className="grid grid-cols-2 gap-1.5">
              {setupData.backup_codes.map((code, i) => (
                <div key={i} className="bg-white dark:bg-[#1e1e1e] border border-[#e1dfdd] dark:border-[#555] rounded px-3 py-1 font-mono text-[13px] text-center select-all">
                  {code}
                </div>
              ))}
            </div>
          </div>
          <button
            onClick={() => { setStep('idle'); setSetupData(null); }}
            className="px-4 py-2 bg-[#0078d4] text-white text-[13px] rounded hover:bg-[#106ebe] transition-colors"
          >
            Listo, los guarde
          </button>
        </div>
      )}

      {/* [H-03] Códigos de respaldo nuevos */}
      {status.enabled && step === 'idle' && (
        <div className="mt-4 pt-4 border-t border-[#edebe9] dark:border-[#444]">
          {!showRegen ? (
            <button
              onClick={() => setShowRegen(true)}
              className="text-[13px] text-[#0078d4] hover:underline"
            >
              Generar códigos de respaldo nuevos
            </button>
          ) : (
            <div className="space-y-2">
              <p className="text-[12px] text-[#323130] dark:text-[#e0e0e0]">
                Los códigos anteriores dejarán de valer. Ingresa el código de 6 dígitos de tu app:
              </p>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={regenCode}
                  onChange={e => setRegenCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  onKeyDown={e => e.key === 'Enter' && handleRegenerar()}
                  placeholder="000000"
                  maxLength={6}
                  autoFocus
                  className="w-[140px] px-3 py-1.5 text-[14px] font-mono text-center border border-[#e1dfdd] dark:border-[#555] rounded bg-white dark:bg-[#1e1e1e] text-[#323130] dark:text-[#e0e0e0] outline-none focus:border-[#0078d4] tracking-[0.3em]"
                />
                <button
                  onClick={handleRegenerar}
                  disabled={loading || regenCode.length !== 6}
                  className="px-4 py-1.5 bg-[#0078d4] text-white text-[13px] rounded hover:bg-[#106ebe] disabled:opacity-50 transition-colors"
                >
                  {loading ? 'Generando...' : 'Generar'}
                </button>
                <button
                  onClick={() => { setShowRegen(false); setRegenCode(''); }}
                  className="px-3 py-1.5 text-[13px] text-[#605e5c] hover:bg-[#f3f2f1] rounded transition-colors"
                >
                  Cancelar
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Disable section */}
      {status.enabled && step === 'idle' && (
        <div className="mt-4 pt-4 border-t border-[#edebe9] dark:border-[#444]">
          {!showDisable ? (
            <button
              onClick={() => setShowDisable(true)}
              className="text-[13px] text-[#d13438] hover:text-[#a4262c] transition-colors"
            >
              Desactivar 2FA
            </button>
          ) : (
            <div className="space-y-2">
              <p className="text-[12px] text-[#323130] dark:text-[#e0e0e0]">
                Ingresa tu código TOTP o un código de respaldo para desactivar:
              </p>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={disableCode}
                  onChange={e => setDisableCode(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleDisable()}
                  placeholder="Código TOTP o de respaldo"
                  className="w-[300px] px-3 py-1.5 text-[13px] font-mono border border-[#e1dfdd] dark:border-[#555] rounded bg-white dark:bg-[#1e1e1e] text-[#323130] dark:text-[#e0e0e0] outline-none focus:border-[#d13438]"
                  autoFocus
                />
                <button
                  onClick={handleDisable}
                  disabled={loading || !disableCode.trim()}
                  className="px-4 py-1.5 bg-[#d13438] text-white text-[13px] rounded hover:bg-[#a4262c] disabled:opacity-50 transition-colors"
                >
                  Desactivar
                </button>
                <button
                  onClick={() => { setShowDisable(false); setDisableCode(''); }}
                  className="px-3 py-1.5 text-[13px] text-[#605e5c] hover:bg-[#f3f2f1] rounded transition-colors"
                >
                  Cancelar
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
