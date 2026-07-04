import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../../api/client';
import { showToast } from '../common/Toast';

/* Archivos (Almacén Maquita) — nube personal integrada al webmail.
   Consume /api/almacen (contrato en almacen/docs/CONTRATO-API.md).
   La sesión es la misma cookie del webmail: no hay segundo login. */

interface Item {
  id: string;
  nombre: string;
  ruta: string;
  es_carpeta: boolean;
  extension?: string;
  tamano_humano: string;
  modificado_at?: string;
  es_editable?: boolean;
  eliminado_en?: string;
}

interface Cuota {
  usado_humano: string;
  total_humano: string;
  porcentaje: number;
}

const ICONOS: Record<string, string> = {
  docx: '📄', doc: '📄', odt: '📄', xlsx: '📊', xls: '📊', ods: '📊', csv: '📊',
  pptx: '📽️', ppt: '📽️', odp: '📽️', pdf: '📕', txt: '📃', md: '📃',
  jpg: '🖼️', jpeg: '🖼️', png: '🖼️', gif: '🖼️', svg: '🖼️', webp: '🖼️',
  mp4: '🎬', avi: '🎬', mkv: '🎬', mp3: '🎵', wav: '🎵', zip: '🗜️', rar: '🗜️', '7z': '🗜️',
};

function iconoDe(item: Item): string {
  if (item.es_carpeta) return '📁';
  return ICONOS[(item.extension || '').toLowerCase()] || '📎';
}

function fechaCorta(iso?: string): string {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString('es-EC', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
  } catch { return ''; }
}

