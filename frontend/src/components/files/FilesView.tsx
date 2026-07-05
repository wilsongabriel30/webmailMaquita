import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../../api/client';
import { showToast } from '../common/Toast';
import { useMailStore } from '../../store/mailStore';

/* Archivos (Almacén Maquita) — nube personal integrada al webmail.
   Consume /api/almacen (contrato en almacen/docs/CONTRATO-API.md).
   - La ruta actual vive en la URL (?ruta=): el botón atrás del navegador
     retrocede ENTRE CARPETAS, y se puede compartir/refrescar el enlace.
   - Dos vistas (cuadrícula estilo Drive / lista) + buscador propio.
   - Menú contextual: editar, descargar, enviar por correo, mover, copiar,
     renombrar, historial de versiones, eliminar. */

interface Item {
  id: string;
  nombre: string;
  ruta: string;
  es_carpeta: boolean;
  extension?: string;
  tamano_humano: string;
  modificado_at?: string;
  es_editable?: boolean;
  es_favorito?: boolean;
  eliminado_en?: string;
}

interface Unidad {
  id: number;
  nombre: string;
  mi_rol: string;
  miembros: number;
  ruta: string;
}

interface Miembro { usuario_id: number; rol: string; nombre: string; username: string; }
interface Conmigo {
  id: number; nombre: string; extension?: string; tamano_bytes?: number;
  token: string; de: string; puede_editar: boolean; abre_en_linea: boolean;
  permite_descarga: boolean; requiere_clave: boolean; expira_en?: string; creado_en: string;
}
interface UsuarioDir { id: number | string; usuario_id?: number; nombre: string; email?: string; }

const ROL_ETIQUETA: Record<string, string> = { manager: 'Administrador', editor: 'Editor', viewer: 'Lector' };

interface Share {
  id: number;
  ruta: string;
  tipo: number;
  con_quien?: string;
  url?: string;
  creado_en?: string;
}

interface Cuota { usado_humano: string; total_humano: string; porcentaje: number; }
interface Version { version_id: string; tamano_humano: string; creado_en: string; guardar_siempre?: boolean; }

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

function carpetaDe(ruta: string): string {
  const i = ruta.lastIndexOf('/');
  return i <= 0 ? '/' : ruta.slice(0, i);
}

