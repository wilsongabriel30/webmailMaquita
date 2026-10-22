import React, { useEffect, useRef, useState } from "react";

// /entrar?vale=… — canjea un vale de entrada de un solo uso por la sesión del panel.
// Llegan aquí la orden de consola «maquita-panel vale-entrada» y la vuelta del proveedor de
// identidad (OpenID Connect). Si la cuenta tiene segundo factor y el vale lo exige, se pide aquí.
const RE_VALE = /^[A-Za-z0-9_-]{32,128}$/;

async function canjear(vale: string, totpCode?: string) {
  const r = await fetch("/api/auth/vale", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ vale, totp_code: totpCode || undefined }),
  });
  const datos = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof datos.detail === "string" ? datos.detail : "No se pudo entrar");
  return datos as { token?: string; user?: unknown; requires_totp?: boolean };
}

export function EntradaVale() {
  const vale = useRef<string>(new URLSearchParams(window.location.search).get("vale") || "");
  const [error, setError] = useState("");
  const [pideCodigo, setPideCodigo] = useState(false);
  const [codigo, setCodigo] = useState("");
  const [enviando, setEnviando] = useState(false);

  const entrar = async (totpCode?: string) => {
    setEnviando(true); setError("");
    try {
      const r = await canjear(vale.current, totpCode);
      if (r.requires_totp) { setPideCodigo(true); setEnviando(false); return; }
      localStorage.setItem("admin_token", r.token!);
      localStorage.setItem("admin_user", JSON.stringify(r.user));
      window.location.replace("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo entrar");
      setCodigo("");
      setEnviando(false);
    }
  };

  useEffect(() => {
    // El vale no se queda en la barra de direcciones ni en el historial.
    window.history.replaceState(null, "", "/entrar");
    if (!RE_VALE.test(vale.current)) { setError("El enlace de entrada no es válido."); return; }
    entrar();
  }, []);

  const enviarCodigo = (e: React.FormEvent) => { e.preventDefault(); entrar(codigo); };

  return (
    <div className="min-h-screen bg-ms-gray-10 flex items-center justify-center p-4">
      <div className="w-full max-w-sm bg-white rounded shadow-lg border border-ms-gray-30 p-8 space-y-4">
        <h1 className="text-xl font-semibold text-ms-gray-130 text-center">Entrar al panel</h1>
        {error && <div className="p-3 bg-red-50 border border-ms-red/30 rounded text-ms-red text-sm" role="alert">{error}</div>}
        {!error && !pideCodigo && <p className="text-sm text-ms-gray-90 text-center">Comprobando el enlace de entrada…</p>}
        {pideCodigo && (
          <form onSubmit={enviarCodigo} className="space-y-3">
            <label htmlFor="codigo-vale" className="block text-sm font-medium text-ms-gray-130">Código de verificación (2FA)</label>
            <input id="codigo-vale" type="text" inputMode="numeric" autoComplete="one-time-code" maxLength={6} autoFocus
              value={codigo} onChange={(e) => setCodigo(e.target.value.replace(/\D/g, ""))} placeholder="000000"
              title="Código de 6 dígitos de su aplicación de autenticación. Su cuenta tiene segundo factor: se pide también al entrar con el proveedor de identidad."
              className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm tracking-widest text-center focus:outline-none focus:border-ms-blue" />
            <button type="submit" disabled={enviando || codigo.length !== 6}
              className="w-full py-2.5 bg-ms-blue hover:bg-ms-blue-dark disabled:opacity-50 text-white font-medium rounded text-sm">
              {enviando ? "Verificando…" : "Verificar código"}
            </button>
          </form>
        )}
        {error && <a href="/login" className="block text-center text-xs text-ms-blue hover:underline">Volver a la pantalla de entrada</a>}
      </div>
    </div>
  );
}
