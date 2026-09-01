import { useEffect, useState } from 'react';
import { api } from '../../api/client';

interface ApiKey { id: number; name: string; prefix: string; permissions: string[]; expires_at: string | null; }
interface Webhook { id: number; url: string; events: string[]; }

export function IntegrationsSettings() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [newKeyName, setNewKeyName] = useState('');
  const [keySend, setKeySend] = useState(false);
  const [createdKey, setCreatedKey] = useState('');
  const [hooks, setHooks] = useState<Webhook[]>([]);
  const [hookUrl, setHookUrl] = useState('');
  const [hookEvents, setHookEvents] = useState('mail.received');
  const [hookErr, setHookErr] = useState('');
  const [importMsg, setImportMsg] = useState('');

  const loadKeys = () => api.get<ApiKey[]>('/keys').then(setKeys).catch(() => {});
  const loadHooks = () => api.get<Webhook[]>('/webhooks').then(setHooks).catch(() => {});
  useEffect(() => { loadKeys(); loadHooks(); }, []);

  const createKey = async () => {
    if (!newKeyName.trim()) return;
    try {
      const r = await api.post<any>('/keys', { name: newKeyName, permissions: keySend ? ['read', 'send'] : ['read'] });
      setCreatedKey(r?.key || ''); setNewKeyName(''); loadKeys();
    } catch { /* fail-open */ }
  };
  const delKey = async (id: number) => { if (!confirm('¿Eliminar la clave?')) return; await api.del(`/keys/${id}`); loadKeys(); };

  const createHook = async () => {
    if (!hookUrl.trim()) return;
    setHookErr('');
    try {
      await api.post('/webhooks', { url: hookUrl, events: hookEvents.split(',').map((e) => e.trim()).filter(Boolean) });
      setHookUrl(''); loadHooks();
    } catch { setHookErr('No se pudo crear (revisa la URL y los eventos).'); }
  };
  const testHook = async (id: number) => { try { await api.post(`/webhooks/${id}/test`, {}); alert('Webhook de prueba enviado.'); } catch { alert('Error al probar.'); } };
  const delHook = async (id: number) => { if (!confirm('¿Eliminar el webhook?')) return; await api.del(`/webhooks/${id}`); loadHooks(); };

  const importContacts = async (e: any) => {
    const f = e.target.files?.[0]; if (!f) return;
    setImportMsg('Importando…');
    const fd = new FormData(); fd.append('file', f);
    try {
      const res = await fetch('/api/import/contacts', { method: 'POST', body: fd, credentials: 'include' });
      const j = await res.json().catch(() => ({}));
      setImportMsg(res.ok ? `Importación iniciada${j.job_id ? ' (job ' + j.job_id + ')' : ''}.` : `Error: ${j.detail || res.status}`);
    } catch { setImportMsg('Error al importar.'); }
    e.target.value = '';
  };

  const cardStyle = { border: '1px solid #e1dfdd', background: '#fff' } as const;
  const inpStyle = { border: '1px solid #e1dfdd' } as const;

  return (
    <div className="space-y-5 max-w-2xl">
      <div className="rounded-lg p-4 space-y-3" style={cardStyle}>
        <h3 className="text-sm font-semibold" style={{ color: '#323130' }}>Claves de API</h3>
        <p className="text-xs" style={{ color: '#605e5c' }}>Para integrar tu correo con otras apps. La clave se muestra una sola vez.</p>
        {createdKey && (
          <div className="rounded p-2 text-xs break-all" style={{ background: '#fff4ce', color: '#7a6400' }}>
            Tu nueva clave (cópiala ahora): <b>{createdKey}</b>
          </div>
        )}
        <div className="space-y-1">
          {keys.map((k) => (
            <div key={k.id} className="flex items-center justify-between text-sm py-1" style={{ borderBottom: '1px solid #f3f2f1' }}>
              <span style={{ color: '#323130' }}>{k.name} <span className="font-mono text-xs" style={{ color: '#a19f9d' }}>{k.prefix}…</span> <span className="text-xs" style={{ color: '#605e5c' }}>[{(k.permissions || []).join(', ')}]</span></span>
              <button onClick={() => delKey(k.id)} className="text-xs hover:underline" style={{ color: '#a4262c' }}>Eliminar</button>
            </div>
          ))}
          {!keys.length && <div className="text-xs" style={{ color: '#a19f9d' }}>Sin claves.</div>}
        </div>
        <div className="flex gap-2 items-center flex-wrap">
          <input value={newKeyName} onChange={(e) => setNewKeyName(e.target.value)} placeholder="Nombre de la clave" className="px-3 py-2 rounded text-sm" style={inpStyle} />
          <label className="text-xs flex gap-1 items-center" style={{ color: '#605e5c' }}><input type="checkbox" checked={keySend} onChange={(e) => setKeySend(e.target.checked)} /> permitir envío</label>
          <button onClick={createKey} className="text-white text-sm px-3 py-2 rounded" style={{ backgroundColor: '#0078d4' }}>Crear clave</button>
        </div>
      </div>

      <div className="rounded-lg p-4 space-y-3" style={cardStyle}>
        <h3 className="text-sm font-semibold" style={{ color: '#323130' }}>Webhooks</h3>
        <p className="text-xs" style={{ color: '#605e5c' }}>Recibe avisos en una URL cuando ocurren eventos (ej. correo recibido).</p>
        <div className="space-y-1">
          {hooks.map((h) => (
            <div key={h.id} className="flex items-center justify-between text-sm py-1" style={{ borderBottom: '1px solid #f3f2f1' }}>
              <span className="truncate" style={{ color: '#323130' }}>{h.url} <span className="text-xs" style={{ color: '#605e5c' }}>[{(h.events || []).join(', ')}]</span></span>
              <span className="flex gap-2 shrink-0">
                <button onClick={() => testHook(h.id)} className="text-xs hover:underline" style={{ color: '#0078d4' }}>Probar</button>
                <button onClick={() => delHook(h.id)} className="text-xs hover:underline" style={{ color: '#a4262c' }}>Eliminar</button>
              </span>
            </div>
          ))}
          {!hooks.length && <div className="text-xs" style={{ color: '#a19f9d' }}>Sin webhooks.</div>}
        </div>
        {hookErr && <div className="text-xs" style={{ color: '#a4262c' }}>{hookErr}</div>}
        <div className="flex gap-2 items-center flex-wrap">
          <input value={hookUrl} onChange={(e) => setHookUrl(e.target.value)} placeholder="https://tu-app/webhook" className="px-3 py-2 rounded text-sm flex-1" style={inpStyle} />
          <input value={hookEvents} onChange={(e) => setHookEvents(e.target.value)} placeholder="eventos (coma)" className="px-3 py-2 rounded text-sm" style={inpStyle} />
          <button onClick={createHook} className="text-white text-sm px-3 py-2 rounded" style={{ backgroundColor: '#0078d4' }}>Crear</button>
        </div>
      </div>

      <div className="rounded-lg p-4 space-y-3" style={cardStyle}>
        <h3 className="text-sm font-semibold" style={{ color: '#323130' }}>Importar contactos</h3>
        <p className="text-xs" style={{ color: '#605e5c' }}>Sube un archivo .csv o .vcf con tus contactos.</p>
        <input type="file" accept=".csv,.vcf,.vcard" onChange={importContacts}
          className="text-sm text-[#605e5c] cursor-pointer file:mr-3 file:cursor-pointer file:rounded file:border-0 file:bg-[#0078d4] file:px-3 file:py-1.5 file:text-[13px] file:font-semibold file:text-white hover:file:bg-[#106ebe]" />
        {importMsg && <div className="text-xs" style={{ color: '#605e5c' }}>{importMsg}</div>}
      </div>
    </div>
  );
}
