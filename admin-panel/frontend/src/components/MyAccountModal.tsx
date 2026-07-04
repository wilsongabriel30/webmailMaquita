import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../api/auth";

export function MyAccountModal({ onClose }: { onClose: () => void }) {
  const { user } = useAuth();
  const [tab, setTab] = useState<"password" | "totp">("password");

  // Cambio de contraseña propia
  const [pwForm, setPwForm] = useState({ current: "", next: "", confirm: "" });
  const [pwMsg, setPwMsg] = useState<{ ok: boolean; text: string } | null>(null);

  // 2FA
  const [totpEnabled, setTotpEnabled] = useState<boolean | null>(null);
  const [totpPw, setTotpPw] = useState("");
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string; qr_svg: string } | null>(null);
  const [totpCode, setTotpCode] = useState("");
  const [totpMsg, setTotpMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    api.get<{ enabled: boolean }>("/auth/totp/status").then((r) => setTotpEnabled(r.enabled)).catch(() => setTotpEnabled(false));
  }, []);

  const changePassword = async () => {
    setPwMsg(null);
    if (pwForm.next.length < 8) { setPwMsg({ ok: false, text: "La nueva contraseña debe tener al menos 8 caracteres" }); return; }
    if (pwForm.next !== pwForm.confirm) { setPwMsg({ ok: false, text: "Las contraseñas no coinciden" }); return; }
    try {
      await api.post("/auth/change-password", { current_password: pwForm.current, new_password: pwForm.next });
      setPwForm({ current: "", next: "", confirm: "" });
      setPwMsg({ ok: true, text: "Contraseña actualizada correctamente" });
    } catch (e) {
      setPwMsg({ ok: false, text: e instanceof Error ? e.message : "Error al cambiar la contraseña" });
    }
  };

  const startTotpSetup = async () => {
    setTotpMsg(null);
    try {
      const res = await api.post<{ secret: string; otpauth_uri: string; qr_svg: string }>("/auth/totp/setup", { password: totpPw });
      setSetup(res); setTotpPw(""); setTotpCode("");
    } catch (e) {
      setTotpMsg({ ok: false, text: e instanceof Error ? e.message : "Error al iniciar la configuración" });
    }
  };

  const verifyTotp = async () => {
    setTotpMsg(null);
    try {
      await api.post("/auth/totp/verify", { code: totpCode });
      setSetup(null); setTotpCode(""); setTotpEnabled(true);
      setTotpMsg({ ok: true, text: "Verificación en dos pasos ACTIVADA. Se pedirá el código en cada inicio de sesión." });
    } catch (e) {
      setTotpMsg({ ok: false, text: e instanceof Error ? e.message : "Código inválido" });
    }
  };

  const disableTotp = async () => {
    if (!confirm("Desactivar la verificación en dos pasos? Su cuenta quedará protegida solo por contraseña. Se registra en auditoria.")) return;
    setTotpMsg(null);
    try {
      await api.post("/auth/totp/disable", { password: totpPw });
      setTotpPw(""); setTotpEnabled(false); setSetup(null);
      setTotpMsg({ ok: true, text: "Verificación en dos pasos desactivada" });
    } catch (e) {
      setTotpMsg({ ok: false, text: e instanceof Error ? e.message : "Error al desactivar" });
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded border border-ms-gray-30 w-[28rem] max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="px-5 py-4 border-b border-ms-gray-30 flex items-center justify-between">
          <h2 className="text-base font-semibold text-ms-gray-130">Mi cuenta — {user?.username}</h2>
          <button onClick={onClose} title="Cierra la ventana de Mi cuenta sin guardar cambios pendientes." className="text-ms-gray-60 hover:text-ms-gray-130 text-lg leading-none">&times;</button>
        </div>

        <div className="flex border-b border-ms-gray-30">
          <button onClick={() => setTab("password")} title="Muestra la pestaña para cambiar la contraseña de su propia cuenta del panel." className={`px-4 py-2 text-sm ${tab === "password" ? "border-b-2 border-ms-blue text-ms-blue font-medium" : "text-ms-gray-90"}`}>Contraseña</button>
          <button onClick={() => setTab("totp")} title="Muestra la pestaña para activar o desactivar la verificación en dos pasos (2FA) de su cuenta." className={`px-4 py-2 text-sm ${tab === "totp" ? "border-b-2 border-ms-blue text-ms-blue font-medium" : "text-ms-gray-90"}`}>Verificación en dos pasos</button>
        </div>

        {tab === "password" && (
          <div className="p-5 space-y-3">
            <input type="password" placeholder="Contraseña actual" autoComplete="current-password" value={pwForm.current} onChange={(e) => setPwForm({ ...pwForm, current: e.target.value })} title="Su contraseña actual. Se pide para verificar su identidad antes de permitir el cambio." className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
            <input type="password" placeholder="Nueva contraseña (min 8)" autoComplete="new-password" value={pwForm.next} onChange={(e) => setPwForm({ ...pwForm, next: e.target.value })} title="Nueva contraseña de su cuenta. Mínimo 8 caracteres. Se aplicará al pulsar Cambiar contraseña." className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
            <input type="password" placeholder="Confirmar nueva contraseña" autoComplete="new-password" value={pwForm.confirm} onChange={(e) => setPwForm({ ...pwForm, confirm: e.target.value })} onKeyDown={(e) => { if (e.key === "Enter") changePassword(); }} title="Repita la nueva contraseña. Debe coincidir exactamente. Enter aplica el cambio." className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
            {pwMsg && <div className={`text-xs ${pwMsg.ok ? "text-ms-green" : "text-ms-red"}`}>{pwMsg.text}</div>}
            <div className="flex justify-end">
              <button onClick={changePassword} title="Cambia la contraseña de su propia cuenta del panel." className="px-4 py-2 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark">Cambiar contraseña</button>
            </div>
          </div>
        )}

        {tab === "totp" && (
          <div className="p-5 space-y-3">
            {totpEnabled === null && <div className="text-sm text-ms-gray-60">Cargando…</div>}

            {totpEnabled === false && !setup && (
              <>
                <p className="text-sm text-ms-gray-90">La verificación en dos pasos está <strong className="text-ms-red">desactivada</strong>. Al activarla, se pedirá un código de su aplicación de autenticación (Google Authenticator, Microsoft Authenticator, Aegis…) en cada inicio de sesión.</p>
                <input type="password" placeholder="Confirme su contraseña para comenzar" value={totpPw} onChange={(e) => setTotpPw(e.target.value)} title="Escriba su contraseña actual para confirmar su identidad antes de iniciar la activación del 2FA." className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
                <div className="flex justify-end">
                  <button onClick={startTotpSetup} disabled={!totpPw} title="Genera el código QR para vincular su aplicación de autenticación." className="px-4 py-2 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark disabled:opacity-50">Activar 2FA</button>
                </div>
              </>
            )}

            {setup && (
              <>
                <p className="text-sm text-ms-gray-90">1. Escanee este código QR con su aplicación de autenticación:</p>
                <div className="flex justify-center bg-white p-2"><img src={setup.qr_svg} alt="Código QR 2FA" className="w-44 h-44" /></div>
                <p className="text-xs text-ms-gray-60 break-all">Si no puede escanear, ingrese esta clave manualmente: <strong>{setup.secret}</strong></p>
                <p className="text-sm text-ms-gray-90">2. Ingrese el código de 6 dígitos que muestra la aplicación:</p>
                <input type="text" inputMode="numeric" maxLength={6} placeholder="000000" value={totpCode} onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, ""))} title="Código de 6 dígitos que muestra su aplicación de autenticación tras escanear el QR. Solo acepta números. Sirve para comprobar que la vinculación funcionó." className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm tracking-widest text-center focus:outline-none focus:border-ms-blue" />
                <div className="flex justify-end gap-2">
                  <button onClick={() => { setSetup(null); setTotpCode(""); }} title="Cancela la activación del 2FA. No se guarda nada y su cuenta sigue solo con contraseña." className="px-4 py-2 border border-ms-gray-40 rounded text-sm text-ms-gray-90">Cancelar</button>
                  <button onClick={verifyTotp} disabled={totpCode.length !== 6} title="Comprueba el código y activa la verificación en dos pasos. Desde ese momento se pedirá el código en cada inicio de sesión." className="px-4 py-2 bg-ms-blue text-white rounded text-sm hover:bg-ms-blue-dark disabled:opacity-50">Verificar y activar</button>
                </div>
              </>
            )}

            {totpEnabled === true && !setup && (
              <>
                <p className="text-sm text-ms-gray-90">La verificación en dos pasos está <strong className="text-ms-green">activada</strong> para su cuenta.</p>
                <input type="password" placeholder="Confirme su contraseña para desactivar" value={totpPw} onChange={(e) => setTotpPw(e.target.value)} title="Escriba su contraseña actual para confirmar su identidad antes de poder desactivar el 2FA." className="w-full px-3 py-2 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue" />
                <div className="flex justify-end">
                  <button onClick={disableTotp} disabled={!totpPw} title="PRECAUCION: Desactiva la verificación en dos pasos. Se registra en auditoria." className="px-4 py-2 bg-ms-red text-white rounded text-sm disabled:opacity-50">Desactivar 2FA</button>
                </div>
              </>
            )}

            {totpMsg && <div className={`text-xs ${totpMsg.ok ? "text-ms-green" : "text-ms-red"}`}>{totpMsg.text}</div>}
          </div>
        )}
      </div>
    </div>
  );
}
