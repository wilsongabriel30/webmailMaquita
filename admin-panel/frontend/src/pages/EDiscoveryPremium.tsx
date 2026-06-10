import { useState, useEffect } from "react";
import { api } from "../api/client";

interface Case { id: number; title: string; reason: string; status: string; custodians: number; acknowledged: number; created_at: string | null; }
interface Custodian { id: number; email: string; role: string; on_hold: boolean; notified: string | null; acknowledged: string | null; }

const inputCls = "px-3 py-2 border border-ms-gray-30 rounded text-sm";

export function EDiscoveryPremium() {
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [openCase, setOpenCase] = useState<number | null>(null);
  const [custodians, setCustodians] = useState<Custodian[]>([]);
  const [newCase, setNewCase] = useState({ title: "", reason: "" });
  const [newEmail, setNewEmail] = useState("");
  const [placeHold, setPlaceHold] = useState(true);
  const [notify, setNotify] = useState(true);

  const loadCases = () => api.get<{ cases: Case[] }>("/ediscovery-premium/cases").then((r) => setCases(r.cases || [])).catch(() => {});
  const loadCustodians = (cid: number) => api.get<{ custodians: Custodian[] }>(`/ediscovery-premium/cases/${cid}/custodians`).then((r) => setCustodians(r.custodians || [])).catch(() => {});

  useEffect(() => { loadCases().finally(() => setLoading(false)); }, []);

  const createCase = async () => {
    if (!newCase.title.trim()) { setMsg({ ok: false, text: "Indica un título." }); return; }
    try { await api.post("/ediscovery-premium/cases", newCase); setNewCase({ title: "", reason: "" }); setMsg({ ok: true, text: "Caso creado." }); await loadCases(); }
    catch (e: any) { setMsg({ ok: false, text: e?.message || "Error" }); }
  };
  const openC = async (cid: number) => { if (openCase === cid) { setOpenCase(null); return; } setOpenCase(cid); await loadCustodians(cid); };
  const addCustodian = async (cid: number) => {
    if (!newEmail.trim()) return;
    try {
      const r: any = await api.post(`/ediscovery-premium/cases/${cid}/custodians`, { email: newEmail, place_hold: placeHold, notify });
      setMsg({ ok: true, text: `Custodio agregado${r.on_hold ? " · bajo retención" : ""}${r.notified ? " · aviso enviado" : ""}.` });
      setNewEmail(""); await loadCustodians(cid); await loadCases();
    } catch (e: any) { setMsg({ ok: false, text: e?.message || "Error" }); }
  };
  const renotify = async (cu: Custodian, cid: number) => {
    try { await api.post(`/ediscovery-premium/custodians/${cu.id}/notify`, {}); setMsg({ ok: true, text: "Aviso reenviado." }); await loadCustodians(cid); }
    catch (e: any) { setMsg({ ok: false, text: e?.message || "Error" }); }
  };
  const removeCustodian = async (cu: Custodian, cid: number) => {
    if (!window.confirm(`¿Quitar a ${cu.email} del caso? Se libera su retención.`)) return;
    try { await api.del(`/ediscovery-premium/custodians/${cu.id}`); await loadCustodians(cid); await loadCases(); } catch {}
  };

  if (loading) return <div className="p-6 text-sm text-ms-gray-110">Cargando…</div>;

  return (
    <div className="max-w-3xl">
      <h1 className="text-xl font-semibold text-ms-gray-160 mb-1">eDiscovery — Custodios y retención legal</h1>
      <p className="text-sm text-ms-gray-110 mb-4">
        Designa <b>custodios</b> (personas bajo investigación), pon su buzón en <b>retención legal</b> (no se
        puede borrar) y envíales un <b>aviso formal</b> que deben confirmar. Todo queda registrado.
      </p>
      {msg && <div className={`text-sm mb-4 px-3 py-2 rounded ${msg.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-600"}`}>{msg.text}</div>}

      {/* Crear caso */}
      <div className="bg-white border border-ms-gray-30 rounded-lg p-4 mb-5 flex gap-2 items-end flex-wrap">
        <div className="flex-1 min-w-[160px]"><label className="block text-xs text-ms-gray-110 mb-1">Nuevo caso</label>
          <input className={inputCls + " w-full"} placeholder="Título del caso" value={newCase.title} onChange={(e) => setNewCase({ ...newCase, title: e.target.value })} /></div>
        <div className="flex-1 min-w-[160px]"><label className="block text-xs text-ms-gray-110 mb-1">Motivo</label>
          <input className={inputCls + " w-full"} placeholder="Motivo legal" value={newCase.reason} onChange={(e) => setNewCase({ ...newCase, reason: e.target.value })} /></div>
        <button onClick={createCase} className="px-4 py-2 bg-ms-blue text-white rounded text-sm font-medium">Crear caso</button>
      </div>

      {/* Casos */}
      {cases.length === 0 ? <div className="bg-white border border-ms-gray-30 rounded-lg p-4 text-sm text-ms-gray-110">No hay casos aún.</div> :
        cases.map((c) => (
          <div key={c.id} className="bg-white border border-ms-gray-30 rounded-lg mb-3">
            <div className="flex items-center justify-between p-4 cursor-pointer hover:bg-ms-gray-10" onClick={() => openC(c.id)}>
              <div>
                <div className="font-medium text-ms-gray-160">{c.title} <span className="text-xs bg-ms-gray-20 text-ms-gray-130 rounded px-2 py-0.5 ml-1">{c.status}</span></div>
                <div className="text-xs text-ms-gray-110">{c.reason} · {c.custodians} custodio(s), {c.acknowledged} confirmaron</div>
              </div>
              <span className="text-ms-gray-110 text-xs">{openCase === c.id ? "▲" : "▼"}</span>
            </div>
            {openCase === c.id && (
              <div className="border-t border-ms-gray-20 p-4">
                {/* agregar custodio */}
                <div className="flex gap-2 items-center flex-wrap mb-3">
                  <input className={inputCls + " flex-1 min-w-[180px]"} placeholder="correo@maquita.org" value={newEmail} onChange={(e) => setNewEmail(e.target.value)} />
                  <label className="flex items-center gap-1 text-xs text-ms-gray-130"><input type="checkbox" checked={placeHold} onChange={(e) => setPlaceHold(e.target.checked)} /> Poner en retención</label>
                  <label className="flex items-center gap-1 text-xs text-ms-gray-130"><input type="checkbox" checked={notify} onChange={(e) => setNotify(e.target.checked)} /> Enviar aviso</label>
                  <button onClick={() => addCustodian(c.id)} className="px-3 py-2 bg-ms-blue text-white rounded text-sm">Agregar custodio</button>
                </div>
                {/* lista */}
                {custodians.length === 0 ? <div className="text-xs text-ms-gray-110">Sin custodios aún.</div> : (
                  <table className="w-full text-sm">
                    <thead className="text-ms-gray-110 text-xs"><tr><th className="text-left py-1">Custodio</th><th>Retención</th><th>Avisado</th><th>Confirmó</th><th></th></tr></thead>
                    <tbody>
                      {custodians.map((cu) => (
                        <tr key={cu.id} className="border-t border-ms-gray-10">
                          <td className="py-2 text-ms-gray-160">{cu.email}</td>
                          <td className="text-center">{cu.on_hold ? "🔒 Sí" : "—"}</td>
                          <td className="text-center text-xs">{cu.notified ? "✓" : "—"}</td>
                          <td className="text-center text-xs">{cu.acknowledged ? <span className="text-green-700">✓</span> : <span className="text-amber-600">pendiente</span>}</td>
                          <td className="text-right whitespace-nowrap">
                            <button onClick={() => renotify(cu, c.id)} className="text-xs text-ms-blue hover:underline mr-2">Reenviar</button>
                            <button onClick={() => removeCustodian(cu, c.id)} className="text-xs text-red-600 hover:underline">Quitar</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </div>
        ))}
    </div>
  );
}