export function FilesView() {
  const [ruta, setRuta] = useState('/');
  const [vista, setVista] = useState<'archivos' | 'papelera'>('archivos');
  const [items, setItems] = useState<Item[]>([]);
  const [cargando, setCargando] = useState(false);
  const [subiendo, setSubiendo] = useState(false);
  const [cuota, setCuota] = useState<Cuota | null>(null);
  const inputSubir = useRef<HTMLInputElement>(null);

  const cargar = useCallback(async (r: string, v: 'archivos' | 'papelera' = 'archivos') => {
    setCargando(true);
    try {
      if (v === 'papelera') {
        const res = await api.get<{ carpetas: Item[]; archivos: Item[] }>('/almacen/papelera');
        setItems([...(res.carpetas || []), ...(res.archivos || [])]);
      } else {
        const res = await api.get<{ carpetas: Item[]; archivos: Item[] }>(`/almacen/archivos?ruta=${encodeURIComponent(r)}`);
        setItems([...(res.carpetas || []), ...(res.archivos || [])]);
      }
    } catch {
      showToast('No se pudieron cargar los archivos');
      setItems([]);
    } finally {
      setCargando(false);
    }
  }, []);

  const cargarCuota = useCallback(() => {
    api.get<Cuota>('/almacen/cuota').then(setCuota).catch(() => {});
  }, []);

  useEffect(() => { cargar(ruta, vista); }, [ruta, vista, cargar]);
  useEffect(() => { cargarCuota(); }, [cargarCuota]);

  const refrescar = () => { cargar(ruta, vista); cargarCuota(); };

  const abrir = (item: Item) => {
    if (vista === 'papelera') return;
    if (item.es_carpeta) { setRuta(item.ruta); return; }
    if (item.es_editable) {
      window.open(`/archivos-almacen/editar?ruta=${encodeURIComponent(item.ruta)}`, '_blank');
    } else {
      window.open(`/api/almacen/archivos/ver?ruta=${encodeURIComponent(item.ruta)}`, '_blank');
    }
  };

  const subir = async (archivos: FileList | null) => {
    if (!archivos || archivos.length === 0) return;
    setSubiendo(true);
    const fd = new FormData();
    fd.append('carpeta', ruta);
    Array.from(archivos).forEach(a => fd.append('archivo', a));
    try {
      const res = await fetch('/api/almacen/archivos', { method: 'POST', credentials: 'include', body: fd });
      if (!res.ok) throw new Error();
      const d = await res.json();
      showToast(`${d.total} archivo${d.total > 1 ? 's' : ''} subido${d.total > 1 ? 's' : ''}`);
      refrescar();
    } catch {
      showToast('Error al subir');
    } finally {
      setSubiendo(false);
      if (inputSubir.current) inputSubir.current.value = '';
    }
  };

  const nuevaCarpeta = async () => {
    const nombre = prompt('Nombre de la carpeta:');
    if (!nombre?.trim()) return;
    try {
      await api.post('/almacen/carpetas', { ruta, nombre: nombre.trim() });
      showToast(`Carpeta "${nombre.trim()}" creada`);
      refrescar();
    } catch { showToast('No se pudo crear la carpeta'); }
  };

  const renombrar = async (item: Item) => {
    const nuevo = prompt('Nuevo nombre:', item.nombre);
    if (!nuevo?.trim() || nuevo.trim() === item.nombre) return;
    try {
      await api.post('/almacen/archivos/renombrar', { ruta: item.ruta, nuevo_nombre: nuevo.trim() });
      refrescar();
    } catch { showToast('No se pudo renombrar'); }
  };

  const eliminar = async (item: Item) => {
    if (!confirm(`¿Enviar "${item.nombre}" a la papelera?`)) return;
    try {
      await api.del(`/almacen/archivos?ruta=${encodeURIComponent(item.ruta)}`);
      showToast('Enviado a la papelera');
      refrescar();
    } catch { showToast('No se pudo eliminar'); }
  };

  const restaurar = async (item: Item) => {
    try {
      await api.post('/almacen/papelera/restaurar', { ruta: item.ruta });
      showToast('Restaurado');
      refrescar();
    } catch { showToast('No se pudo restaurar'); }
  };

  const eliminarDefinitivo = async (item: Item) => {
    if (!confirm(`¿Eliminar DEFINITIVAMENTE "${item.nombre}"?`)) return;
    try {
      await api.post('/almacen/papelera/eliminar', { ruta: item.ruta });
      refrescar();
    } catch { showToast('No se pudo eliminar'); }
  };

  const vaciarPapelera = async () => {
    if (!confirm('¿Vaciar toda la papelera?')) return;
    try {
      await api.post('/almacen/papelera/vaciar', {});
      showToast('Papelera vaciada');
      refrescar();
    } catch { showToast('No se pudo vaciar'); }
  };

  const migas = ruta.split('/').filter(Boolean);

  return (
    <div className="flex flex-col h-full bg-white dark:bg-[#1b1a19]">
      {/* Barra superior */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-[#edebe9] dark:border-[#3b3a39] flex-wrap">
        <button onClick={() => setVista('archivos')}
          title="Ver mis archivos"
          className={`px-3 py-1.5 rounded text-sm font-semibold ${vista === 'archivos' ? 'bg-[#deecf9] text-[#106ebe] dark:bg-[#004578] dark:text-white' : 'text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#323130]'}`}>
          📁 Mis archivos
        </button>
        <button onClick={() => setVista('papelera')}
          title="Ver la papelera (lo eliminado se puede restaurar)"
          className={`px-3 py-1.5 rounded text-sm font-semibold ${vista === 'papelera' ? 'bg-[#deecf9] text-[#106ebe] dark:bg-[#004578] dark:text-white' : 'text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#323130]'}`}>
          🗑️ Papelera
        </button>
        <div className="flex-1" />
        {vista === 'archivos' ? (
          <>
            <button onClick={() => inputSubir.current?.click()} disabled={subiendo}
              title="Subir uno o varios archivos a la carpeta actual"
              className="px-3 py-1.5 rounded text-sm font-semibold bg-[#0078d4] text-white hover:bg-[#106ebe] disabled:opacity-50">
              {subiendo ? 'Subiendo…' : '⬆️ Subir'}
            </button>
            <input ref={inputSubir} type="file" multiple className="hidden" onChange={e => subir(e.target.files)} />
            <button onClick={nuevaCarpeta}
              title="Crear una carpeta en la ubicación actual"
              className="px-3 py-1.5 rounded text-sm font-semibold border border-[#8a8886] text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#323130]">
              📁 Nueva carpeta
            </button>
          </>
        ) : (
          <button onClick={vaciarPapelera}
            title="Vaciar la papelera (los administradores aún pueden recuperar por un tiempo)"
            className="px-3 py-1.5 rounded text-sm font-semibold border border-[#d13438] text-[#d13438] hover:bg-[#fde7e9]">
            Vaciar papelera
          </button>
        )}
        <button onClick={refrescar} title="Actualizar el listado"
          className="px-2 py-1.5 rounded text-sm text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#323130]">🔄</button>
      </div>

      {/* Migas de pan */}
      {vista === 'archivos' && (
        <div className="flex items-center gap-1 px-4 py-2 text-sm text-[#605e5c] dark:text-[#a19f9d] flex-wrap">
          <button onClick={() => setRuta('/')} className="hover:underline font-semibold text-[#106ebe]" title="Ir a la raíz de mis archivos">Mis archivos</button>
          {migas.map((parte, i) => (
            <span key={i} className="flex items-center gap-1">
              <span>›</span>
              <button onClick={() => setRuta('/' + migas.slice(0, i + 1).join('/'))} className="hover:underline" title={`Ir a ${parte}`}>{parte}</button>
            </span>
          ))}
        </div>
      )}

      {/* Listado */}
      <div className="flex-1 overflow-y-auto">
        {cargando ? (
          <div className="p-8 text-center text-[#605e5c] dark:text-[#a19f9d]">Cargando…</div>
        ) : items.length === 0 ? (
          <div className="p-12 text-center text-[#605e5c] dark:text-[#a19f9d]">
            {vista === 'papelera' ? 'La papelera está vacía' : 'Esta carpeta está vacía — usa "Subir" para empezar'}
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-[#605e5c] dark:text-[#a19f9d] border-b border-[#edebe9] dark:border-[#3b3a39]">
                <th className="px-4 py-2 font-semibold">Nombre</th>
                <th className="px-2 py-2 font-semibold w-24">Tamaño</th>
                <th className="px-2 py-2 font-semibold w-36 hidden sm:table-cell">{vista === 'papelera' ? 'Eliminado' : 'Modificado'}</th>
                <th className="px-2 py-2 w-44"></th>
              </tr>
            </thead>
            <tbody>
              {items.map(item => (
                <tr key={item.id || item.ruta}
                  className="border-b border-[#f3f2f1] dark:border-[#292827] hover:bg-[#f3f2f1] dark:hover:bg-[#292827] group">
                  <td className="px-4 py-2 cursor-pointer" onDoubleClick={() => abrir(item)} onClick={() => item.es_carpeta && vista === 'archivos' ? abrir(item) : undefined}
                    title={item.es_carpeta ? 'Abrir la carpeta' : (item.es_editable ? 'Doble clic: editar en línea' : 'Doble clic: ver/descargar')}>
                    <span className="mr-2">{iconoDe(item)}</span>
                    <span className="text-[#323130] dark:text-[#e0e0e0]">{item.nombre}</span>
                  </td>
                  <td className="px-2 py-2 text-[#605e5c] dark:text-[#a19f9d]">{item.tamano_humano}</td>
                  <td className="px-2 py-2 text-[#605e5c] dark:text-[#a19f9d] hidden sm:table-cell">{fechaCorta(item.eliminado_en || item.modificado_at)}</td>
                  <td className="px-2 py-2 text-right whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity">
                    {vista === 'archivos' ? (
                      <>
                        {!item.es_carpeta && item.es_editable && (
                          <button onClick={() => abrir(item)} title="Editar en línea (colaborativo)"
                            className="px-2 py-1 text-xs rounded text-[#106ebe] hover:bg-[#deecf9] dark:hover:bg-[#004578] font-semibold">Editar</button>
                        )}
                        {!item.es_carpeta && (
                          <button onClick={() => window.open(`/api/almacen/archivos/descargar?ruta=${encodeURIComponent(item.ruta)}`)}
                            title="Descargar el archivo"
                            className="px-2 py-1 text-xs rounded text-[#323130] dark:text-[#e0e0e0] hover:bg-[#edebe9] dark:hover:bg-[#3b3a39]">Descargar</button>
                        )}
                        <button onClick={() => renombrar(item)} title="Cambiar el nombre"
                          className="px-2 py-1 text-xs rounded text-[#323130] dark:text-[#e0e0e0] hover:bg-[#edebe9] dark:hover:bg-[#3b3a39]">Renombrar</button>
                        <button onClick={() => eliminar(item)} title="Enviar a la papelera"
                          className="px-2 py-1 text-xs rounded text-[#d13438] hover:bg-[#fde7e9]">Eliminar</button>
                      </>
                    ) : (
                      <>
                        <button onClick={() => restaurar(item)} title="Devolver a su ubicación original"
                          className="px-2 py-1 text-xs rounded text-[#106ebe] hover:bg-[#deecf9] font-semibold">Restaurar</button>
                        <button onClick={() => eliminarDefinitivo(item)} title="Eliminar definitivamente"
                          className="px-2 py-1 text-xs rounded text-[#d13438] hover:bg-[#fde7e9]">Eliminar</button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Cuota */}
      {cuota && (
        <div className="px-4 py-2 border-t border-[#edebe9] dark:border-[#3b3a39] text-xs text-[#605e5c] dark:text-[#a19f9d]"
          title="Espacio usado de tu almacenamiento personal">
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1.5 bg-[#edebe9] dark:bg-[#3b3a39] rounded overflow-hidden max-w-xs">
              <div className="h-full bg-[#0078d4]" style={{ width: `${Math.min(100, cuota.porcentaje)}%` }} />
            </div>
            <span>{cuota.usado_humano} de {cuota.total_humano} usados</span>
          </div>
        </div>
      )}
    </div>
  );
}
