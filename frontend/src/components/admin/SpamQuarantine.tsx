import { useEffect, useState } from 'react';
import { api } from '../../api/client';

// --- Tipos ---
interface JunkMessage {
  uid: string;
  username: string;
  from?: string;
  subject?: string;
  date?: string;
  flags?: string;
}

interface LogEntry {
  timestamp: string;
  level: string;
  verdict: string;
  details: string;
}

type Tab = 'quarantine' | 'log' | 'keywords' | 'whitelist';

export function SpamQuarantine() {
  const [tab, setTab] = useState<Tab>('quarantine');

  const tabs: { key: Tab; label: string; icon: string }[] = [
    { key: 'quarantine', label: 'Cuarentena', icon: 'M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z' },
    { key: 'log', label: 'Log del Filtro', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2' },
    { key: 'keywords', label: 'Palabras Clave', icon: 'M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z' },
    { key: 'whitelist', label: 'Whitelist', icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' },
  ];

  return (
    <div className="p-8 max-w-6xl">
      <h1 className="text-2xl font-bold text-slate-800 mb-2">Filtro Anti-Spam</h1>
      <p className="text-sm text-slate-500 mb-6">Gestiona la cuarentena, palabras clave y whitelist del filtro de spam</p>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-slate-200">
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              tab === t.key
                ? 'border-orange-500 text-orange-700'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={t.icon} />
            </svg>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'quarantine' && <QuarantineTab />}
      {tab === 'log' && <LogTab />}
      {tab === 'keywords' && <KeywordsTab />}
      {tab === 'whitelist' && <WhitelistTab />}
    </div>
  );
}


// =====================================================
// TAB 1: Cuarentena — Mensajes en Junk de todos los usuarios
// =====================================================
function QuarantineTab() {
  const [messages, setMessages] = useState<JunkMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const load = () => {
    setLoading(true);
    setSelected(new Set());
    api.get<JunkMessage[]>('/admin/spam/junk')
      .then(setMessages)
      .catch(() => setMessages([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const doAction = async (action: 'approve' | 'confirm' | 'delete', username: string, uid: string) => {
    const key = `${username}:${uid}`;
    setActionLoading(key);
    try {
      await api.post(`/admin/spam/${action}`, { username, uid });
      setMessages(prev => prev.filter(m => !(m.username === username && m.uid === uid)));
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Error');
    } finally {
      setActionLoading(null);
    }
  };

  const doBulkAction = async (action: 'approve' | 'confirm' | 'delete') => {
    const items = messages.filter(m => selected.has(`${m.username}:${m.uid}`));
    if (!items.length) return;
    if (action === 'delete' && !confirm(`Eliminar ${items.length} mensaje(s) permanentemente?`)) return;

    for (const m of items) {
      try {
        await api.post(`/admin/spam/${action}`, { username: m.username, uid: m.uid });
      } catch { /* continue */ }
    }
    load();
  };

  const toggleSelect = (key: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === messages.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(messages.map(m => `${m.username}:${m.uid}`)));
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-500">{messages.length} mensaje(s) en cuarentena</span>
          {selected.size > 0 && (
            <span className="text-sm font-medium text-orange-600">{selected.size} seleccionado(s)</span>
          )}
        </div>
        <div className="flex gap-2">
          {selected.size > 0 && (
            <>
              <button onClick={() => doBulkAction('approve')}
                className="px-3 py-1.5 text-xs bg-green-50 text-green-700 rounded-lg hover:bg-green-100 font-medium">
                Aprobar seleccionados
              </button>
              <button onClick={() => doBulkAction('delete')}
                className="px-3 py-1.5 text-xs bg-red-50 text-red-700 rounded-lg hover:bg-red-100 font-medium">
                Eliminar seleccionados
              </button>
            </>
          )}
          <button onClick={load}
            className="px-4 py-2 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 text-sm">
            Refrescar
          </button>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-8 text-slate-400">Cargando mensajes en cuarentena...</div>
      ) : messages.length === 0 ? (
        <div className="text-center py-12 text-slate-400">
          <svg className="w-12 h-12 mx-auto mb-3 text-green-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-lg">Sin spam en cuarentena</p>
          <p className="text-sm mt-1">Todas las carpetas Junk están vacías</p>
        </div>
      ) : (
        <div className="border border-slate-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="w-10 px-3 py-2">
                  <input type="checkbox" checked={selected.size === messages.length && messages.length > 0}
                    onChange={toggleAll} className="rounded border-slate-300" />
                </th>
                <th className="text-left px-3 py-2 text-xs font-semibold text-slate-500 uppercase">Usuario</th>
                <th className="text-left px-3 py-2 text-xs font-semibold text-slate-500 uppercase">De</th>
                <th className="text-left px-3 py-2 text-xs font-semibold text-slate-500 uppercase">Asunto</th>
                <th className="text-left px-3 py-2 text-xs font-semibold text-slate-500 uppercase">Fecha</th>
                <th className="text-right px-3 py-2 text-xs font-semibold text-slate-500 uppercase">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {messages.map(m => {
                const key = `${m.username}:${m.uid}`;
                const isLoading = actionLoading === key;
                return (
                  <tr key={key} className={`hover:bg-slate-50 ${selected.has(key) ? 'bg-orange-50' : ''}`}>
                    <td className="px-3 py-2">
                      <input type="checkbox" checked={selected.has(key)}
                        onChange={() => toggleSelect(key)} className="rounded border-slate-300" />
                    </td>
                    <td className="px-3 py-2 text-slate-600 font-mono text-xs">{m.username}</td>
                    <td className="px-3 py-2 text-slate-700 max-w-[200px] truncate">{m.from || '-'}</td>
                    <td className="px-3 py-2 text-slate-800 font-medium max-w-[250px] truncate">{m.subject || '(sin asunto)'}</td>
                    <td className="px-3 py-2 text-slate-500 text-xs whitespace-nowrap">{m.date || '-'}</td>
                    <td className="px-3 py-2 text-right">
                      <div className="flex gap-1 justify-end">
                        <button onClick={() => doAction('approve', m.username, m.uid)} disabled={isLoading}
                          title="Mover a Inbox (no es spam)"
                          className="px-2.5 py-1 text-xs bg-green-50 text-green-700 rounded hover:bg-green-100 disabled:opacity-50">
                          Aprobar
                        </button>
                        <button onClick={() => doAction('confirm', m.username, m.uid)} disabled={isLoading}
                          title="Confirmar como spam (marcar leído)"
                          className="px-2.5 py-1 text-xs bg-yellow-50 text-yellow-700 rounded hover:bg-yellow-100 disabled:opacity-50">
                          Spam
                        </button>
                        <button onClick={() => { if (confirm('Eliminar permanentemente?')) doAction('delete', m.username, m.uid); }}
                          disabled={isLoading}
                          title="Eliminar permanentemente"
                          className="px-2.5 py-1 text-xs bg-red-50 text-red-700 rounded hover:bg-red-100 disabled:opacity-50">
                          Eliminar
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}


// =====================================================
// TAB 2: Log del Filtro Spam
// =====================================================
function LogTab() {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    api.get<LogEntry[]>('/admin/spam/log')
      .then(setEntries)
      .catch(() => setEntries([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm text-slate-500">{entries.length} entradas recientes</span>
        <button onClick={load} className="px-4 py-2 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 text-sm">
          Refrescar
        </button>
      </div>

      {loading ? (
        <div className="text-center py-8 text-slate-400">Cargando log...</div>
      ) : entries.length === 0 ? (
        <div className="text-center py-12 text-slate-400">
          <p className="text-lg">Log vacío</p>
          <p className="text-sm mt-1">No hay entradas en el log del filtro</p>
        </div>
      ) : (
        <div className="border border-slate-200 rounded-lg overflow-hidden max-h-[600px] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200 sticky top-0">
              <tr>
                <th className="text-left px-3 py-2 text-xs font-semibold text-slate-500 uppercase">Fecha</th>
                <th className="text-left px-3 py-2 text-xs font-semibold text-slate-500 uppercase">Nivel</th>
                <th className="text-left px-3 py-2 text-xs font-semibold text-slate-500 uppercase">Veredicto</th>
                <th className="text-left px-3 py-2 text-xs font-semibold text-slate-500 uppercase">Detalles</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {entries.map((e, i) => (
                <tr key={i} className="hover:bg-slate-50">
                  <td className="px-3 py-2 text-slate-500 text-xs whitespace-nowrap font-mono">{e.timestamp}</td>
                  <td className="px-3 py-2">
                    <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                      e.level === 'ERROR' ? 'bg-red-100 text-red-700' :
                      e.level === 'WARNING' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-slate-100 text-slate-600'
                    }`}>{e.level}</span>
                  </td>
                  <td className="px-3 py-2">
                    <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                      e.verdict.includes('SPAM') ? 'bg-red-100 text-red-700' :
                      e.verdict.includes('HAM') ? 'bg-green-100 text-green-700' :
                      'bg-slate-100 text-slate-600'
                    }`}>{e.verdict}</span>
                  </td>
                  <td className="px-3 py-2 text-slate-600 text-xs max-w-[400px] truncate" title={e.details}>{e.details}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}


// =====================================================
// TAB 3: Keywords — Editar palabras clave del filtro
// =====================================================
function KeywordsTab() {
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.get<{ content: string }>('/admin/spam/keywords')
      .then(d => setContent(d.content))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true);
    setSaved(false);
    try {
      await api.put('/admin/spam/keywords', { content });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Error al guardar');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <div>
            <h3 className="text-sm font-semibold text-slate-700">Palabras clave del filtro anti-spam</h3>
            <p className="text-xs text-slate-500 mt-1">
              Formato: <code className="bg-slate-100 px-1 rounded">palabra o frase|peso</code> — Score &ge; 3 = SPAM. Se aplican sin reiniciar servicios.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {saved && <span className="text-xs text-green-600 font-medium">Guardado correctamente</span>}
            <button onClick={save} disabled={saving}
              className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 text-sm font-medium disabled:opacity-50">
              {saving ? 'Guardando...' : 'Guardar cambios'}
            </button>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-8 text-slate-400">Cargando...</div>
      ) : (
        <textarea
          value={content}
          onChange={e => setContent(e.target.value)}
          className="w-full h-[500px] font-mono text-sm border border-slate-300 rounded-lg p-4 focus:ring-2 focus:ring-orange-300 focus:border-orange-400 outline-none resize-none bg-slate-50"
          placeholder="# Formato: palabra|peso&#10;spam word|2&#10;phishing attempt|3"
          spellCheck={false}
        />
      )}
    </div>
  );
}


// =====================================================
// TAB 4: Whitelist — Editar dominios/emails permitidos
// =====================================================
function WhitelistTab() {
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.get<{ content: string }>('/admin/spam/whitelist')
      .then(d => setContent(d.content))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true);
    setSaved(false);
    try {
      await api.put('/admin/spam/whitelist', { content });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Error al guardar');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <div>
            <h3 className="text-sm font-semibold text-slate-700">Whitelist de remitentes</h3>
            <p className="text-xs text-slate-500 mt-1">
              Un dominio o email por línea. Los remitentes en esta lista nunca serán marcados como spam.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {saved && <span className="text-xs text-green-600 font-medium">Guardado correctamente</span>}
            <button onClick={save} disabled={saving}
              className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 text-sm font-medium disabled:opacity-50">
              {saving ? 'Guardando...' : 'Guardar cambios'}
            </button>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-8 text-slate-400">Cargando...</div>
      ) : (
        <textarea
          value={content}
          onChange={e => setContent(e.target.value)}
          className="w-full h-[500px] font-mono text-sm border border-slate-300 rounded-lg p-4 focus:ring-2 focus:ring-orange-300 focus:border-orange-400 outline-none resize-none bg-slate-50"
          placeholder="# Un dominio o email por línea&#10;gmail.com&#10;usuario@ejemplo.com"
          spellCheck={false}
        />
      )}
    </div>
  );
}
