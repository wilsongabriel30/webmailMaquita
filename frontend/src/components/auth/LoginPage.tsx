import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';
import { api } from '../../api/client';

export function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [needs2FA, setNeeds2FA] = useState(false);
  const [savedUsername, setSavedUsername] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const setUser = useAuthStore((s) => s.setUser);

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

      // Verify session is established before navigating
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
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-slate-100">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-2xl shadow-xl p-8">
          {/* Logo / Header */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-600 rounded-2xl mb-4">
              <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <h1 className="text-2xl font-bold text-slate-800">Maquita Mail</h1>
            <p className="text-slate-500 mt-1">
              {needs2FA ? 'Verificacion en dos pasos' : 'Inicia sesion en tu correo'}
            </p>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {!needs2FA ? (
              <>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Correo electronico
                  </label>
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="usuario@maquita.org"
                    className="w-full px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-colors"
                    required
                    autoFocus
                    autoComplete="username"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Contrasena
                  </label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022"
                    className="w-full px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-colors"
                    required
                    autoComplete="current-password"
                  />
                </div>
              </>
            ) : (
              <div>
                <p className="text-sm text-slate-600 mb-3">
                  Ingresa el codigo de tu app de autenticacion{savedUsername ? ` para ${savedUsername}` : ''}.
                </p>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Codigo de verificacion
                </label>
                <input
                  type="text"
                  value={totpCode}
                  onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 8))}
                  placeholder="000000"
                  className="w-full px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-colors text-center font-mono text-lg tracking-[0.3em]"
                  required
                  autoFocus
                  maxLength={8}
                  autoComplete="one-time-code"
                />
                <p className="text-xs text-slate-400 mt-1">
                  Tambien puedes usar un codigo de respaldo
                </p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 focus:ring-4 focus:ring-blue-200 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Verificando...' : needs2FA ? 'Verificar' : 'Iniciar sesion'}
            </button>

            {needs2FA && (
              <button
                type="button"
                onClick={() => { setNeeds2FA(false); setTotpCode(''); setError(''); }}
                className="w-full py-2 text-sm text-slate-500 hover:text-slate-700 transition-colors"
              >
                Volver al inicio de sesion
              </button>
            )}
          </form>
        </div>

        <p className="text-center text-slate-400 text-sm mt-6">
          Maquita Comercializando como Hermanos &copy; {new Date().getFullYear()}
        </p>
      </div>
    </div>
  );
}
