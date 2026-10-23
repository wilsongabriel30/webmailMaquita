import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../../api/client';
import { showToast } from '../common/Toast';
import { ROL_ETIQUETA, type Miembro, type Unidad, type UsuarioDir } from './tipos';

/* Miembros de una unidad de equipo (sacado de FilesView.tsx). */

export function MiembrosModal({ unidad, onCerrar }: { unidad: Unidad; onCerrar: () => void }) {
  const [miembros, setMiembros] = useState<Miembro[] | null>(null);
  const [buscar, setBuscar] = useState('');
  const [encontrados, setEncontrados] = useState<UsuarioDir[]>([]);
  const [rol, setRol] = useState('editor');
  const cerrar = useRef(onCerrar);
  useEffect(() => { cerrar.current = onCerrar; }, [onCerrar]);

  const cargarMiembros = useCallback(() => {
    api.get<{ miembros: Miembro[] }>(`/almacen/unidades/${unidad.id}/miembros`)
      .then(r => setMiembros(r.miembros || []))
      .catch(() => { showToast('No se pudieron cargar los miembros'); cerrar.current(); });
  }, [unidad.id]);

  useEffect(() => { cargarMiembros(); }, [cargarMiembros]);

  const buscarParaUnidad = (q: string) => {
    setBuscar(q);
    if (q.trim().length < 2) { setEncontrados([]); return; }
    api.get<{ usuarios: UsuarioDir[] }>(`/almacen/usuarios/buscar?q=${encodeURIComponent(q.trim())}`)
      .then(r => setEncontrados((r.usuarios || []).slice(0, 6)))
      .catch(() => {});
  };

  const agregarMiembro = async (u: UsuarioDir) => {
    if (!u.usuario_id) { showToast('Ese usuario no está en el directorio central'); return; }
    try {
      await api.post(`/almacen/unidades/${unidad.id}/miembros`, { usuario_id: u.usuario_id, rol });
      showToast(`${u.nombre} agregado como ${ROL_ETIQUETA[rol] || rol}`);
      setBuscar(''); setEncontrados([]);
      cargarMiembros();
    } catch { showToast('No se pudo agregar (solo el administrador de la unidad puede)'); }
  };

  const quitarMiembro = async (m: Miembro) => {
    if (!confirm(`¿Quitar a ${m.nombre} de "${unidad.nombre}"?`)) return;
    try {
      await api.del(`/almacen/unidades/${unidad.id}/miembros/${m.usuario_id}`);
      cargarMiembros();
    } catch { showToast('No se pudo quitar'); }
  };

  if (miembros === null) return null;
  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={onCerrar}>
      <div className="bg-white dark:bg-[#252423] rounded-lg shadow-xl w-full max-w-md max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="px-4 py-3 border-b border-[#edebe9] dark:border-[#3b3a39]">
          <div className="font-semibold text-[#323130] dark:text-[#e0e0e0]">👥 Miembros de la unidad</div>
          <div className="text-xs text-[#605e5c] dark:text-[#a19f9d] truncate">{unidad.nombre}</div>
        </div>
        <div className="p-4 border-b border-[#f3f2f1] dark:border-[#3b3a39] space-y-2">
          <div className="text-xs font-semibold text-[#323130] dark:text-[#e0e0e0]">Agregar persona</div>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <input value={buscar}
                onChange={e => buscarParaUnidad(e.target.value)}
                placeholder="Buscar por nombre o usuario…"
                className="w-full px-2 py-1.5 rounded border border-[#8a8886] text-sm bg-white dark:bg-[#1b1a19] text-[#323130] dark:text-[#e0e0e0]" />
              {encontrados.length > 0 && (
                <div className="absolute z-10 left-0 right-0 mt-1 bg-white dark:bg-[#252423] border border-[#edebe9] dark:border-[#3b3a39] rounded shadow-lg max-h-40 overflow-y-auto">
                  {encontrados.map(u => (
                    <button key={u.id} onClick={() => agregarMiembro(u)}
                      title={`Agregar como ${ROL_ETIQUETA[rol]}`}
                      className="block w-full text-left px-3 py-1.5 text-sm text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39]">
                      {u.nombre} <span className="text-xs text-[#a19f9d]">{u.email || ''}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <select value={rol}
              onChange={e => setRol(e.target.value)}
              title="Administrador: gestiona miembros. Editor: sube y edita. Lector: solo ve y descarga."
              className="px-2 py-1 rounded border border-[#8a8886] text-sm bg-white dark:bg-[#1b1a19] text-[#323130] dark:text-[#e0e0e0]">
              <option value="manager">Administrador</option>
              <option value="editor">Editor</option>
              <option value="viewer">Lector</option>
            </select>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {miembros.map(m => (
            <div key={m.usuario_id} className="flex items-center gap-2 px-3 py-2 rounded hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39]">
              <div className="flex-1 min-w-0">
                <div className="text-sm text-[#323130] dark:text-[#e0e0e0] truncate">{m.nombre}</div>
                <div className="text-[10px] text-[#a19f9d]">{m.username} · {ROL_ETIQUETA[m.rol] || m.rol}</div>
              </div>
              <button onClick={() => quitarMiembro(m)} title="Quitar de la unidad"
                className="px-2 py-1 rounded text-xs text-[#d13438] hover:bg-[#fde7e9]">Quitar</button>
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