export function FilesView() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const ruta = params.get('ruta') || '/';
  const vistaParam = params.get('vista');
  const vista = (['papelera', 'favoritos', 'unidades', 'conmigo'].includes(vistaParam || '') ? vistaParam : 'archivos') as 'archivos' | 'papelera' | 'favoritos' | 'unidades' | 'conmigo';

  const [modo, setModo] = useState<'cuadricula' | 'lista'>(
    () => (localStorage.getItem('almacen_modo_vista') as 'cuadricula' | 'lista') || 'cuadricula');
  const [items, setItems] = useState<Item[]>([]);
  const [cargando, setCargando] = useState(false);
  const [subiendo, setSubiendo] = useState(false);
  const [cuota, setCuota] = useState<Cuota | null>(null);
  const [menu, setMenu] = useState<{ item: Item; x: number; y: number } | null>(null);
  const [busqueda, setBusqueda] = useState('');
  const [resultados, setResultados] = useState<Item[] | null>(null);
  const [versiones, setVersiones] = useState<{ item: Item; lista: Version[] } | null>(null);
  const [selector, setSelector] = useState<{ item: Item; accion: 'mover' | 'copiar'; carpeta: string; subcarpetas: Item[] } | null>(null);
  const [compartirModal, setCompartirModal] = useState<{ item: Item; shares: Share[]; creando: boolean } | null>(null);
  const [persona, setPersona] = useState({ correo: '', rol: 'lector' });
  const [sugerencias, setSugerencias] = useState<UsuarioDir[]>([]);
  const [unidades, setUnidades] = useState<Unidad[]>([]);
  const [conmigo, setConmigo] = useState<Conmigo[]>([]);
  const [miembrosModal, setMiembrosModal] = useState<{ unidad: Unidad; miembros: Miembro[]; buscar: string; encontrados: UsuarioDir[]; rol: string } | null>(null);
  const [opcionesEnlace, setOpcionesEnlace] = useState({ expira_dias: 0, clave: '', permite_descarga: true });
  const inputSubir = useRef<HTMLInputElement>(null);
  const timerBusqueda = useRef<ReturnType<typeof setTimeout>>(undefined);

  const irA = (nuevaRuta: string, nuevaVista: 'archivos' | 'papelera' | 'favoritos' | 'unidades' | 'conmigo' = 'archivos') => {
    const p: Record<string, string> = {};
    if (nuevaRuta !== '/') p.ruta = nuevaRuta;
    if (nuevaVista !== 'archivos') p.vista = nuevaVista;
    setParams(p);           // entra al historial → el botón atrás retrocede carpetas
    setBusqueda(''); setResultados(null);
  };

  const cambiarModo = (m: 'cuadricula' | 'lista') => {
    setModo(m);
    localStorage.setItem('almacen_modo_vista', m);
  };

  const cargar = useCallback(async (r: string, v: 'archivos' | 'papelera' | 'favoritos' | 'unidades' | 'conmigo') => {
    if (v === 'unidades') { setItems([]); setCargando(false); return; }
    if (v === 'conmigo') {
      setItems([]); setCargando(true);
      try {
        const res = await api.get<{ compartidos: Conmigo[] }>('/almacen/compartidos-conmigo');
        setConmigo(res.compartidos || []);
      } catch { setConmigo([]); }
      setCargando(false);
      return;
    }
    setCargando(true);
    try {
      if (v === 'papelera') {
        const res = await api.get<{ carpetas: Item[]; archivos: Item[] }>('/almacen/papelera');
        setItems([...(res.carpetas || []), ...(res.archivos || [])]);
      } else if (v === 'favoritos') {
        const res = await api.get<{ carpetas: Item[]; archivos: Item[] }>('/almacen/favoritos');
        setItems([...(res.carpetas || []), ...(res.archivos || [])].map(i => ({ ...i, es_favorito: true })));
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
    api.get<{ unidades: Unidad[] }>('/almacen/unidades').then(r => setUnidades(r.unidades || [])).catch(() => {});
  }, [vista]);
  useEffect(() => {
    const cerrar = () => setMenu(null);
    window.addEventListener('click', cerrar);
    return () => window.removeEventListener('click', cerrar);
  }, []);

  // Buscador (con retardo de tecleo; mínimo 2 letras)
  useEffect(() => {
    clearTimeout(timerBusqueda.current);
    if (busqueda.trim().length < 2) { setResultados(null); return; }
    timerBusqueda.current = setTimeout(() => {
      api.get<{ resultados: Item[] }>(`/almacen/buscar?q=${encodeURIComponent(busqueda.trim())}`)
        .then(r => setResultados(r.resultados || []))
        .catch(() => setResultados([]));
    }, 350);
    return () => clearTimeout(timerBusqueda.current);
  }, [busqueda]);

  const refrescar = () => { cargar(ruta, vista); cargarCuota(); };

  const abrir = (item: Item) => {
    if (vista === 'papelera') return;
    if (vista === 'favoritos' && item.es_carpeta) { irA(item.ruta); return; }
    if (item.es_carpeta) { irA(item.ruta); return; }
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

  const verVersiones = async (item: Item) => {
    try {
      const r = await api.get<{ versiones: Version[] }>(`/almacen/versiones/${encodeURIComponent(item.id)}`);
      setVersiones({ item, lista: r.versiones || [] });
    } catch { showToast('No se pudo cargar el historial'); }
  };

  const restaurarVersion = async (version: Version) => {
    if (!versiones) return;
    if (!confirm(`¿Volver a la versión del ${fechaCorta(version.creado_en)}? La versión actual se conserva en el historial.`)) return;
    try {
      await api.post(`/almacen/versiones/${encodeURIComponent(versiones.item.id)}/restaurar`, { version_id: version.version_id });
      showToast('Versión restaurada');
      setVersiones(null);
      refrescar();
    } catch { showToast('No se pudo restaurar la versión'); }
  };

  const abrirSelector = async (item: Item, accion: 'mover' | 'copiar', carpeta = '/') => {
    try {
      const res = await api.get<{ carpetas: Item[] }>(`/almacen/archivos?ruta=${encodeURIComponent(carpeta)}`);
      setSelector({ item, accion, carpeta, subcarpetas: (res.carpetas || []).filter(c => c.ruta !== item.ruta) });
    } catch { showToast('No se pudo abrir el selector'); }
  };

  const confirmarSelector = async () => {
    if (!selector) return;
    const destino = (selector.carpeta === '/' ? '' : selector.carpeta) + '/' + selector.item.nombre;
    if (destino === selector.item.ruta) { showToast('Ya está en esa carpeta'); return; }
    try {
      await api.post(`/almacen/archivos/${selector.accion}`, { origen: selector.item.ruta, destino });
      showToast(selector.accion === 'mover' ? 'Movido' : 'Copiado');
      setSelector(null);
      refrescar();
    } catch { showToast(`No se pudo ${selector.accion}`); }
  };

  const toggleFavorito = async (item: Item) => {
    try {
      const r = await api.post<{ es_favorito: boolean }>('/almacen/archivos/favorito', { ruta: item.ruta });
      showToast(r.es_favorito ? 'Agregado a favoritos ⭐' : 'Quitado de favoritos');
      refrescar();
    } catch { showToast('No se pudo cambiar el favorito'); }
  };

  const abrirCompartir = async (item: Item) => {
    setOpcionesEnlace({ expira_dias: 0, clave: '', permite_descarga: true });
    try {
      const r = await api.get<{ compartidos: Share[] }>('/almacen/compartidos');
      setCompartirModal({ item, shares: (r.compartidos || []).filter(c => c.ruta === item.ruta), creando: false });
    } catch { showToast('No se pudo abrir compartir'); }
  };

  const crearEnlace = async () => {
    if (!compartirModal) return;
    setCompartirModal({ ...compartirModal, creando: true });
    try {
      const r = await api.post<{ compartido: Share }>('/almacen/compartir', {
        ruta: compartirModal.item.ruta, tipo: 3, permisos: 1,
        expira_dias: opcionesEnlace.expira_dias || 0,
        clave: opcionesEnlace.clave.trim(),
        permite_descarga: opcionesEnlace.permite_descarga,
      });
      setCompartirModal(prev => prev ? { ...prev, shares: [r.compartido, ...prev.shares], creando: false } : prev);
      if (r.compartido.url) copiarEnlace(r.compartido.url, 'Enlace creado y copiado 🔗');
    } catch {
      showToast('No se pudo crear el enlace');
      setCompartirModal(prev => prev ? { ...prev, creando: false } : prev);
    }
  };

  useEffect(() => {
    const q = persona.correo.trim();
    if (q.length < 2 || q.includes('@')) { setSugerencias([]); return; }
    const t = setTimeout(() => {
      api.get<{ usuarios: UsuarioDir[] }>(`/almacen/usuarios/buscar?q=${encodeURIComponent(q)}`)
        .then(r => setSugerencias((r.usuarios || []).slice(0, 6)))
        .catch(() => setSugerencias([]));
    }, 300);
    return () => clearTimeout(t);
  }, [persona.correo]);

  const compartirConPersona = async () => {
    if (!compartirModal) return;
    const correo = persona.correo.trim().toLowerCase();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(correo)) { showToast('Escribe un correo válido'); return; }
    setCompartirModal({ ...compartirModal, creando: true });
    try {
      const r = await api.post<{ compartido: Share & { url?: string } }>('/almacen/compartir', {
        ruta: compartirModal.item.ruta, tipo: 3,
        permisos: persona.rol === 'editor' ? 3 : 1,
        email: correo, rol: persona.rol,
        permite_descarga: true,
      });
      setCompartirModal(prev => prev ? { ...prev, shares: [r.compartido, ...prev.shares], creando: false } : prev);
      setSugerencias([]);
      // Abre el redactor con el enlace listo para esa persona
      const url = r.compartido.url || '';
      useMailStore.getState().openCompose('new', {
        to: [correo], subject: `Te comparto: ${compartirModal.item.nombre}`,
        text_body: '', html_body: `<p>Hola,</p><p>Te comparto <b>${compartirModal.item.nombre}</b> desde mi nube:</p><p><a href="${url}">${url}</a></p>`,
      } as never);
      navigate('/');
    } catch {
      showToast('No se pudo compartir con esa persona');
      setCompartirModal(prev => prev ? { ...prev, creando: false } : prev);
    }
  };

  const nuevaUnidad = async () => {
    const nombre = prompt('Nombre de la unidad de equipo (ej: Contabilidad):');
    if (!nombre?.trim()) return;
    try {
      await api.post('/almacen/unidades', { nombre: nombre.trim() });
      showToast(`Unidad "${nombre.trim()}" creada`);
      api.get<{ unidades: Unidad[] }>('/almacen/unidades').then(r => setUnidades(r.unidades || []));
    } catch { showToast('No se pudo crear (solo administradores crean unidades)'); }
  };

  const abrirMiembros = async (unidad: Unidad) => {
    try {
      const r = await api.get<{ miembros: Miembro[] }>(`/almacen/unidades/${unidad.id}/miembros`);
      setMiembrosModal({ unidad, miembros: r.miembros || [], buscar: '', encontrados: [], rol: 'editor' });
    } catch { showToast('No se pudieron cargar los miembros'); }
  };

  const buscarParaUnidad = (q: string) => {
    setMiembrosModal(prev => prev ? { ...prev, buscar: q } : prev);
    if (q.trim().length < 2) { setMiembrosModal(prev => prev ? { ...prev, encontrados: [] } : prev); return; }
    api.get<{ usuarios: UsuarioDir[] }>(`/almacen/usuarios/buscar?q=${encodeURIComponent(q.trim())}`)
      .then(r => setMiembrosModal(prev => prev ? { ...prev, encontrados: (r.usuarios || []).slice(0, 6) } : prev))
      .catch(() => {});
  };

  const agregarMiembro = async (u: UsuarioDir) => {
    if (!miembrosModal) return;
    if (!u.usuario_id) { showToast('Ese usuario no está en el directorio central'); return; }
    try {
      await api.post(`/almacen/unidades/${miembrosModal.unidad.id}/miembros`, { usuario_id: u.usuario_id, rol: miembrosModal.rol });
      showToast(`${u.nombre} agregado como ${ROL_ETIQUETA[miembrosModal.rol] || miembrosModal.rol}`);
      abrirMiembros(miembrosModal.unidad);
    } catch { showToast('No se pudo agregar (solo el administrador de la unidad puede)'); }
  };

  const quitarMiembro = async (m: Miembro) => {
    if (!miembrosModal) return;
    if (!confirm(`¿Quitar a ${m.nombre} de "${miembrosModal.unidad.nombre}"?`)) return;
    try {
      await api.del(`/almacen/unidades/${miembrosModal.unidad.id}/miembros/${m.usuario_id}`);
      abrirMiembros(miembrosModal.unidad);
    } catch { showToast('No se pudo quitar'); }
  };

  const copiarEnlace = (url: string, mensaje = 'Enlace copiado') => {
    navigator.clipboard?.writeText(url).then(() => showToast(mensaje)).catch(() => prompt('Copia el enlace:', url));
  };

  const dejarDeCompartir = async (share: Share) => {
    try {
      await api.del(`/almacen/compartidos/${share.id}`);
      setCompartirModal(prev => prev ? { ...prev, shares: prev.shares.filter(x => x.id !== share.id) } : prev);
      showToast('Se dejó de compartir');
    } catch { showToast('No se pudo eliminar'); }
  };

  const enviarPorCorreo = (item: Item) => {
    useMailStore.getState().openCompose('new', {
      to: [], subject: item.nombre, text_body: '', html_body: '',
      adjuntos_almacen: [{ nombre: item.nombre, ruta: item.ruta }],
    } as never);
    navigate('/');   // el redactor vive en la vista de correo
  };

  const abrirMenu = (e: React.MouseEvent, item: Item) => {
    e.preventDefault();
    e.stopPropagation();
    setMenu({ item, x: Math.min(e.clientX, window.innerWidth - 210), y: Math.min(e.clientY, window.innerHeight - 300) });
  };

  const migas = ruta.split('/').filter(Boolean);
  const botonModo = 'px-2 py-1.5 rounded text-sm';
  const mostrados = resultados ?? items;

  const accionesDe = (item: Item) => vista !== 'papelera' ? ([
    ...(!item.es_carpeta && item.es_editable ? [{ texto: '✏️ Editar en línea', fn: () => abrir(item) }] : []),
    ...(!item.es_carpeta ? [
      { texto: '⬇️ Descargar', fn: () => window.open(`/api/almacen/archivos/descargar?ruta=${encodeURIComponent(item.ruta)}`) },
      { texto: '✉️ Enviar por correo', fn: () => enviarPorCorreo(item) },
    ] : []),
    { texto: '🔗 Compartir', fn: () => abrirCompartir(item) },
    { texto: item.es_favorito ? '⭐ Quitar de favoritos' : '⭐ Agregar a favoritos', fn: () => toggleFavorito(item) },
    { texto: '📂 Mover a…', fn: () => abrirSelector(item, 'mover') },
    { texto: '📋 Copiar a…', fn: () => abrirSelector(item, 'copiar') },
    { texto: '✍️ Renombrar', fn: () => renombrar(item) },
    ...(!item.es_carpeta ? [{ texto: '🕘 Historial de versiones', fn: () => verVersiones(item) }] : []),
    { texto: '🗑️ Eliminar', fn: () => eliminar(item) },
  ]) : ([
    { texto: '♻️ Restaurar', fn: () => restaurar(item) },
    { texto: '🗑️ Eliminar definitivo', fn: () => eliminarDefinitivo(item) },
  ]);

  return (
    <div className="flex flex-col h-full bg-white dark:bg-[#1b1a19]">
      {/* Barra superior */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-[#edebe9] dark:border-[#3b3a39] flex-wrap">
        <button onClick={() => irA('/', 'archivos')}
          title="Ver mis archivos"
          className={`px-3 py-1.5 rounded text-sm font-semibold ${vista === 'archivos' ? 'bg-[#deecf9] text-[#106ebe] dark:bg-[#004578] dark:text-white' : 'text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#323130]'}`}>
          📁 Mis archivos
        </button>
        <button onClick={() => irA('/', 'unidades')}
          title="Unidades compartidas de equipo: carpetas comunes donde varios miembros trabajan con roles (administrador, editor, lector)"
          className={`px-3 py-1.5 rounded text-sm font-semibold ${vista === 'unidades' ? 'bg-[#deecf9] text-[#106ebe] dark:bg-[#004578] dark:text-white' : 'text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#323130]'}`}>
          👥 Unidades
        </button>
        <button onClick={() => irA('/', 'conmigo')}
          title="Archivos que otras personas te compartieron a tu correo"
          className={`px-3 py-1.5 rounded text-sm font-semibold ${vista === 'conmigo' ? 'bg-[#deecf9] text-[#106ebe] dark:bg-[#004578] dark:text-white' : 'text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#323130]'}`}>
          🤝 Conmigo
        </button>
        <button onClick={() => irA('/', 'favoritos')}
          title="Tus archivos y carpetas marcados con estrella"
          className={`px-3 py-1.5 rounded text-sm font-semibold ${vista === 'favoritos' ? 'bg-[#deecf9] text-[#106ebe] dark:bg-[#004578] dark:text-white' : 'text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#323130]'}`}>
          ⭐ Favoritos
        </button>
        <button onClick={() => irA('/', 'papelera')}
          title="Ver la papelera (lo eliminado se puede restaurar)"
          className={`px-3 py-1.5 rounded text-sm font-semibold ${vista === 'papelera' ? 'bg-[#deecf9] text-[#106ebe] dark:bg-[#004578] dark:text-white' : 'text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#323130]'}`}>
          🗑️ Papelera
        </button>
        {vista === 'archivos' && (
          <div className="relative flex-1 min-w-[160px] max-w-md">
            <input value={busqueda} onChange={e => setBusqueda(e.target.value)}
              placeholder="Buscar en mis archivos…"
              title="Busca por nombre en todas tus carpetas (mínimo 2 letras)"
              className="w-full px-3 py-1.5 pr-8 rounded text-sm border border-[#8a8886] bg-white dark:bg-[#252423] text-[#323130] dark:text-[#e0e0e0] focus:border-[#0078d4] outline-none" />
            {busqueda && (
              <button onClick={() => { setBusqueda(''); setResultados(null); }}
                title="Limpiar la búsqueda"
                className="absolute right-1 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full text-[#605e5c] hover:bg-[#edebe9] dark:hover:bg-[#3b3a39]">✕</button>
            )}
          </div>
        )}
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
        ) : vista === 'unidades' ? (
          <button onClick={nuevaUnidad}
            title="Crear una unidad de equipo (solo administradores)"
            className="px-3 py-1.5 rounded text-sm font-semibold bg-[#0078d4] text-white hover:bg-[#106ebe]">
            ➕ Nueva unidad
          </button>
        ) : vista === 'papelera' ? (
          <button onClick={vaciarPapelera}
            title="Vaciar la papelera (los administradores aún pueden recuperar por un tiempo)"
            className="px-3 py-1.5 rounded text-sm font-semibold border border-[#d13438] text-[#d13438] hover:bg-[#fde7e9]">
            Vaciar papelera
          </button>
        ) : null}
        <div className="flex rounded border border-[#8a8886] overflow-hidden" role="group">
          <button onClick={() => cambiarModo('cuadricula')} title="Vista de cuadrícula (estilo Drive)"
            className={`${botonModo} ${modo === 'cuadricula' ? 'bg-[#deecf9] text-[#106ebe] dark:bg-[#004578] dark:text-white' : 'text-[#323130] dark:text-[#e0e0e0]'}`}>▦</button>
          <button onClick={() => cambiarModo('lista')} title="Vista de lista (estilo explorador)"
            className={`${botonModo} ${modo === 'lista' ? 'bg-[#deecf9] text-[#106ebe] dark:bg-[#004578] dark:text-white' : 'text-[#323130] dark:text-[#e0e0e0]'}`}>☰</button>
        </div>
        <button onClick={refrescar} title="Actualizar el listado"
          className="px-2 py-1.5 rounded text-sm text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#323130]">🔄</button>
      </div>

      {/* Migas de pan / encabezado de resultados */}
      {vista === 'archivos' && (resultados !== null ? (
        <div className="px-4 py-2 text-sm text-[#605e5c] dark:text-[#a19f9d]">
          🔎 {resultados.length} resultado{resultados.length !== 1 ? 's' : ''} para «{busqueda.trim()}» — clic en un resultado para abrir su carpeta
        </div>
      ) : (
        <div className="flex items-center gap-1 px-4 py-2 text-sm text-[#605e5c] dark:text-[#a19f9d] flex-wrap">
          {migas[0] === 'unidades' ? (
            <button onClick={() => irA('/', 'unidades')} className="hover:underline font-semibold text-[#106ebe]" title="Ver todas las unidades de equipo">👥 Unidades</button>
          ) : (
            <button onClick={() => irA('/')} className="hover:underline font-semibold text-[#106ebe]" title="Ir a la raíz de mis archivos">Mis archivos</button>
          )}
          {migas.map((parte, i) => {
            if (migas[0] === 'unidades' && i === 0) return null;
            const etiqueta = (migas[0] === 'unidades' && i === 1)
              ? (unidades.find(u => String(u.id) === parte)?.nombre || parte) : parte;
            return (
              <span key={i} className="flex items-center gap-1">
                <span>›</span>
                <button onClick={() => irA('/' + migas.slice(0, i + 1).join('/'))} className="hover:underline" title={`Ir a ${etiqueta}`}>{etiqueta}</button>
              </span>
            );
          })}
        </div>
      ))}

      {/* Contenido */}
      <div className="flex-1 overflow-y-auto">
        {vista === 'conmigo' ? (
          cargando ? (
            <div className="p-8 text-center text-[#605e5c] dark:text-[#a19f9d]">Cargando…</div>
          ) : conmigo.length === 0 ? (
            <div className="p-12 text-center text-[#605e5c] dark:text-[#a19f9d]">
              Nadie te ha compartido archivos todavía.<br/>
              Cuando alguien use "Compartir con una persona" hacia tu correo, aparecerá aquí.
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-[#605e5c] dark:text-[#a19f9d] border-b border-[#edebe9] dark:border-[#3b3a39]">
                  <th className="px-4 py-2 font-semibold">Nombre</th>
                  <th className="px-2 py-2 font-semibold w-44 hidden sm:table-cell">Compartido por</th>
                  <th className="px-2 py-2 font-semibold w-32 hidden md:table-cell">Fecha</th>
                  <th className="px-2 py-2 w-48"></th>
                </tr>
              </thead>
              <tbody>
                {conmigo.map(c => (
                  <tr key={c.id} className="border-b border-[#f3f2f1] dark:border-[#292827] hover:bg-[#f3f2f1] dark:hover:bg-[#292827]">
                    <td className="px-4 py-2 cursor-pointer"
                      onDoubleClick={() => window.open(c.abre_en_linea ? `/almacen-s/${c.token}/editar` : `/almacen-s/${c.token}`, '_blank')}
                      title={c.puede_editar ? 'Doble clic: editar en línea (misma sala que el dueño)' : c.abre_en_linea ? 'Doble clic: ver en línea' : 'Doble clic: descargar'}>
                      <span className="mr-2">{ICONOS[(c.extension || '').toLowerCase()] || '📎'}</span>
                      <span className="text-[#323130] dark:text-[#e0e0e0]">{c.nombre}</span>
                      {c.requiere_clave && <span className="ml-2 text-xs" title="El enlace tiene clave">🔒</span>}
                      {c.puede_editar && <span className="ml-2 text-[10px] font-semibold text-[#107c10]" title="Puedes editarlo">EDITOR</span>}
                    </td>
                    <td className="px-2 py-2 text-[#605e5c] dark:text-[#a19f9d] hidden sm:table-cell truncate max-w-[180px]">{c.de}</td>
                    <td className="px-2 py-2 text-[#605e5c] dark:text-[#a19f9d] hidden md:table-cell">{fechaCorta(c.creado_en)}</td>
                    <td className="px-2 py-2 text-right whitespace-nowrap">
                      {c.abre_en_linea && (
                        <button onClick={() => window.open(`/almacen-s/${c.token}/editar`, '_blank')}
                          title={c.puede_editar ? 'Editar en línea' : 'Ver en línea'}
                          className="px-2 py-1 text-xs rounded text-[#106ebe] hover:bg-[#deecf9] dark:hover:bg-[#004578] font-semibold">
                          {c.puede_editar ? '✏️ Editar' : '👁 Ver'}
                        </button>
                      )}
                      {c.permite_descarga && (
                        <button onClick={() => window.open(`/almacen-s/${c.token}`, '_blank')}
                          title="Descargar el archivo"
                          className="px-2 py-1 text-xs rounded text-[#323130] dark:text-[#e0e0e0] hover:bg-[#edebe9] dark:hover:bg-[#3b3a39]">Descargar</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        ) : vista === 'unidades' ? (
          unidades.length === 0 ? (
            <div className="p-12 text-center text-[#605e5c] dark:text-[#a19f9d]">
              No perteneces a ninguna unidad de equipo todavía.<br/>
              Las unidades son carpetas comunes donde un equipo trabaja junto (con roles y co-edición).
            </div>
          ) : (
            <div className="grid gap-3 p-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(190px, 1fr))' }}>
              {unidades.map(u => (
                <div key={u.id}
                  onClick={() => irA(u.ruta)}
                  title={`Abrir "${u.nombre}" — tu rol: ${ROL_ETIQUETA[u.mi_rol] || u.mi_rol}`}
                  className="relative rounded-lg border border-[#edebe9] dark:border-[#3b3a39] p-4 cursor-pointer select-none hover:shadow-md hover:border-[#0078d4] dark:hover:border-[#2899f5] transition-all group bg-white dark:bg-[#252423]">
                  <button onClick={e => { e.stopPropagation(); abrirMiembros(u); }}
                    title="Ver y gestionar los miembros de la unidad"
                    className="absolute top-2 right-2 px-2 py-0.5 rounded text-[11px] text-[#106ebe] opacity-0 group-hover:opacity-100 hover:bg-[#deecf9] dark:hover:bg-[#004578] font-semibold">Miembros</button>
                  <div className="text-4xl text-center mb-2">👥</div>
                  <div className="text-sm text-center font-semibold text-[#323130] dark:text-[#e0e0e0] break-words">{u.nombre}</div>
                  <div className="text-[11px] text-center text-[#a19f9d] mt-1">
                    {u.miembros} miembro{u.miembros !== 1 ? 's' : ''} · {ROL_ETIQUETA[u.mi_rol] || u.mi_rol}
                  </div>
                </div>
              ))}
            </div>
          )
        ) : cargando && resultados === null ? (
          <div className="p-8 text-center text-[#605e5c] dark:text-[#a19f9d]">Cargando…</div>
        ) : mostrados.length === 0 ? (
          <div className="p-12 text-center text-[#605e5c] dark:text-[#a19f9d]">
            {resultados !== null ? 'Sin resultados' : vista === 'papelera' ? 'La papelera está vacía' : vista === 'favoritos' ? 'Aún no marcas favoritos — clic derecho → ⭐ Agregar a favoritos' : 'Esta carpeta está vacía — usa "Subir" para empezar'}
          </div>
        ) : modo === 'cuadricula' ? (
          <div className="grid gap-3 p-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))' }}>
            {mostrados.map(item => (
              <div key={item.id || item.ruta}
                onClick={() => resultados !== null ? irA(item.es_carpeta ? item.ruta : carpetaDe(item.ruta)) : (item.es_carpeta && vista !== 'papelera' ? abrir(item) : undefined)}
                onDoubleClick={() => abrir(item)}
                onContextMenu={e => abrirMenu(e, item)}
                title={`${item.nombre}${item.es_carpeta ? '' : ` — ${item.tamano_humano}`}${resultados !== null ? `\nUbicación: ${carpetaDe(item.ruta)}` : ''}\nClic derecho: opciones`}
                className="relative rounded-lg border border-[#edebe9] dark:border-[#3b3a39] p-3 cursor-pointer select-none hover:shadow-md hover:border-[#0078d4] dark:hover:border-[#2899f5] transition-all group bg-white dark:bg-[#252423]">
                <button onClick={e => abrirMenu(e, item)} title="Opciones"
                  className="absolute top-1 right-1 w-7 h-7 rounded-full text-[#605e5c] dark:text-[#a19f9d] opacity-0 group-hover:opacity-100 hover:bg-[#edebe9] dark:hover:bg-[#3b3a39] text-lg leading-none">⋯</button>
                <div className="text-4xl text-center mb-2">{iconoDe(item)}</div>
                <div className="text-xs text-center text-[#323130] dark:text-[#e0e0e0] break-words leading-tight"
                  style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                  {item.nombre}
                </div>
                <div className="text-[10px] text-center text-[#a19f9d] mt-1 truncate">
                  {resultados !== null ? carpetaDe(item.ruta) : item.es_carpeta ? fechaCorta(item.eliminado_en || item.modificado_at) : item.tamano_humano}
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
                <th className="px-2 py-2 font-semibold w-40 hidden sm:table-cell">{resultados !== null ? 'Ubicación' : vista === 'papelera' ? 'Eliminado' : 'Modificado'}</th>
                <th className="px-2 py-2 w-10"></th>
              </tr>
            </thead>
            <tbody>
              {mostrados.map(item => (
                <tr key={item.id || item.ruta}
                  onContextMenu={e => abrirMenu(e, item)}
                  className="border-b border-[#f3f2f1] dark:border-[#292827] hover:bg-[#f3f2f1] dark:hover:bg-[#292827] group">
                  <td className="px-4 py-2 cursor-pointer"
                    onDoubleClick={() => abrir(item)}
                    onClick={() => resultados !== null ? irA(item.es_carpeta ? item.ruta : carpetaDe(item.ruta)) : (item.es_carpeta && vista !== 'papelera' ? abrir(item) : undefined)}
                    title={item.es_carpeta ? 'Abrir la carpeta' : (item.es_editable ? 'Doble clic: editar en línea' : 'Doble clic: ver/descargar')}>
                    <span className="mr-2">{iconoDe(item)}</span>
                    <span className="text-[#323130] dark:text-[#e0e0e0]">{item.nombre}</span>
                  </td>
                  <td className="px-2 py-2 text-[#605e5c] dark:text-[#a19f9d]">{item.tamano_humano}</td>
                  <td className="px-2 py-2 text-[#605e5c] dark:text-[#a19f9d] hidden sm:table-cell truncate max-w-[200px]">
                    {resultados !== null ? carpetaDe(item.ruta) : fechaCorta(item.eliminado_en || item.modificado_at)}
                  </td>
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

      {/* Menú contextual */}
      {menu && (
        <div className="fixed z-50 bg-white dark:bg-[#252423] border border-[#edebe9] dark:border-[#3b3a39] rounded-lg shadow-lg py-1 min-w-[190px]"
          style={{ left: menu.x, top: menu.y }} onClick={e => e.stopPropagation()}>
          <div className="px-3 py-1.5 text-xs text-[#a19f9d] border-b border-[#f3f2f1] dark:border-[#3b3a39] truncate max-w-[230px]">{menu.item.nombre}</div>
          {accionesDe(menu.item).map((a, i) => (
            <button key={i} onClick={() => { setMenu(null); a.fn(); }}
              className="block w-full text-left px-3 py-1.5 text-sm text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39]">
              {a.texto}
            </button>
          ))}
        </div>
      )}

      {/* Modal: miembros de una unidad de equipo */}
      {miembrosModal && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={() => setMiembrosModal(null)}>
          <div className="bg-white dark:bg-[#252423] rounded-lg shadow-xl w-full max-w-md max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="px-4 py-3 border-b border-[#edebe9] dark:border-[#3b3a39]">
              <div className="font-semibold text-[#323130] dark:text-[#e0e0e0]">👥 Miembros de la unidad</div>
              <div className="text-xs text-[#605e5c] dark:text-[#a19f9d] truncate">{miembrosModal.unidad.nombre}</div>
            </div>
            <div className="p-4 border-b border-[#f3f2f1] dark:border-[#3b3a39] space-y-2">
              <div className="text-xs font-semibold text-[#323130] dark:text-[#e0e0e0]">Agregar persona</div>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <input value={miembrosModal.buscar}
                    onChange={e => buscarParaUnidad(e.target.value)}
                    placeholder="Buscar por nombre o usuario…"
                    className="w-full px-2 py-1.5 rounded border border-[#8a8886] text-sm bg-white dark:bg-[#1b1a19] text-[#323130] dark:text-[#e0e0e0]" />
                  {miembrosModal.encontrados.length > 0 && (
                    <div className="absolute z-10 left-0 right-0 mt-1 bg-white dark:bg-[#252423] border border-[#edebe9] dark:border-[#3b3a39] rounded shadow-lg max-h-40 overflow-y-auto">
                      {miembrosModal.encontrados.map(u => (
                        <button key={u.id} onClick={() => agregarMiembro(u)}
                          title={`Agregar como ${ROL_ETIQUETA[miembrosModal.rol]}`}
                          className="block w-full text-left px-3 py-1.5 text-sm text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39]">
                          {u.nombre} <span className="text-xs text-[#a19f9d]">{u.email || ''}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <select value={miembrosModal.rol}
                  onChange={e => setMiembrosModal(prev => prev ? { ...prev, rol: e.target.value } : prev)}
                  title="Administrador: gestiona miembros. Editor: sube y edita. Lector: solo ve y descarga."
                  className="px-2 py-1 rounded border border-[#8a8886] text-sm bg-white dark:bg-[#1b1a19] text-[#323130] dark:text-[#e0e0e0]">
                  <option value="manager">Administrador</option>
                  <option value="editor">Editor</option>
                  <option value="viewer">Lector</option>
                </select>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-2">
              {miembrosModal.miembros.map(m => (
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
              <button onClick={() => setMiembrosModal(null)} className="px-3 py-1.5 rounded text-sm text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39]">Cerrar</button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: compartir con enlace */}
      {compartirModal && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={() => setCompartirModal(null)}>
          <div className="bg-white dark:bg-[#252423] rounded-lg shadow-xl w-full max-w-md max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="px-4 py-3 border-b border-[#edebe9] dark:border-[#3b3a39]">
              <div className="font-semibold text-[#323130] dark:text-[#e0e0e0]">🔗 Compartir</div>
              <div className="text-xs text-[#605e5c] dark:text-[#a19f9d] truncate">{compartirModal.item.nombre}</div>
            </div>
            <div className="p-4 border-b border-[#f3f2f1] dark:border-[#3b3a39] space-y-2">
              <div className="text-xs font-semibold text-[#323130] dark:text-[#e0e0e0]">Crear enlace de descarga</div>
              <div className="flex gap-2 items-center text-sm">
                <label className="text-xs text-[#605e5c] dark:text-[#a19f9d]" title="El enlace deja de funcionar pasado este plazo">Expira:</label>
                <select value={opcionesEnlace.expira_dias}
                  onChange={e => setOpcionesEnlace(o => ({ ...o, expira_dias: Number(e.target.value) }))}
                  className="px-2 py-1 rounded border border-[#8a8886] text-sm bg-white dark:bg-[#1b1a19] text-[#323130] dark:text-[#e0e0e0]">
                  <option value={0}>Nunca</option>
                  <option value={7}>7 días</option>
                  <option value={30}>30 días</option>
                  <option value={90}>90 días</option>
                </select>
                <input value={opcionesEnlace.clave}
                  onChange={e => setOpcionesEnlace(o => ({ ...o, clave: e.target.value }))}
                  placeholder="Clave (opcional)" title="Quien reciba el enlace deberá escribir esta clave"
                  className="flex-1 min-w-0 px-2 py-1 rounded border border-[#8a8886] text-sm bg-white dark:bg-[#1b1a19] text-[#323130] dark:text-[#e0e0e0]" />
              </div>
              <button onClick={crearEnlace} disabled={compartirModal.creando}
                title="Genera el enlace y lo copia al portapapeles"
                className="w-full px-3 py-1.5 rounded text-sm font-semibold bg-[#0078d4] text-white hover:bg-[#106ebe] disabled:opacity-50">
                {compartirModal.creando ? 'Creando…' : 'Crear y copiar enlace'}
              </button>
              <div className="text-[11px] text-[#a19f9d]">Cualquiera con el enlace podrá descargar el archivo (con la clave, si le pusiste una).</div>
            </div>
            <div className="p-4 border-b border-[#f3f2f1] dark:border-[#3b3a39] space-y-2">
              <div className="text-xs font-semibold text-[#323130] dark:text-[#e0e0e0]">Compartir con una persona</div>
              <div className="relative">
                <input value={persona.correo}
                  onChange={e => setPersona(p => ({ ...p, correo: e.target.value }))}
                  placeholder="Nombre o correo (interno o externo)"
                  title="Escribe un nombre para buscar en el directorio, o un correo completo"
                  className="w-full px-2 py-1.5 rounded border border-[#8a8886] text-sm bg-white dark:bg-[#1b1a19] text-[#323130] dark:text-[#e0e0e0]" />
                {sugerencias.length > 0 && (
                  <div className="absolute z-10 left-0 right-0 mt-1 bg-white dark:bg-[#252423] border border-[#edebe9] dark:border-[#3b3a39] rounded shadow-lg max-h-40 overflow-y-auto">
                    {sugerencias.map(u => (
                      <button key={u.id} onClick={() => { setPersona(p => ({ ...p, correo: u.email || '' })); setSugerencias([]); }}
                        className="block w-full text-left px-3 py-1.5 text-sm text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39]">
                        {u.nombre} <span className="text-xs text-[#a19f9d]">{u.email || ''}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex gap-2 items-center">
                <select value={persona.rol} onChange={e => setPersona(p => ({ ...p, rol: e.target.value }))}
                  title="Lector: puede descargar. Editor: además podrá editar cuando se habilite la edición por enlace."
                  className="px-2 py-1 rounded border border-[#8a8886] text-sm bg-white dark:bg-[#1b1a19] text-[#323130] dark:text-[#e0e0e0]">
                  <option value="lector">Lector</option>
                  <option value="editor">Editor</option>
                </select>
                <button onClick={compartirConPersona} disabled={compartirModal.creando}
                  title="Crea el enlace para esa persona y abre el correo listo para enviárselo"
                  className="flex-1 px-3 py-1.5 rounded text-sm font-semibold border border-[#0078d4] text-[#0078d4] hover:bg-[#deecf9] dark:hover:bg-[#004578] disabled:opacity-50">
                  ✉️ Compartir y enviar por correo
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-2">
              {compartirModal.shares.length === 0 ? (
                <div className="p-4 text-center text-sm text-[#605e5c] dark:text-[#a19f9d]">Este elemento aún no tiene enlaces activos</div>
              ) : compartirModal.shares.map(sh => (
                <div key={sh.id} className="flex items-center gap-2 px-3 py-2 rounded hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39]">
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-[#323130] dark:text-[#e0e0e0] truncate">{sh.url || sh.con_quien || `Compartido #${sh.id}`}</div>
                    <div className="text-[10px] text-[#a19f9d]">{sh.tipo === 3 ? 'Enlace público' : `Con: ${sh.con_quien || '—'}`}</div>
                  </div>
                  {sh.url && (
                    <button onClick={() => copiarEnlace(sh.url!)} title="Copiar el enlace"
                      className="px-2 py-1 rounded text-xs font-semibold text-[#106ebe] hover:bg-[#deecf9] dark:hover:bg-[#004578]">Copiar</button>
                  )}
                  <button onClick={() => dejarDeCompartir(sh)} title="El enlace deja de funcionar de inmediato"
                    className="px-2 py-1 rounded text-xs text-[#d13438] hover:bg-[#fde7e9]">Quitar</button>
                </div>
              ))}
            </div>
            <div className="px-4 py-2 border-t border-[#edebe9] dark:border-[#3b3a39] text-right">
              <button onClick={() => setCompartirModal(null)} className="px-3 py-1.5 rounded text-sm text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39]">Cerrar</button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: historial de versiones */}
      {versiones && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={() => setVersiones(null)}>
          <div className="bg-white dark:bg-[#252423] rounded-lg shadow-xl w-full max-w-md max-h-[70vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="px-4 py-3 border-b border-[#edebe9] dark:border-[#3b3a39]">
              <div className="font-semibold text-[#323130] dark:text-[#e0e0e0]">🕘 Historial de versiones</div>
              <div className="text-xs text-[#605e5c] dark:text-[#a19f9d] truncate">{versiones.item.nombre}</div>
            </div>
            <div className="flex-1 overflow-y-auto p-2">
              {versiones.lista.length === 0 ? (
                <div className="p-6 text-center text-sm text-[#605e5c] dark:text-[#a19f9d]">
                  Este archivo aún no tiene versiones anteriores.<br/>Cada vez que se edita o se sube de nuevo, la versión previa se guarda aquí.
                </div>
              ) : versiones.lista.map(v => (
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
              <button onClick={() => setVersiones(null)} className="px-3 py-1.5 rounded text-sm text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39]">Cerrar</button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: elegir carpeta destino (mover/copiar) */}
      {selector && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={() => setSelector(null)}>
          <div className="bg-white dark:bg-[#252423] rounded-lg shadow-xl w-full max-w-md max-h-[70vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="px-4 py-3 border-b border-[#edebe9] dark:border-[#3b3a39]">
              <div className="font-semibold text-[#323130] dark:text-[#e0e0e0]">{selector.accion === 'mover' ? '📂 Mover a…' : '📋 Copiar a…'}</div>
              <div className="text-xs text-[#605e5c] dark:text-[#a19f9d] truncate">{selector.item.nombre}</div>
            </div>
            <div className="px-4 py-2 flex items-center gap-1 text-sm flex-wrap border-b border-[#f3f2f1] dark:border-[#3b3a39]">
              <button onClick={() => abrirSelector(selector.item, selector.accion, '/')} className="text-[#106ebe] hover:underline font-semibold">Mis archivos</button>
              {selector.carpeta.split('/').filter(Boolean).map((parte, i, arr) => (
                <span key={i} className="flex items-center gap-1 text-[#605e5c] dark:text-[#a19f9d]">
                  <span>›</span>
                  <button onClick={() => abrirSelector(selector.item, selector.accion, '/' + arr.slice(0, i + 1).join('/'))} className="hover:underline">{parte}</button>
                </span>
              ))}
            </div>
            <div className="flex-1 overflow-y-auto p-2 min-h-[150px]">
              {selector.subcarpetas.length === 0 ? (
                <div className="p-6 text-center text-sm text-[#605e5c] dark:text-[#a19f9d]">Sin subcarpetas aquí</div>
              ) : selector.subcarpetas.map(c => (
                <button key={c.ruta} onClick={() => abrirSelector(selector.item, selector.accion, c.ruta)}
                  className="block w-full text-left px-3 py-2 rounded text-sm text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39]">
                  📁 {c.nombre}
                </button>
              ))}
            </div>
            <div className="px-4 py-2 border-t border-[#edebe9] dark:border-[#3b3a39] flex justify-between items-center">
              <span className="text-xs text-[#605e5c] dark:text-[#a19f9d] truncate">Destino: {selector.carpeta}</span>
              <div className="flex gap-2">
                <button onClick={() => setSelector(null)} className="px-3 py-1.5 rounded text-sm text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39]">Cancelar</button>
                <button onClick={confirmarSelector}
                  className="px-3 py-1.5 rounded text-sm font-semibold bg-[#0078d4] text-white hover:bg-[#106ebe]">
                  {selector.accion === 'mover' ? 'Mover aquí' : 'Copiar aquí'}
                </button>
              </div>
            </div>
          </div>
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
