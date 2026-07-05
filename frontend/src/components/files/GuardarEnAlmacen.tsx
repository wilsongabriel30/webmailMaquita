import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { showToast } from '../common/Toast';

/* Botón "Guardar en Archivos" para los adjuntos del correo.
   Descarga el adjunto con la sesión y lo sube al Almacén en la carpeta que
   el usuario elija (selector navegable). Autocontenido: cada botón maneja
   su propio modal, sin tocar el estado del visor de mensajes. */

interface Props {
  folder: string;
  uid: number;
  att: { part_number: string; filename: string; size?: number };
}

interface Carpeta { nombre: string; ruta: string; }

export function BotonGuardarEnAlmacen({ folder, uid, att }: Props) {
  const [abierto, setAbierto] = useState(false);
  const [carpeta, setCarpeta] = useState('/');
  const [subcarpetas, setSubcarpetas] = useState<Carpeta[]>([]);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    if (!abierto) return;
    api.get<{ carpetas: Carpeta[] }>(`/almacen/archivos?ruta=${encodeURIComponent(carpeta)}`)
      .then(r => setSubcarpetas(r.carpetas || []))
      .catch(() => setSubcarpetas([]));
  }, [abierto, carpeta]);

  const guardar = async () => {
    setGuardando(true);
    try {
      const res = await fetch(
        `/api/mail/attachment/${encodeURIComponent(folder)}/${uid}/${att.part_number}/${encodeURIComponent(att.filename)}`,
        { credentials: 'include' });
      if (!res.ok) throw new Error();
      const blob = await res.blob();
      const fd = new FormData();
      fd.append('carpeta', carpeta);
      fd.append('archivo', new File([blob], att.filename, { type: blob.type || 'application/octet-stream' }));
      const up = await fetch('/api/almacen/archivos', { method: 'POST', credentials: 'include', body: fd });
      if (!up.ok) throw new Error();
      showToast(`"${att.filename}" guardado en Archivos (${carpeta === '/' ? 'Mis archivos' : carpeta})`);
      setAbierto(false);
    } catch {
      showToast('No se pudo guardar el adjunto en Archivos');
    } finally {
      setGuardando(false);
    }
  };

  const migas = carpeta.split('/').filter(Boolean);

  return (
    <>
      <button
        onClick={e => { e.stopPropagation(); setCarpeta('/'); setAbierto(true); }}
        title="Guardar este adjunto en tu nube (Archivos)"
        style={{
          display: 'inline-flex', alignItems: 'center', padding: '4px 6px',
          border: '1px solid #d2d0ce', borderRadius: 4, background: '#faf9f8',
          cursor: 'pointer', fontSize: 12, lineHeight: 1,
        }}>
        ☁️
      </button>
      {abierto && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4"
          onClick={() => setAbierto(false)}>
          <div className="bg-white dark:bg-[#252423] rounded-lg shadow-xl w-full max-w-md max-h-[70vh] flex flex-col"
            onClick={e => e.stopPropagation()}>
            <div className="px-4 py-3 border-b border-[#edebe9] dark:border-[#3b3a39]">
              <div className="font-semibold text-[#323130] dark:text-[#e0e0e0]">☁️ Guardar en Archivos</div>
              <div className="text-xs text-[#605e5c] dark:text-[#a19f9d] truncate">{att.filename}</div>
            </div>
            <div className="px-4 py-2 flex items-center gap-1 text-sm flex-wrap border-b border-[#f3f2f1] dark:border-[#3b3a39]">
              <button onClick={() => setCarpeta('/')} className="text-[#106ebe] hover:underline font-semibold">Mis archivos</button>
              {migas.map((parte, i, arr) => (
                <span key={i} className="flex items-center gap-1 text-[#605e5c] dark:text-[#a19f9d]">
                  <span>›</span>
                  <button onClick={() => setCarpeta('/' + arr.slice(0, i + 1).join('/'))} className="hover:underline">{parte}</button>
                </span>
              ))}
            </div>
            <div className="flex-1 overflow-y-auto p-2 min-h-[140px]">
              {subcarpetas.length === 0 ? (
                <div className="p-6 text-center text-sm text-[#605e5c] dark:text-[#a19f9d]">Sin subcarpetas aquí</div>
              ) : subcarpetas.map(c => (
                <button key={c.ruta} onClick={() => setCarpeta(c.ruta)}
                  className="block w-full text-left px-3 py-2 rounded text-sm text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39]">
                  📁 {c.nombre}
                </button>
              ))}
            </div>
            <div className="px-4 py-2 border-t border-[#edebe9] dark:border-[#3b3a39] flex justify-between items-center">
              <span className="text-xs text-[#605e5c] dark:text-[#a19f9d] truncate">Destino: {carpeta}</span>
              <div className="flex gap-2">
                <button onClick={() => setAbierto(false)}
                  className="px-3 py-1.5 rounded text-sm text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39]">Cancelar</button>
                <button onClick={guardar} disabled={guardando}
                  className="px-3 py-1.5 rounded text-sm font-semibold bg-[#0078d4] text-white hover:bg-[#106ebe] disabled:opacity-50">
                  {guardando ? 'Guardando…' : 'Guardar aquí'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
