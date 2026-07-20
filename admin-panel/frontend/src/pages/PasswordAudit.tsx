import { useState, useEffect } from "react";
import { api } from "../api/client";

interface Acct { username: string; active: boolean; }
interface Audit {
  total: number;
  ok: number;
  flagged_count: number;
  empty: Acct[];
  plaintext: Acct[];
  invalid_format: Acct[];
}

export function PasswordAudit() {
  const [a, setA] = useState<Audit | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [resets, setResets] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState("");

  async function load() {
    setLoading(true); setErr("");
    try { setA(await api.get<Audit>("/admin/password-audit")); }
    catch (e: any) { setErr(e.message); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  async function reset(username: string) {
    if (!confirm(`Generar clave temporal para ${username}? Su sesión actual se cerrará y deberá usar la nueva clave.`)) return;
    setBusy(username);
    try {
      const r = await api.post<{ username: string; temp_password: string }>("/admin/password-audit/reset", { username });
      setResets((m) => ({ ...m, [username]: r.temp_password }));
    } catch (e: any) { setErr(e.message); }
    finally { setBusy(""); }
  }

  if (loading) return <div className="p-6">Cargando…</div>;
  if (err) return <div className="p-6 text-red-700">{err}</div>;
  if (!a) return null;

  const Section = ({ title, list, tone }: { title: string; list: Acct[]; tone: string }) => (
    <div className="bg-white border rounded-lg p-4">
      <h2 className={`font-semibold ${tone}`}>{title} ({list.length})</h2>
      {list.length === 0 ? (
        <p className="text-sm text-gray-400 mt-1">Ninguna.</p>
      ) : (
        <table className="w-full text-sm mt-2">
          <tbody>
            {list.map((m) => (
              <tr key={m.username} className="border-b last:border-0">
                <td className="py-2">{m.username} {!m.active && <span className="text-xs text-gray-400">(inactiva)</span>}</td>
                <td className="py-2 text-right">
                  {resets[m.username] ? (
                    <span className="font-mono text-green-700">clave: {resets[m.username]}</span>
                  ) : (
                    <button onClick={() => reset(m.username)} disabled={busy === m.username}
                      className="text-blue-600 hover:underline text-xs disabled:opacity-50">
                      {busy === m.username ? "…" : "Resetear clave temporal"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );

  return (
    <div className="p-6 max-w-3xl space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Cuentas sin clave válida</h1>
          <p className="text-gray-500 text-sm mt-1">
            Revisa que ningún buzón quede con clave inservible (vacía, en texto plano o con formato roto)
            tras una migración. Dovecot solo autentica contra la tabla de buzones.
          </p>
        </div>
        <button onClick={load} className="text-sm text-blue-600 hover:underline">Actualizar</button>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Stat label="Total" value={a.total} />
        <Stat label="Con clave válida" value={a.ok} />
        <Stat label="A revisar" value={a.flagged_count} />
      </div>

      {a.flagged_count === 0 && (
        <div className="bg-green-50 border border-green-200 text-green-800 rounded p-3 text-sm">
          ✓ Todas las {a.total} cuentas tienen una clave en formato válido.
        </div>
      )}

      <Section title="Sin contraseña" list={a.empty} tone="text-red-700" />
      <Section title="Texto plano (inseguro)" list={a.plaintext} tone="text-amber-700" />
      <Section title="Formato inválido / hash roto" list={a.invalid_format} tone="text-red-700" />

      <p className="text-xs text-gray-400">
        El reseteo pone una clave temporal fuerte (mostrada una vez para comunicársela al usuario),
        verifica que autentique e invalida la sesión cacheada. El usuario la cambia desde el webmail.
      </p>
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
