import { useEffect, useState, useCallback } from "react";
import { api } from "../../api/client";

interface Entry {
  value: string;
  reason: string;
  date: string;
}

interface SendersData {
  domains: Entry[];
  addresses: Entry[];
}

export function MailGuardPanel() {
  const [senders, setSenders] = useState<SendersData>({ domains: [], addresses: [] });
  const [extensions, setExtensions] = useState<Entry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [okMsg, setOkMsg] = useState("");

  const [newSender, setNewSender] = useState("");
  const [newSenderReason, setNewSenderReason] = useState("");
  const [newExt, setNewExt] = useState("");
  const [newExtReason, setNewExtReason] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [s, e] = await Promise.all([
        api.get<SendersData>("/admin/mailguard/senders"),
        api.get<{ extensions: Entry[] }>("/admin/mailguard/extensions"),
      ]);
      setSenders(s);
      setExtensions(e.extensions);
      setError("");
    } catch (err: any) {
      setError(err?.message || "Error cargando bloqueos");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const flash = (msg: string) => {
    setOkMsg(msg);
    setTimeout(() => setOkMsg(""), 4000);
  };

  const addSender = async () => {
    if (!newSender.trim()) return;
    setBusy(true);
    try {
      const r = await api.post<{ message: string }>("/admin/mailguard/senders", {
        value: newSender.trim(),
        reason: newSenderReason.trim(),
      });
      flash(r.message);
      setNewSender("");
      setNewSenderReason("");
      await load();
    } catch (err: any) {
      setError(err?.message || "Error al bloquear");
    } finally {
      setBusy(false);
    }
  };

  const removeSender = async (value: string) => {
    if (!confirm(`¿Desbloquear ${value}? Sus correos volverán a entrar.`)) return;
    try {
      await api.del(`/admin/mailguard/senders/${encodeURIComponent(value)}`);
      flash(`Desbloqueado: ${value}`);
      await load();
    } catch (err: any) {
      setError(err?.message || "Error al desbloquear");
    }
  };

  const addExt = async () => {
    if (!newExt.trim()) return;
    setBusy(true);
    try {
      const r = await api.post<{ message: string }>("/admin/mailguard/extensions", {
        ext: newExt.trim(),
        reason: newExtReason.trim(),
      });
      flash(r.message);
      setNewExt("");
      setNewExtReason("");
      await load();
    } catch (err: any) {
      setError(err?.message || "Error al bloquear extensión");
    } finally {
      setBusy(false);
    }
  };

  const removeExt = async (ext: string) => {
    if (!confirm(`¿Desbloquear la extensión .${ext}?`)) return;
    try {
      await api.del(`/admin/mailguard/extensions/${encodeURIComponent(ext)}`);
      flash(`Extensión .${ext} desbloqueada`);
      await load();
    } catch (err: any) {
      setError(err?.message || "Error al desbloquear extensión");
    }
  };

  const allSenders = [
    ...senders.domains.map((d) => ({ ...d, tipo: "Dominio" })),
    ...senders.addresses.map((a) => ({ ...a, tipo: "Dirección" })),
  ];

  if (loading) {
    return <div className="p-8 text-slate-500">Cargando bloqueos…</div>;
  }

  return (
    <div className="p-6 max-w-5xl space-y-8 overflow-y-auto">
      <div>
        <h1 className="text-xl font-semibold text-slate-800">Bloqueos de Correo</h1>
        <p className="text-sm text-slate-500 mt-1">
          Los remitentes y extensiones de esta lista se <strong>rechazan en el servidor</strong> antes
          de llegar a los buzones (Rspamd). Úselo para cortar campañas de malware/phishing.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-2">
          {error}
          <button className="ml-3 underline" onClick={() => { setError(""); load(); }}>Reintentar</button>
        </div>
      )}
      {okMsg && (
        <div className="bg-green-50 border border-green-200 text-green-700 text-sm rounded-lg px-4 py-2">{okMsg}</div>
      )}

      {/* ── Remitentes bloqueados ── */}
      <section className="bg-white border border-slate-200 rounded-xl shadow-sm">
        <div className="px-5 py-4 border-b border-slate-100">
          <h2 className="font-medium text-slate-800">Remitentes bloqueados ({allSenders.length})</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Acepta un dominio completo (ej: <code className="bg-slate-100 px-1 rounded">zh-klvpn.com</code>) o
            una dirección exacta (ej: <code className="bg-slate-100 px-1 rounded">malo@spam.com</code>).
          </p>
        </div>
        <div className="px-5 py-3 flex flex-wrap gap-2 border-b border-slate-100 bg-slate-50">
          <input
            className="flex-1 min-w-48 border border-slate-300 rounded-lg px-3 py-1.5 text-sm"
            placeholder="dominio.com o direccion@dominio.com"
            value={newSender}
            onChange={(e) => setNewSender(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addSender()}
          />
          <input
            className="flex-1 min-w-48 border border-slate-300 rounded-lg px-3 py-1.5 text-sm"
            placeholder="Motivo (ej: phishing RRHH falso)"
            value={newSenderReason}
            onChange={(e) => setNewSenderReason(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addSender()}
          />
          <button
            onClick={addSender}
            disabled={busy || !newSender.trim()}
            className="bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg px-4 py-1.5"
          >
            Bloquear
          </button>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-slate-500 border-b border-slate-100">
              <th className="px-5 py-2">Remitente</th>
              <th className="px-3 py-2">Tipo</th>
              <th className="px-3 py-2">Motivo</th>
              <th className="px-3 py-2">Fecha</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {allSenders.length === 0 && (
              <tr><td colSpan={5} className="px-5 py-4 text-slate-400">Sin remitentes bloqueados</td></tr>
            )}
            {allSenders.map((s) => (
              <tr key={s.value} className="border-b border-slate-50 hover:bg-slate-50">
                <td className="px-5 py-2 font-mono text-slate-800">{s.value}</td>
                <td className="px-3 py-2 text-slate-500">{s.tipo}</td>
                <td className="px-3 py-2 text-slate-600">{s.reason || "—"}</td>
                <td className="px-3 py-2 text-slate-500 whitespace-nowrap">{s.date || "—"}</td>
                <td className="px-3 py-2 text-right">
                  <button onClick={() => removeSender(s.value)} className="text-red-600 hover:underline text-xs">
                    Desbloquear
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* ── Extensiones bloqueadas ── */}
      <section className="bg-white border border-slate-200 rounded-xl shadow-sm">
        <div className="px-5 py-4 border-b border-slate-100">
          <h2 className="font-medium text-slate-800">Extensiones de adjunto bloqueadas ({extensions.length})</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Correos con adjuntos de estas extensiones se rechazan. Incluye ejecutables y archivos
            partidos (<code className="bg-slate-100 px-1 rounded">.001</code>) usados para esconder malware.
          </p>
        </div>
        <div className="px-5 py-3 flex flex-wrap gap-2 border-b border-slate-100 bg-slate-50">
          <input
            className="w-40 border border-slate-300 rounded-lg px-3 py-1.5 text-sm"
            placeholder="ext (ej: 004)"
            value={newExt}
            onChange={(e) => setNewExt(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addExt()}
          />
          <input
            className="flex-1 min-w-48 border border-slate-300 rounded-lg px-3 py-1.5 text-sm"
            placeholder="Motivo"
            value={newExtReason}
            onChange={(e) => setNewExtReason(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addExt()}
          />
          <button
            onClick={addExt}
            disabled={busy || !newExt.trim()}
            className="bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg px-4 py-1.5"
          >
            Bloquear
          </button>
        </div>
        <div className="px-5 py-4 flex flex-wrap gap-2">
          {extensions.length === 0 && <span className="text-slate-400 text-sm">Sin extensiones bloqueadas</span>}
          {extensions.map((e) => (
            <span
              key={e.value}
              title={`${e.reason || ""} ${e.date || ""}`.trim()}
              className="inline-flex items-center gap-1.5 bg-slate-100 border border-slate-200 rounded-full px-3 py-1 text-sm font-mono text-slate-700"
            >
              .{e.value}
              <button
                onClick={() => removeExt(e.value)}
                className="text-slate-400 hover:text-red-600 font-sans"
                title={`Desbloquear .${e.value}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      </section>

      <p className="text-xs text-slate-400">
        Nota: los cambios se aplican en segundos (Rspamd recarga los mapas automáticamente).
        Todo queda registrado en Auditoría.
      </p>
    </div>
  );
}
