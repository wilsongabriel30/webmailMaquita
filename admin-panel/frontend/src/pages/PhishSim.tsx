import { useState, useEffect } from "react";
import { api } from "../api/client";

interface Template { id: number; name: string; subject: string; difficulty: string; }
interface Recipient { email: string; name: string; }
interface Campaign {
  id: number; name: string; template: string; status: string;
  total: number; sent: number; opened: number; clicked: number; submitted: number; reported: number;
  created_at: string | null;
}
interface Target { email: string; sent: boolean; opened: boolean; clicked: boolean; submitted: boolean; reported: boolean; }

const pct = (n: number, d: number) => (d ? Math.round((n / d) * 100) : 0);

export function PhishSim() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [recipients, setRecipients] = useState<Recipient[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  // form
  const [name, setName] = useState("");
  const [templateId, setTemplateId] = useState<number | null>(null);
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);

  // detail
  const [detailId, setDetailId] = useState<number | null>(null);
  const [targets, setTargets] = useState<Target[]>([]);

  const loadCampaigns = () => api.get<{ campaigns: Campaign[] }>("/phish/campaigns").then((r) => setCampaigns(r.campaigns || [])).catch(() => {});

  useEffect(() => {
    Promise.all([
      api.get<{ templates: Template[] }>("/phish/templates").then((r) => { setTemplates(r.templates || []); if (r.templates?.[0]) setTemplateId(r.templates[0].id); }).catch(() => {}),
      api.get<{ recipients: Recipient[] }>("/phish/recipients").then((r) => setRecipients(r.recipients || [])).catch(() => {}),
      loadCampaigns(),
    ]).finally(() => setLoading(false));
  }, []);

  const filtered = recipients.filter((r) => r.email.toLowerCase().includes(search.toLowerCase()) || (r.name || "").toLowerCase().includes(search.toLowerCase()));
  const toggle = (em: string) => { const s = new Set(sel); s.has(em) ? s.delete(em) : s.add(em); setSel(s); };
  const selectAllFiltered = () => { const s = new Set(sel); filtered.forEach((r) => s.add(r.email)); setSel(s); };
  const clearSel = () => setSel(new Set());

  const create = async () => {
    if (!name.trim() || !templateId || sel.size === 0) { setMsg({ ok: false, text: "Completa nombre, plantilla y al menos un destinatario." }); return; }
    setCreating(true); setMsg(null);
    try {
      await api.post("/phish/campaigns", { name, template_id: templateId, recipients: Array.from(sel) });
      setName(""); clearSel(); setMsg({ ok: true, text: "Campaña creada (en borrador). Pulsa «Enviar» para lanzarla." });
      await loadCampaigns();
    } catch (e: any) { setMsg({ ok: false, text: e?.message || "Error al crear" }); }
    finally { setCreating(false); }
  };

  const send = async (c: Campaign) => {
    if (!window.confirm(`¿Lanzar la campaña «${c.name}» a ${c.total} persona(s)? Recibirán un correo de phishing simulado.`)) return;
    try { const r: any = await api.post(`/phish/campaigns/${c.id}/send`, {}); setMsg({ ok: true, text: `Enviada a ${r.sent} persona(s).` }); await loadCampaigns(); }
    catch (e: any) { setMsg({ ok: false, text: e?.message || "Error al enviar" }); }
  };

  const remove = async (c: Campaign) => {
    if (!window.confirm(`¿Eliminar la campaña «${c.name}» y sus resultados?`)) return;
    try { await api.del(`/phish/campaigns/${c.id}`); if (detailId === c.id) setDetailId(null); await loadCampaigns(); }
    catch (e: any) { setMsg({ ok: false, text: e?.message || "Error al eliminar" }); }
  };

  const openDetail = async (c: Campaign) => {
    if (detailId === c.id) { setDetailId(null); return; }
    setDetailId(c.id);
    try { const r: any = await api.get(`/phish/campaigns/${c.id}`); setTargets(r.targets || []); } catch { setTargets([]); }
  };

  if (loading) return <div className="p-6 text-sm text-ms-gray-110">Cargando…</div>;

  return (
    <div className="max-w-4xl">
      <h1 className="text-xl font-semibold text-ms-gray-160 mb-1">Simulación de phishing</h1>
      <p className="text-sm text-ms-gray-110 mb-4">
        Envía correos de phishing <b>falsos y seguros</b> a tu personal para entrenarlos. Mide quién hace clic
        o «entrega su contraseña», y enséñales a reconocer el engaño. <b>Nunca se guardan contraseñas reales.</b>
      </p>

      {msg && <div className={`text-sm mb-4 px-3 py-2 rounded ${msg.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-600"}`}>{msg.text}</div>}

      {/* Crear campaña */}
      <div className="bg-white border border-ms-gray-30 rounded-lg p-5 mb-6">
        <h2 className="text-base font-semibold text-ms-gray-160 mb-3">Nueva campaña</h2>
        <div className="grid grid-cols-2 gap-4 mb-3">
          <div>
            <label className="block text-sm font-medium text-ms-gray-130 mb-1">Nombre de la campaña</label>
            <input className="w-full px-3 py-2 border border-ms-gray-30 rounded text-sm" placeholder="Ej.: Capacitación junio 2026"
              value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-ms-gray-130 mb-1">Plantilla del correo señuelo</label>
            <select className="w-full px-3 py-2 border border-ms-gray-30 rounded text-sm" value={templateId ?? ""}
              onChange={(e) => setTemplateId(parseInt(e.target.value))}>
              {templates.map((t) => <option key={t.id} value={t.id}>{t.name} — «{t.subject}» (dificultad {t.difficulty})</option>)}
            </select>
          </div>
        </div>

        <label className="block text-sm font-medium text-ms-gray-130 mb-1">Destinatarios ({sel.size} seleccionados)</label>
        <div className="flex gap-2 mb-2">
          <input className="flex-1 px-3 py-1.5 border border-ms-gray-30 rounded text-sm" placeholder="Buscar buzón…"
            value={search} onChange={(e) => setSearch(e.target.value)} />
          <button onClick={selectAllFiltered} className="px-3 py-1.5 bg-ms-gray-20 text-ms-gray-160 rounded text-xs whitespace-nowrap">Seleccionar visibles</button>
          <button onClick={clearSel} className="px-3 py-1.5 bg-ms-gray-20 text-ms-gray-160 rounded text-xs whitespace-nowrap">Limpiar</button>
        </div>
        <div className="border border-ms-gray-20 rounded max-h-48 overflow-auto mb-3">
          {filtered.slice(0, 300).map((r) => (
            <label key={r.email} className="flex items-center gap-2 px-3 py-1.5 text-sm hover:bg-ms-gray-10 cursor-pointer border-b border-ms-gray-10">
              <input type="checkbox" checked={sel.has(r.email)} onChange={() => toggle(r.email)} />
              <span className="text-ms-gray-160">{r.email}</span>
              {r.name && <span className="text-ms-gray-110 text-xs">— {r.name}</span>}
            </label>
          ))}
          {filtered.length === 0 && <div className="px-3 py-2 text-xs text-ms-gray-110">Sin resultados.</div>}
        </div>
        <button onClick={create} disabled={creating} className="px-4 py-2 bg-ms-blue text-white rounded text-sm font-medium disabled:opacity-60">
          {creating ? "Creando…" : "Crear campaña (borrador)"}
        </button>
      </div>

      {/* Lista de campañas */}
      <h2 className="text-base font-semibold text-ms-gray-160 mb-2">Campañas</h2>
      {campaigns.length === 0 ? (
        <div className="bg-white border border-ms-gray-30 rounded-lg p-4 text-sm text-ms-gray-110">Aún no hay campañas.</div>
      ) : campaigns.map((c) => (
        <div key={c.id} className="bg-white border border-ms-gray-30 rounded-lg p-4 mb-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <div className="font-medium text-ms-gray-160">{c.name}
                <span className={`ml-2 text-xs rounded px-2 py-0.5 ${c.status === "enviado" ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"}`}>{c.status}</span>
              </div>
              <div className="text-xs text-ms-gray-110">{c.template} · {c.total} destinatario(s)</div>
            </div>
            <div className="flex items-center gap-2">
              {c.status !== "enviado" && <button onClick={() => send(c)} className="px-3 py-1.5 bg-ms-blue text-white rounded text-xs font-medium">Enviar ahora</button>}
              <button onClick={() => openDetail(c)} className="px-3 py-1.5 bg-ms-gray-20 text-ms-gray-160 rounded text-xs">{detailId === c.id ? "Ocultar" : "Ver detalle"}</button>
              <button onClick={() => remove(c)} className="px-2 py-1.5 text-red-600 text-xs hover:underline">Eliminar</button>
            </div>
          </div>

          {c.status === "enviado" && (
            <div className="grid grid-cols-4 gap-3 mt-3 text-center">
              {[["Abrieron", c.opened, "#0078d4"], ["Hicieron clic", c.clicked, "#ca5010"], ["Dieron clave", c.submitted, "#d13438"], ["Reportaron 👍", c.reported, "#107c10"]].map(([lbl, val, col]: any) => (
                <div key={lbl} className="border border-ms-gray-20 rounded p-2">
                  <div className="text-lg font-bold" style={{ color: col }}>{pct(val, c.total)}%</div>
                  <div className="text-[11px] text-ms-gray-110">{lbl} ({val}/{c.total})</div>
                </div>
              ))}
            </div>
          )}

          {detailId === c.id && (
            <div className="mt-3 border-t border-ms-gray-20 pt-3">
              <table className="w-full text-xs">
                <thead className="text-ms-gray-110">
                  <tr><th className="text-left py-1">Persona</th><th>Abrió</th><th>Clic</th><th>Dio clave</th><th>Reportó</th></tr>
                </thead>
                <tbody>
                  {targets.map((t) => (
                    <tr key={t.email} className="border-t border-ms-gray-10">
                      <td className="py-1 text-ms-gray-160">{t.email}</td>
                      <td className="text-center">{t.opened ? "•" : ""}</td>
                      <td className="text-center text-[#ca5010]">{t.clicked ? "✓" : ""}</td>
                      <td className="text-center text-[#d13438]">{t.submitted ? "✓" : ""}</td>
                      <td className="text-center text-[#107c10]">{t.reported ? "✓" : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
