import { useEffect, useRef, useState } from 'react';
import { api } from '../../api/client';
import { showToast } from '../common/Toast';
import type { Item, Version } from './tipos';
import { fechaCorta } from './utilidadesArchivos';

/* Historial de versiones de un archivo (sacado de FilesView.tsx). */

export function VersionesModal({ item, onCerrar, onRestaurada }: { item: Item; onCerrar: () => void; onRestaurada: () => void }) {
  const [lista, setLista] = useState<Version[] | null>(null);
  const cerrar = useRef(onCerrar);
  useEffect(() => { cerrar.current = onCerrar; }, [onCerrar]);

  useEffect(() => {
    api.get<{ versiones: Version[] }>(`/almacen/versiones/${encodeURIComponent(item.id)}`)
      .then(r => setLista(r.versiones || []))
      .catch(() => { showToast('No se pudo cargar el historial'); cerrar.current(); });
  }, [item.id]);

  const restaurarVersion = async (version: Version) => {
    if (!confirm(`¿Volver a la versión del ${fechaCorta(version.creado_en)}? La versión actual se conserva en el historial.`)) return;
    try {
      await api.post(`/almacen/versiones/${encodeURIComponent(item.id)}/restaurar`, { version_id: version.version_id });
      showToast('Versión restaurada');
      onRestaurada();
    } catch { showToast('No se pudo restaurar la versión'); }
  };

  if (lista === null) return null;
  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={onCerrar}>
      <div className="bg-white dark:bg-[#252423] rounded-lg shadow-xl w-full max-w-md max-h-[70vh] flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="px-4 py-3 border-b border-[#edebe9] dark:border-[#3b3a39]">
          <div className="font-semibold text-[#323130] dark:text-[#e0e0e0]">🕘 Historial de versiones</div>
          <div className="text-xs text-[#605e5c] dark:text-[#a19f9d] truncate">{item.nombre}</div>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {lista.length === 0 ? (
            <div className="p-6 text-center text-sm text-[#605e5c] dark:text-[#a19f9d]">
              Este archivo aún no tiene versiones anteriores.<br/>Cada vez que se edita o se sube de nuevo, la versión previa se guarda aquí.
            </div>
          ) : lista.map(v => (
            <div key={v.version_id} className="flex items-center gap-2 px-3 py-2 rounded hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39]">
              <div className="flex-1">
                <div className="text-sm text-[#323130] dark:text-[#e0e0e0]">{fechaCorta(v.creado_en)}</div>
                <div className="text-xs text-[#a19f9d]">{v.tamano_humano}{v.guardar_siempre ? ' · conservar siempre' : ''}</div>
              </div>
              <button onClick={() => restaurarVersion(v)}
                title="Vuelve a esta versión (la actual se conserva en el historial)"
                className="px-3 py-1 rounded text-xs font-semibold text-[#106ebe] hover:bg-[#deecf9] dark:hover:bg-[#004578]">Restaurar</button>
            </div>
          ))}
        </div>
        <div className="px-4 py-2 border-t border-[#edebe9] dark:border-[#3b3a39] text-right">
          <button onClick={onCerrar} className="px-3 py-1.5 rounded text-sm text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39]">Cerrar</button>
        </div>
      </div>
    </div>
  );
}
