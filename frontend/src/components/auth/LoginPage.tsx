import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';
import { api } from '../../api/client';

interface Branding {
  org_name?: string;
  org_slogan?: string;
  primary_color?: string;
  logo_url?: string;
  favicon_url?: string;
  footer_text?: string;
}

export function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [needs2FA, setNeeds2FA] = useState(false);
  const [savedUsername, setSavedUsername] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [brand, setBrand] = useState<Branding>({});
  const navigate = useNavigate();
  const setUser = useAuthStore((s) => s.setUser);

  const color = brand.primary_color || '#0078d4';
  const orgName = brand.org_name || 'Maquita Mail';
  const slogan = brand.org_slogan || '';
  const footerText = brand.footer_text || '';

  useEffect(() => {
    fetch('/api/branding')
      .then(r => r.ok ? r.json() : {})
      .then((b: Branding) => setBrand(b))
      .catch(() => {});
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const payload: any = { username, password };
      if (needs2FA) {
        payload.totp_code = totpCode;
      }

      const res = await api.post<{ success?: boolean; error?: string; username?: string; is_admin?: boolean; requires_2fa?: boolean }>('/auth/login', payload);

      if (res.success === false) {
        setError(res.error || 'Credenciales incorrectas');
        setLoading(false);
        return;
      }

      if (res.requires_2fa) {
        setNeeds2FA(true);
        setSavedUsername(res.username || username);
        setLoading(false);
        return;
      }

      const meRes = await fetch('/api/auth/me', { credentials: 'include' });
      const meData = await meRes.json();
      if (meData.user) {
        setUser(meData.user);
        navigate('/');
      } else {
        setError('Sesión no establecida. Intenta de nuevo.');
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error al iniciar sesion');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col" style={{ backgroundColor: '#faf9f8' }}>
      {/* Top bar */}
      <div className="h-12 flex items-center px-6" style={{ backgroundColor: color }}>
        <svg className="w-5 h-5 text-white mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
        <span className="text-white font-semibold text-sm">{orgName}</span>
      </div>

      <div className="flex-1 flex items-center justify-center p-4">
        <div className="w-full max-w-sm">
          <div className="bg-white rounded shadow-lg p-8" style={{ borderColor: '#edebe9', borderWidth: '1px' }}>
            {/* Header with logo or icon */}
            <div className="text-center mb-6">
              {brand.logo_url ? (
                <img src={brand.logo_url} alt={orgName}
                  className="h-16 mx-auto mb-3 object-contain" />
              ) : (
                <div className="inline-flex items-center justify-center w-14 h-14 rounded-full mb-3" style={{ backgroundColor: color }}>
                  {needs2FA ? (
                    <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                    </svg>
                  ) : (
                    <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                  )}
                </div>
              )}
              <h1 className="text-xl font-semibold" style={{ color: '#323130' }}>
                {needs2FA ? 'Verificación en dos pasos' : 'Iniciar sesión'}
              </h1>
              <p className="text-sm mt-1" style={{ color: '#605e5c' }}>
                {needs2FA
                  ? `Ingresa el código para ${savedUsername || 'tu cuenta'}`
                  : `Correo electrónico${brand.org_name ? ' de ' + brand.org_name : ''}`}
              </p>
            </div>

            {error && (
              <div className="mb-4 p-3 rounded text-sm flex items-center gap-2" style={{ backgroundColor: '#fde7e9', borderColor: 'rgba(209,52,56,0.3)', borderWidth: '1px', color: '#d13438' }}>
                <svg className="w-4 h-4 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit}>
              {!needs2FA ? (
                <>
                  <div className="mb-4">
                    <label className="block text-sm font-medium mb-1.5" style={{ color: '#323130' }}>
                      Correo electrónico
                    </label>
                    <input
                      type="text"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      placeholder="usuario@maquita.org"
                      className="w-full px-3 py-2 rounded text-sm outline-none transition-colors"
                      style={{ borderColor: '#d2d0ce', borderWidth: '1px', color: '#323130' }}
                      onFocus={(e) => { e.target.style.borderColor = color; e.target.style.boxShadow = `0 0 0 1px ${color}`; }}
                      onBlur={(e) => { e.target.style.borderColor = '#d2d0ce'; e.target.style.boxShadow = 'none'; }}
                      required
                      autoFocus
                      autoComplete="username"
                    />
                  </div>
                  <div className="mb-6">
                    <label className="block text-sm font-medium mb-1.5" style={{ color: '#323130' }}>
                      Contraseña
                    </label>
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Ingrese su contraseña"
                      className="w-full px-3 py-2 rounded text-sm outline-none transition-colors"
                      style={{ borderColor: '#d2d0ce', borderWidth: '1px', color: '#323130' }}
                      onFocus={(e) => { e.target.style.borderColor = color; e.target.style.boxShadow = `0 0 0 1px ${color}`; }}
                      onBlur={(e) => { e.target.style.borderColor = '#d2d0ce'; e.target.style.boxShadow = 'none'; }}
                      required
                      autoComplete="current-password"
                    />
                  </div>
                </>
              ) : (
                <div className="mb-6">
                  <label className="block text-sm font-medium mb-1.5" style={{ color: '#323130' }}>
                    Código de verificación
                  </label>
                  <input
                    type="text"
                    value={totpCode}
                    onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 8))}
                    placeholder="000000"
                    className="w-full px-3 py-2 rounded text-sm text-center font-mono text-lg tracking-[0.3em] outline-none transition-colors"
                    style={{ borderColor: '#d2d0ce', borderWidth: '1px', color: '#323130' }}
                    onFocus={(e) => { e.target.style.borderColor = color; e.target.style.boxShadow = `0 0 0 1px ${color}`; }}
                    onBlur={(e) => { e.target.style.borderColor = '#d2d0ce'; e.target.style.boxShadow = 'none'; }}
                    required
                    autoFocus
                    maxLength={8}
                    autoComplete="one-time-code"
                  />
                  <p className="text-xs mt-1" style={{ color: '#a19f9d' }}>
                    También puedes usar un código de respaldo
                  </p>
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 text-white font-medium rounded text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                style={{ backgroundColor: color }}
                onMouseEnter={(e) => { if (!loading) (e.currentTarget).style.opacity = '0.85'; }}
                onMouseLeave={(e) => { (e.currentTarget).style.opacity = '1'; }}
              >
                {loading ? 'Verificando...' : needs2FA ? 'Verificar' : 'Iniciar sesión'}
              </button>

              {needs2FA && (
                <button
                  type="button"
                  onClick={() => { setNeeds2FA(false); setTotpCode(''); setError(''); }}
                  className="w-full py-2 text-sm mt-2 transition-colors"
                  style={{ color: '#605e5c' }}
                  onMouseEnter={(e) => { (e.currentTarget).style.color = '#323130'; }}
                  onMouseLeave={(e) => { (e.currentTarget).style.color = '#605e5c'; }}
                >
                  ← Volver al inicio de sesión
                </button>
              )}
            </form>
          </div>
          <p className="text-center text-xs mt-4" style={{ color: '#a19f9d' }}>
            {footerText || (
              <>{orgName}{slogan ? ` — ${slogan}` : ''} &middot; {new Date().getFullYear()}</>
            )}
          </p>
        </div>
      </div>
    </div>
  );
}
