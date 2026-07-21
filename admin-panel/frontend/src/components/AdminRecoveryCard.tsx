import { useState, useEffect } from "react";
import { api } from "../api/client";

interface RecStatus {
  configured: boolean;
  verified?: boolean;
  recovery_email?: string;
  uses_this_year?: number;
  max_per_year?: number;
}

export function AdminRecoveryCard() {
  const [st, setSt] = useState<RecStatus | null>(null);
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [pending, setPending] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const load = () => api.get<RecStatus>("/admin-recovery/status").then(setSt).catch(() => {});
  useEffect(() => { load(); }, []);

  const register = async () => {
    setBusy(true); setMsg(null);
    try {
      const r = await api.post<{ sent_to?: string }>("/admin-recovery/register", { recovery_email: email });
      setMsg({ ok: true, text: `Enviamos un codigo a ${r?.sent_to || "tu correo"}. Ingresalo abajo para verificar.` });
      setPending(true);
    } catch (e: any) { setMsg({ ok: false, text: e.message || "Error" }); }
    finally { setBusy(false); }
  };
  const verify = async () => {
    setBusy(true); setMsg(null);
    try {
      await api.post("/admin-recovery/verify", { otp: otp.trim() });
      setMsg({ ok: true, text: "Correo de recuperacion verificado y activo." });
      setPending(false); setOtp(""); setEmail(""); await load();
    } catch (e: any) { setMsg({ ok: false, text: e.message || "Error" }); }
    finally { setBusy(false); }
  };

  const inputCls = "px-3 py-2 border border-ms-gray-30 rounded text-sm";

  return (
    <div className="bg-white border border-ms-gray-30 rounded-lg p-4 mb-4 space-y-3">
      <div>
        <h2 className="text-sm font-semibold text-ms-gray-160">Correo de recuperacion del panel</h2>
        <p className="text-xs text-ms-gray-110">Correo alternativo (Gmail, Hotmail, etc.) para recuperar el acceso a ESTE panel si pierdes tu contrasena o te bloquean. Se permite recuperar hasta 5 veces al ano; superado, se desbloquea por consola. Solo aplica al panel administrativo.</p>
      </div>

      {st?.configured && st?.verified ? (
        <div className="text-sm text-ms-gray-160">
          <span className="inline-block px-2 py-0.5 rounded text-xs mr-2" style={{ background: "#dff6dd", color: "#107c10" }}>Activo</span>
          Correo: <b>{st.recovery_email}</b> · Recuperaciones usadas este ano: {st.uses_this_year}/{st.max_per_year}
        </div>
      ) : (
        <p className="text-xs text-amber-700">Aun no tienes un correo de recuperacion verificado. Registralo abajo.</p>
      )}

      {msg && (
        <div className={`p-2 rounded text-xs ${msg.ok ? "bg-green-50 border border-green-300 text-green-700" : "bg-red-50 border border-red-300 text-red-700"}`}>{msg.text}</div>
      )}

      {!pending ? (
        <div className="flex flex-wrap gap-2 items-end">
          <div className="flex-1" style={{ minWidth: "16rem" }}>
            <label className="block text-xs text-ms-gray-110">{st?.configured ? "Cambiar correo de recuperacion" : "Correo alternativo"}</label>
            <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="tucorreo@gmail.com" type="email"
              title="Correo externo donde recibiras el codigo de verificacion y, en el futuro, el token de recuperacion." className={inputCls + " w-full"} />
          </div>
          <button onClick={register} disabled={busy || !email.includes("@")} className="text-white text-sm px-4 py-2 rounded" style={{ backgroundColor: "#0078d4" }}>
            {busy ? "Enviando..." : "Enviar codigo"}
          </button>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2 items-end">
          <div>
            <label className="block text-xs text-ms-gray-110">Codigo de 6 digitos</label>
            <input value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))} maxLength={6} placeholder="000000"
              title="Codigo que llego a tu correo alternativo (vence en 15 minutos)." className={inputCls + " tracking-widest text-center w-32"} />
          </div>
          <button onClick={verify} disabled={busy || otp.length !== 6} className="text-white text-sm px-4 py-2 rounded" style={{ backgroundColor: "#107c10" }}>
            {busy ? "Verificando..." : "Verificar"}
          </button>
          <button onClick={() => { setPending(false); setOtp(""); }} className="text-xs text-ms-gray-110 hover:underline">Cancelar</button>
        </div>
      )}
    </div>
  );
}
