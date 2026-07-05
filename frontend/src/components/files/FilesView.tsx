import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../../api/client';
import { showToast } from '../common/Toast';

/* Archivos (Almacén Maquita) — nube personal integrada al webmail.
   Consume /api/almacen (contrato en almacen/docs/CONTRATO-API.md).
   La sesión es la misma cookie del webmail: no hay segundo login.
   Dos vistas: cuadrícula estilo Drive (default) y lista tipo explorador. */

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
  const [modo, setModo] = useState<'cuadricula' | 'lista'>(
    () => (localStorage.getItem('almacen_modo_vista') as 'cuadricula' | 'lista') || 'cuadricula');
  const [items, setItems] = useState<Item[]>([]);
  const [cargando, setCargando] = useState(false);
  const [subiendo, setSubiendo] = useState(false);
  const [cuota, setCuota] = useState<Cuota | null>(null);
  const [menu, setMenu] = useState<{ item: Item; x: number; y: number } | null>(null);
  const inputSubir = useRef<HTMLInputElement>(null);

  const cambiarModo = (m: 'cuadricula' | 'lista') => {
    setModo(m);
    localStorage.setItem('almacen_modo_vista', m);
  };

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
  useEffect(() => {
    const cerrar = () => setMenu(null);
    window.addEventListener('click', cerrar);
    return () => window.removeEventListener('click', cerrar);
  }, []);

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

  const abrirMenu = (e: React.MouseEvent, item: Item) => {
    e.preventDefault();
    e.stopPropagation();
    setMenu({ item, x: Math.min(e.clientX, window.innerWidth - 200), y: Math.min(e.clientY, window.innerHeight - 220) });
  };

  const migas = ruta.split('/').filter(Boolean);
  const botonModo = 'px-2 py-1.5 rounded text-sm';

  const accionesDe = (item: Item) => vista === 'archivos' ? ([
    ...(!item.es_carpeta && item.es_editable ? [{ texto: '✏️ Editar en línea', fn: () => abrir(item) }] : []),
    ...(!item.es_carpeta ? [{ texto: '⬇️ Descargar', fn: () => window.open(`/api/almacen/archivos/descargar?ruta=${encodeURIComponent(item.ruta)}`) }] : []),
    { texto: '✍️ Renombrar', fn: () => renombrar(item) },
    { texto: '🗑️ Eliminar', fn: () => eliminar(item) },
  ]) : ([
    { texto: '♻️ Restaurar', fn: () => restaurar(item) },
    { texto: '🗑️ Eliminar definitivo', fn: () => eliminarDefinitivo(item) },
  ]);

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
        {/* Selector cuadrícula / lista */}
        <div className="flex rounded border border-[#8a8886] overflow-hidden" role="group">
          <button onClick={() => cambiarModo('cuadricula')} title="Vista de cuadrícula (estilo Drive)"
            className={`${botonModo} ${modo === 'cuadricula' ? 'bg-[#deecf9] text-[#106ebe] dark:bg-[#004578] dark:text-white' : 'text-[#323130] dark:text-[#e0e0e0]'}`}>▦</button>
          <button onClick={() => cambiarModo('lista')} title="Vista de lista (estilo explorador)"
            className={`${botonModo} ${modo === 'lista' ? 'bg-[#deecf9] text-[#106ebe] dark:bg-[#004578] dark:text-white' : 'text-[#323130] dark:text-[#e0e0e0]'}`}>☰</button>
        </div>
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

      {/* Contenido */}
      <div className="flex-1 overflow-y-auto">
        {cargando ? (
          <div className="p-8 text-center text-[#605e5c] dark:text-[#a19f9d]">Cargando…</div>
        ) : items.length === 0 ? (
          <div className="p-12 text-center text-[#605e5c] dark:text-[#a19f9d]">
            {vista === 'papelera' ? 'La papelera está vacía' : 'Esta carpeta está vacía — usa "Subir" para empezar'}
          </div>
        ) : modo === 'cuadricula' ? (
          <div className="grid gap-3 p-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))' }}>
            {items.map(item => (
              <div key={item.id || item.ruta}
                onClick={() => item.es_carpeta && vista === 'archivos' ? abrir(item) : undefined}
                onDoubleClick={() => abrir(item)}
                onContextMenu={e => abrirMenu(e, item)}
                title={`${item.nombre}${item.es_carpeta ? '' : ` — ${item.tamano_humano}`}\nClic derecho: opciones${item.es_editable ? ' · Doble clic: editar en línea' : item.es_carpeta ? '' : ' · Doble clic: ver'}`}
                className="relative rounded-lg border border-[#edebe9] dark:border-[#3b3a39] p-3 cursor-pointer select-none hover:shadow-md hover:border-[#0078d4] dark:hover:border-[#2899f5] transition-all group bg-white dark:bg-[#252423]">
                <button onClick={e => abrirMenu(e, item)}
                  title="Opciones"
                  className="absolute top-1 right-1 w-7 h-7 rounded-full text-[#605e5c] dark:text-[#a19f9d] opacity-0 group-hover:opacity-100 hover:bg-[#edebe9] dark:hover:bg-[#3b3a39] text-lg leading-none">⋯</button>
                <div className="text-4xl text-center mb-2">{iconoDe(item)}</div>
                <div className="text-xs text-center text-[#323130] dark:text-[#e0e0e0] break-words leading-tight"
                  style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                  {item.nombre}
                </div>
                <div className="text-[10px] text-center text-[#a19f9d] mt-1">
                  {item.es_carpeta ? fechaCorta(item.eliminado_en || item.modificado_at) : item.tamano_humano}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-[#605e5c] dark:text-[#a19f9d] border-b border-[#edebe9] dark:border-[#3b3a39]">
                <th className="px-4 py-2 font-semibold">Nombre</th>
                <th className="px-2 py-2 font-semibold w-24">Tamaño</th>
                <th className="px-2 py-2 font-semibold w-36 hidden sm:table-cell">{vista === 'papelera' ? 'Eliminado' : 'Modificado'}</th>
                <th className="px-2 py-2 w-10"></th>
              </tr>
            </thead>
            <tbody>
              {items.map(item => (
                <tr key={item.id || item.ruta}
                  onContextMenu={e => abrirMenu(e, item)}
                  className="border-b border-[#f3f2f1] dark:border-[#292827] hover:bg-[#f3f2f1] dark:hover:bg-[#292827] group">
                  <td className="px-4 py-2 cursor-pointer" onDoubleClick={() => abrir(item)} onClick={() => item.es_carpeta && vista === 'archivos' ? abrir(item) : undefined}
                    title={item.es_carpeta ? 'Abrir la carpeta' : (item.es_editable ? 'Doble clic: editar en línea' : 'Doble clic: ver/descargar')}>
                    <span className="mr-2">{iconoDe(item)}</span>
                    <span className="text-[#323130] dark:text-[#e0e0e0]">{item.nombre}</span>
                  </td>
                  <td className="px-2 py-2 text-[#605e5c] dark:text-[#a19f9d]">{item.tamano_humano}</td>
                  <td className="px-2 py-2 text-[#605e5c] dark:text-[#a19f9d] hidden sm:table-cell">{fechaCorta(item.eliminado_en || item.modificado_at)}</td>
                  <td className="px-2 py-2 text-right">
                    <button onClick={e => abrirMenu(e, item)} title="Opciones"
                      className="w-7 h-7 rounded-full text-[#605e5c] dark:text-[#a19f9d] opacity-0 group-hover:opacity-100 hover:bg-[#edebe9] dark:hover:bg-[#3b3a39] text-lg leading-none">⋯</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Menú contextual (clic derecho o botón ⋯) */}
      {menu && (
        <div className="fixed z-50 bg-white dark:bg-[#252423] border border-[#edebe9] dark:border-[#3b3a39] rounded-lg shadow-lg py-1 min-w-[180px]"
          style={{ left: menu.x, top: menu.y }} onClick={e => e.stopPropagation()}>
          <div className="px-3 py-1.5 text-xs text-[#a19f9d] border-b border-[#f3f2f1] dark:border-[#3b3a39] truncate max-w-[220px]">{menu.item.nombre}</div>
          {accionesDe(menu.item).map((a, i) => (
            <button key={i} onClick={() => { setMenu(null); a.fn(); }}
              className="block w-full text-left px-3 py-1.5 text-sm text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39]">
              {a.texto}
            </button>
          ))}
        </div>
      )}

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
