import { useState, useEffect } from "react";
import { api } from "../api/client";

interface LastExternal { user: string; ip: string; time: string; }
interface Health {
  window_hours: number;
  external_count: number;
  internal_count: number;
  by_protocol: { imap: number; pop3: number };
  last_external: LastExternal | null;
  ok: boolean;
  note: string;
}

export function LoginHealth() {
  const [h, setH] = useState<Health | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true); setErr("");
    try { setH(await api.get<Health>("/admin/login-health?hours=24")); }
    catch (e: any) { setErr(e.message); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  if (loading) return <div className="p-6">Cargando…</div>;
  if (err) return <div className="p-6 text-red-700">{err}</div>;
  if (!h) return null;

  return (
    <div className="p-6 max-w-3xl space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Accesos externos (IMAP/POP)</h1>
          <p className="text-gray-500 text-sm mt-1">
            Conexiones de clientes reales (celular, Outlook, Thunderbird) en las últimas {h.window_hours} h.
            El webmail entra por localhost y no cuenta. 0 accesos externos suele significar que nadie
            puede configurar su correo (como el incidente de migración).
          </p>
        </div>
        <button onClick={load} className="text-sm text-blue-600 hover:underline">Actualizar</button>
      </div>

      {h.external_count === 0 ? (
        <div className="bg-red-50 border border-red-200 text-red-800 rounded p-4">
          ⚠️ <strong>0 accesos externos en {h.window_hours} h.</strong> Revisar autenticación Dovecot,
          claves de usuarios y la tarjeta “Configurar mi correo”. Hay {h.internal_count} accesos internos (webmail).
        </div>
      ) : (
        <div className="bg-green-50 border border-green-200 text-green-800 rounded p-4">
          ✓ {h.external_count} accesos externos en {h.window_hours} h — los clientes están conectando.
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Stat label="Externos" value={h.external_count} />
        <Stat label="IMAP" value={h.by_protocol.imap} />
        <Stat label="POP3" value={h.by_protocol.pop3} />
        <Stat label="Internos (webmail)" value={h.internal_count} />
      </div>

      <div className="bg-white border rounded-lg p-4 text-sm">
        <div className="font-medium mb-1">Último acceso externo</div>
        {h.last_external ? (
          <div className="text-[#323130]">
            <span className="font-mono">{h.last_external.user}</span> desde{" "}
            <span className="font-mono">{h.last_external.ip}</span>
            <div className="text-gray-400 text-xs mt-0.5">{h.last_external.time}</div>
          </div>
        ) : (
          <div className="text-red-700">Sin accesos externos en la ventana.</div>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-white border rounded-lg p-3 text-center">
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  );
}
