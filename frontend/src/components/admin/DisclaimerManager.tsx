import { useState, useEffect } from 'react';
import { api } from '../../api/client';

interface Disclaimer {
  domain: string;
  html_footer: string;
  text_footer: string;
  is_active: boolean;
}

export function DisclaimerManager() {
  const [disclaimers, setDisclaimers] = useState<Disclaimer[]>([]);
  const [domain, setDomain] = useState('');
  const [htmlFooter, setHtmlFooter] = useState('');
  const [textFooter, setTextFooter] = useState('');
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState('');

  const load = async () => {
    try {
      const data = await api.get<Disclaimer[]>('/admin/disclaimer');
      setDisclaimers(data);
    } catch { setDisclaimers([]); }
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!domain || !htmlFooter) return;
    setLoading(true);
    try {
      await api.post('/admin/disclaimer', { domain, html_footer: htmlFooter, text_footer: textFooter || htmlFooter.replace(/<[^>]+>/g, '') });
      setMsg('Disclaimer guardado');
      setDomain(''); setHtmlFooter(''); setTextFooter('');
      load();
    } catch (e: any) { setMsg(e.message); }
    setLoading(false);
  };

  const remove = async (d: string) => {
    if (!confirm(`¿Eliminar disclaimer de ${d}?`)) return;
    try { await api.del(`/admin/disclaimer/${d}`); load(); } catch {}
  };

  return (
    <div className="p-6 max-w-4xl">
      <h2 className="text-xl font-semibold text-slate-800 mb-4">Disclaimer Corporativo</h2>
      <p className="text-sm text-slate-500 mb-6">Firma/aviso legal que se agrega automáticamente a todos los correos salientes del dominio.</p>

      {msg && <div className="mb-4 p-3 bg-blue-50 text-blue-700 rounded text-sm">{msg}</div>}

      <div className="bg-white border border-slate-200 rounded-lg p-5 mb-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Dominio</label>
          <input value={domain} onChange={e => setDomain(e.target.value)} placeholder="maquita.org"
            className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-orange-300 focus:border-orange-400 outline-none" />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Footer HTML</label>
          <textarea value={htmlFooter} onChange={e => setHtmlFooter(e.target.value)} rows={4}
            placeholder='<div style="border-top:1px solid #ccc;margin-top:16px;padding-top:8px;font-size:11px;color:#666">Fundación Maquita - Este mensaje es confidencial</div>'
            className="w-full px-3 py-2 border border-slate-300 rounded text-sm font-mono focus:ring-2 focus:ring-orange-300 outline-none" />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Footer texto plano (opcional)</label>
          <textarea value={textFooter} onChange={e => setTextFooter(e.target.value)} rows={2}
            placeholder="-- Fundación Maquita - Este mensaje es confidencial"
            className="w-full px-3 py-2 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-orange-300 outline-none" />
        </div>
        <button onClick={save} disabled={loading || !domain || !htmlFooter}
          className="px-4 py-2 bg-orange-500 text-white rounded text-sm font-medium hover:bg-orange-600 disabled:opacity-50">
          {loading ? 'Guardando...' : 'Guardar disclaimer'}
        </button>
      </div>

      <h3 className="text-lg font-medium text-slate-700 mb-3">Disclaimers activos</h3>
      {disclaimers.length === 0 ? (
        <p className="text-sm text-slate-400">No hay disclaimers configurados</p>
      ) : (
        <div className="space-y-3">
          {disclaimers.map(d => (
            <div key={d.domain} className="border border-slate-200 rounded-lg p-4 flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <span className="font-medium text-slate-800">{d.domain}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${d.is_active ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'}`}>
                    {d.is_active ? 'Activo' : 'Inactivo'}
                  </span>
                </div>
                <div className="text-xs text-slate-500 bg-slate-50 p-2 rounded font-mono max-h-20 overflow-auto"
                  dangerouslySetInnerHTML={{ __html: d.html_footer }} />
              </div>
              <button onClick={() => remove(d.domain)} className="ml-4 text-red-500 hover:text-red-700 text-sm">Eliminar</button>
            </div>
          ))}
        </div>
      )}

      <div className="mt-6 p-4 bg-amber-50 border border-amber-200 rounded-lg">
        <p className="text-sm text-amber-800"><strong>Nota:</strong> El disclaimer se inyecta al momento de enviar el correo desde el webmail. No afecta correos enviados desde clientes externos (Outlook, móvil).</p>
      </div>
    </div>
  );
}
