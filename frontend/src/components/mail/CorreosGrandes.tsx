/**
 * CorreosGrandes — «Liberar espacio»: los mensajes que más ocupan en todo el buzón, de mayor a menor,
 * con su carpeta y tamaño. La persona marca y borra (a la papelera no: se eliminan) o abre el mensaje.
 * Se abre desde el Drive (/webmail/?vista=grandes) o desde el menú. API: GET /api/mail/grandes,
 * POST /api/mail/bulk-action/{carpeta} {uids, action: "delete"}.
 */
import { useCallback, useEffect, useState } from 'react';
import { api } from '../../api/client';
import { useMailStore } from '../../store/mailStore';

interface Grande { folder: string; uid: number; size: number; subject: string; from: string; date: string | null }

function humano(b: number): string {
  if (b >= 1073741824) return (b / 1073741824).toFixed(2) + ' GB';
  if (b >= 1048576) return (b / 1048576).toFixed(1) + ' MB';
  return Math.round(b / 1024) + ' KB';
}

const CARPETAS: Record<string, string> = { INBOX: 'Bandeja de entrada', Sent: 'Enviados', Drafts: 'Borradores', Junk: 'Correo no deseado', Trash: 'Papelera', Archive: 'Archivo' };

export function CorreosGrandes({ onCerrar }: { onCerrar: () => void }) {
  const [lista, setLista] = useState<Grande[]>([]);
  const [total, setTotal] = useState(0);
  const [cargando, setCargando] = useState(true);
  const [marcados, setMarcados] = useState<Set<string>>(new Set());
  const [msg, setMsg] = useState('');
  const [cuota, setCuota] = useState<{ usado: number; limite: number } | null>(null);

  const cargar = useCallback(async () => {
    setCargando(true); setMsg('');
    try {
      const r = await api.get<{ mensajes: Grande[]; total_bytes: number }>('/mail/grandes?limit=60');
      setLista(r.mensajes); setTotal(r.total_bytes); setMarcados(new Set());
    } catch (e: unknown) { setMsg(e instanceof Error ? e.message : 'No se pudo cargar'); }
    finally { setCargando(false); }
    try {
      const s = await api.get<{ storage_used_mb: number; storage_limit_mb: number }>('/mail/stats');
      setCuota({ usado: s.storage_used_mb, limite: s.storage_limit_mb });
    } catch { /* sin cuota: se omite la cabecera */ }
  }, []);
  useEffect(() => { cargar(); }, [cargar]);

  const clave = (m: Grande) => `${m.folder}:${m.uid}`;
  const alternar = (m: Grande) => setMarcados(prev => { const n = new Set(prev); const k = clave(m); if (n.has(k)) n.delete(k); else n.add(k); return n; });

  const borrar = async () => {
    if (!marcados.size) return;
    const bytes = lista.filter(m => marcados.has(clave(m))).reduce((a, m) => a + m.size, 0);
    if (!window.confirm(`¿Eliminar ${marcados.size} mensaje(s) (${humano(bytes)})? Esta acción no se puede deshacer.`)) return;
    setMsg('');
    try {
      const porCarpeta: Record<string, number[]> = {};
      lista.filter(m => marcados.has(clave(m))).forEach(m => { (porCarpeta[m.folder] ||= []).push(m.uid); });
      for (const [carpeta, uids] of Object.entries(porCarpeta)) {
        await api.post(`/mail/bulk-action/${encodeURIComponent(carpeta)}`, { uids, action: 'delete' });
      }
      setMsg(`Eliminados ${marcados.size} mensajes (${humano(bytes)} liberados).`);
      await cargar();
    } catch (e: unknown) { setMsg(e instanceof Error ? e.message : 'No se pudo eliminar'); }
  };

  const abrir = async (m: Grande) => {
    try {
      const st = useMailStore.getState();
      if (m.folder !== st.currentFolder) st.setCurrentFolder(m.folder);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any -- mensaje completo tal como llega de la API
      const msg = await api.get<any>(`/mail/message/${encodeURIComponent(m.folder)}/${m.uid}`);
      if (msg) useMailStore.getState().setSelectedMessage(msg);
      onCerrar();
    } catch { setMsg('No se pudo abrir el mensaje'); }
  };

  const seleccion = lista.filter(m => marcados.has(clave(m)));
  return (
    <div className="flex flex-col h-full bg-white">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#edebe9]">
        <div>
          <h2 className="text-base font-semibold text-[#323130]">Liberar espacio: los correos más grandes</h2>
          <p className="text-xs text-[#605e5c]">
            {cuota && cuota.limite > 0 ? `Tu correo usa ${(cuota.usado / 1024).toFixed(2)} GB de ${(cuota.limite / 1024).toFixed(1)} GB. ` : ''}
            Los {lista.length} mensajes de abajo suman {humano(total)}. Marca los que ya no necesites y elimínalos, o ábrelos para revisarlos.
          </p>
        </div>
        <button onClick={onCerrar} className="text-[#605e5c] hover:text-[#323130] text-xl" title="Cerrar">×</button>
      </div>
      <div className="flex items-center gap-3 px-4 py-2 border-b border-[#f3f2f1] text-sm">
        <button onClick={borrar} disabled={!marcados.size}
          className="px-3 py-1.5 rounded bg-[#a4262c] text-white text-xs font-medium disabled:opacity-40 hover:bg-[#8e2026]">
          Eliminar {marcados.size ? `${marcados.size} (${humano(seleccion.reduce((a, m) => a + m.size, 0))})` : ''}
        </button>
        <button onClick={() => setMarcados(new Set(lista.map(clave)))} className="text-xs text-[#0078d4] hover:underline">Marcar todos</button>
        <button onClick={() => setMarcados(new Set())} className="text-xs text-[#0078d4] hover:underline">Ninguno</button>
        {msg && <span className="text-xs text-[#605e5c]">{msg}</span>}
      </div>
      <div className="flex-1 overflow-auto">
        {cargando ? <div className="p-6 text-sm text-[#605e5c]">Midiendo el buzón…</div> : (
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-[#faf9f8] text-[#605e5c] text-xs">
              <tr><th className="w-8"></th><th className="text-right px-2 py-1 w-24">Tamaño</th><th className="text-left px-2 py-1">Asunto</th><th className="text-left px-2 py-1 w-56">De</th><th className="text-left px-2 py-1 w-36">Carpeta</th><th className="text-left px-2 py-1 w-28">Fecha</th></tr>
            </thead>
            <tbody>
              {lista.map(m => (
                <tr key={clave(m)} className={`border-b border-[#f3f2f1] hover:bg-[#f3f2f1] ${marcados.has(clave(m)) ? 'bg-[#eff6fc]' : ''}`}>
                  <td className="text-center"><input type="checkbox" checked={marcados.has(clave(m))} onChange={() => alternar(m)} /></td>
                  <td className="text-right px-2 py-1 font-mono text-[#323130]">{humano(m.size)}</td>
                  <td className="px-2 py-1 truncate max-w-[28rem]"><button onClick={() => abrir(m)} className="text-left hover:underline text-[#323130]" title="Abrir el mensaje">{m.subject || '(sin asunto)'}</button></td>
                  <td className="px-2 py-1 truncate text-[#605e5c]">{m.from}</td>
                  <td className="px-2 py-1 text-[#605e5c]">{CARPETAS[m.folder] || m.folder}</td>
                  <td className="px-2 py-1 text-[#605e5c]">{m.date ? new Date(m.date).toLocaleDateString('es-EC') : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
