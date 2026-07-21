import React from "react";
import { useState } from "react";
import { useAuth } from "../api/auth";
import { api } from "../api/client";

export function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [needTotp, setNeedTotp] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [recover, setRecover] = useState(false);
  const [recStep, setRecStep] = useState(1);
  const [recUser, setRecUser] = useState("");
  const [recToken, setRecToken] = useState("");
  const [recPass, setRecPass] = useState("");
  const [recMsg, setRecMsg] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await login(username, password, needTotp ? totpCode : undefined);
      if (res?.requires_totp) {
        setNeedTotp(true);
      }
    } catch (err: any) {
      setError(err.message || "Error de autenticacion");
    } finally {
      setLoading(false);
    }
  };

  const doRequest = async (e: React.FormEvent) => {
    e.preventDefault(); setError(""); setRecMsg(""); setLoading(true);
    try {
      const r = await api.post<{ message?: string }>("/admin-recovery/request", { username: recUser });
      setRecMsg(r?.message || "Si la cuenta tiene recuperacion configurada, se envio un enlace al correo alternativo.");
      setRecStep(2);
    } catch (err: any) { setError(err.message || "Error"); }
    finally { setLoading(false); }
  };
  const doReset = async (e: React.FormEvent) => {
    e.preventDefault(); setError(""); setRecMsg(""); setLoading(true);
    try {
      const r = await api.post<{ message?: string }>("/admin-recovery/reset", { username: recUser, token: recToken.trim(), new_password: recPass });
      setRecMsg(r?.message || "Contrasena actualizada. Ya puedes iniciar sesion.");
      setTimeout(() => { setRecover(false); setRecStep(1); setRecToken(""); setRecPass(""); setRecMsg(""); }, 2500);
    } catch (err: any) { setError(err.message || "Error"); }
    finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-ms-gray-10 flex flex-col">
      {/* Top bar */}
      <div className="h-12 bg-ms-blue flex items-center px-6">
        <svg className="w-5 h-5 text-white mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
        <span className="text-white font-semibold text-sm">Maquita Mail Admin</span>
      </div>

      <div className="flex-1 flex items-center justify-center p-4">
        <div className="w-full max-w-sm">
          <div className="bg-white rounded shadow-lg border border-ms-gray-30 p-8">
            <div className="text-center mb-6">
              <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-ms-blue mb-3">
                <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              </div>
              <h1 className="text-xl font-semibold text-ms-gray-130">Iniciar sesión</h1>
              <p className="text-sm text-ms-gray-90 mt-1">Centro de Administración de Correo</p>
            </div>

            {error && (
              <div className="mb-4 p-3 bg-red-50 border border-ms-red/30 rounded text-ms-red text-sm flex items-center gap-2">
                <svg className="w-4 h-4 shrink-0" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" /></svg>
                {error}
              </div>
            )}

            {recover ? (
              <div>
                <h2 className="text-sm font-semibold text-ms-gray-130 mb-1">Recuperar acceso</h2>
                <p className="text-xs text-ms-gray-60 mb-3">Se enviara un token al correo alternativo registrado de esta cuenta. Solo para el panel administrativo.</p>
                {recMsg && <div className="mb-3 p-2 bg-green-50 border border-green-300 rounded text-green-700 text-xs">{recMsg}</div>}
                {recStep === 1 ? (
                  <form onSubmit={doRequest}>
                    <label className="block text-sm font-medium text-ms-gray-130 mb-1.5">Usuario</label>
                    <input value={recUser} onChange={(e) => setRecUser(e.target.value)} placeholder="admin" required
                      title="Usuario del panel cuyo acceso quieres recuperar. Se enviara un token al correo alternativo que registro."
                      className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm mb-4" autoFocus />
                    <button type="submit" disabled={loading} className="w-full py-2.5 bg-ms-blue hover:bg-ms-blue-dark disabled:opacity-50 text-white font-medium rounded text-sm">
                      {loading ? "Enviando..." : "Enviar token al correo alternativo"}
                    </button>
                  </form>
                ) : (
                  <form onSubmit={doReset}>
                    <label className="block text-sm font-medium text-ms-gray-130 mb-1.5">Token recibido</label>
                    <input value={recToken} onChange={(e) => setRecToken(e.target.value)} placeholder="Pega el token del correo" required
                      title="Token que llego a tu correo alternativo (valido 30 minutos, un solo uso)."
                      className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm mb-3" autoFocus />
                    <label className="block text-sm font-medium text-ms-gray-130 mb-1.5">Nueva contrasena</label>
                    <input type="password" value={recPass} onChange={(e) => setRecPass(e.target.value)} placeholder="Minimo 10 caracteres" minLength={10} required
                      title="Nueva contrasena del panel (minimo 10 caracteres)."
                      className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm mb-4" />
                    <button type="submit" disabled={loading || recPass.length < 10} className="w-full py-2.5 bg-ms-blue hover:bg-ms-blue-dark disabled:opacity-50 text-white font-medium rounded text-sm">
                      {loading ? "Guardando..." : "Definir nueva contrasena"}
                    </button>
                  </form>
                )}
                <button type="button" onClick={() => { setRecover(false); setRecStep(1); setError(""); setRecMsg(""); }} className="w-full mt-3 text-xs text-ms-blue hover:underline">Volver a iniciar sesion</button>
              </div>
            ) : (
            <form onSubmit={handleSubmit}>
              <div className="mb-4">
                <label className="block text-sm font-medium text-ms-gray-130 mb-1.5">Usuario</label>
                <input
                  type="text" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)}
                  title="Nombre de usuario de su cuenta de administrador del panel (no es su correo)."
                  className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-130 focus:outline-none focus:border-ms-blue focus:ring-1 focus:ring-ms-blue"
                  placeholder="admin" autoFocus
                />
              </div>
              <div className="mb-6">
                <label className="block text-sm font-medium text-ms-gray-130 mb-1.5">Contraseña</label>
                <input
                  type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)}
                  title="Contraseña de su cuenta de administrador. Los intentos fallidos quedan registrados en auditoría."
                  className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-130 focus:outline-none focus:border-ms-blue focus:ring-1 focus:ring-ms-blue"
                  placeholder="Ingrese su contraseña"
                />
              </div>
              {needTotp && (
                <div className="mb-6">
                  <label className="block text-sm font-medium text-ms-gray-130 mb-1.5">Código de verificación (2FA)</label>
                  <input
                    type="text" inputMode="numeric" autoComplete="one-time-code" maxLength={6}
                    title="Código temporal de 6 dígitos generado por su aplicación de autenticación (Google Authenticator, Microsoft Authenticator, Aegis...). Solo acepta números."
                    value={totpCode} onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, ""))}
                    className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-130 tracking-widest text-center focus:outline-none focus:border-ms-blue focus:ring-1 focus:ring-ms-blue"
                    placeholder="000000" autoFocus
                  />
                  <p className="text-xs text-ms-gray-60 mt-1">Ingrese el código de 6 dígitos de su aplicación de autenticación.</p>
                </div>
              )}
              <button
                type="submit" disabled={loading || (needTotp && totpCode.length !== 6)}
                title="Envía las credenciales para entrar al panel. Si su cuenta tiene 2FA activado, se pedirá además el código de 6 dígitos. El inicio de sesión queda registrado en auditoría."
                className="w-full py-2.5 bg-ms-blue hover:bg-ms-blue-dark disabled:opacity-50 text-white font-medium rounded text-sm transition-colors"
              >
                {loading ? "Ingresando..." : needTotp ? "Verificar código" : "Iniciar sesión"}
              </button>
            </form>
            )}
            {!recover && !needTotp && (
              <button type="button" onClick={() => { setRecover(true); setError(""); }} className="w-full mt-3 text-xs text-ms-blue hover:underline"
                title="Si perdiste el acceso al panel, recupera con el correo alternativo que registraste.">
                Perdi el acceso — Recuperar con correo alternativo
              </button>
            )}
          </div>
          <p className="text-center text-ms-gray-60 text-xs mt-4">Maquita Cushunchic MCCH &middot; v2.0</p>
        </div>
      </div>
    </div>
  );
}
