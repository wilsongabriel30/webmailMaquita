import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../../api/client';
import { showToast } from '../common/Toast';
import { useMailStore } from '../../store/mailStore';
import { ROL_ETIQUETA, type Conmigo, type Cuota, type Item, type Share, type Unidad, type UsuarioDir, type Vista } from './tipos';
import { ICONOS, carpetaDe, fechaCorta, iconoDe } from './utilidadesArchivos';
import { MiniaturaOIcono } from './MiniaturaOIcono';
import { SelectorDestino } from './SelectorDestino';
import { VersionesModal } from './VersionesModal';
import { MiembrosModal } from './MiembrosModal';
import { AvisoCompartido } from './AvisoCompartido';
import { VistaDividida } from './VistaDividida';
import { carpetaInicialSelector } from './rutasEspacio';
import { moverOCopiar, type AccionDestino } from './moverElemento';
import { CLASE_RESALTADA, propsArrastrable, useSoltar, type Arrastrado } from './arrastre';
import { usePantallaAncha, useVistaDividida } from './preferenciaVistaDividida';

/* Archivos (Almacén Maquita) — nube personal integrada al webmail.
   Consume /api/almacen (contrato en almacen/docs/CONTRATO-API.md).
   - La ruta actual vive en la URL (?ruta=): el botón atrás del navegador
     retrocede ENTRE CARPETAS, y se puede compartir/refrescar el enlace.
   - Dos vistas (cuadrícula estilo Drive / lista) + buscador propio.
   - Menú contextual: editar, descargar, enviar por correo, mover, copiar,
     renombrar, historial de versiones, eliminar.
   - Vista dividida opcional (VistaDividida.tsx): segundo panel para arrastrar entre
     dos carpetas. Los tipos y los diálogos grandes viven en sus propios archivos. */

export function FilesView() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const ruta = params.get('ruta') || '/';
  const vistaParam = params.get('vista');
  const vista = (['papelera', 'favoritos', 'unidades', 'conmigo'].includes(vistaParam || '') ? vistaParam : 'archivos') as Vista;

  const [modo, setModo] = useState<'cuadricula' | 'lista'>(
    () => (localStorage.getItem('almacen_modo_vista') as 'cuadricula' | 'lista') || 'cuadricula');
  const [items, setItems] = useState<Item[]>([]);
  // Por qué falló la última carga: sin esto, un acceso denegado se veía igual que una
  // carpeta vacía, y la pantalla invitaba a subir ficheros que iban a ser rechazados.
  const [fallo, setFallo] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const [subiendo, setSubiendo] = useState(false);
  const [cuota, setCuota] = useState<Cuota | null>(null);
  const [menu, setMenu] = useState<{ item: Item; x: number; y: number } | null>(null);
  const [busqueda, setBusqueda] = useState('');
  const [resultados, setResultados] = useState<Item[] | null>(null);
  const [versionesDe, setVersionesDe] = useState<Item | null>(null);
  const [selector, setSelector] = useState<{ item: Item; accion: AccionDestino; carpeta: string } | null>(null);
  const [compartirModal, setCompartirModal] = useState<{ item: Item; shares: Share[]; creando: boolean } | null>(null);
  const [persona, setPersona] = useState({ correo: '', rol: 'lector' });
  const [sugerencias, setSugerencias] = useState<UsuarioDir[]>([]);
  const [unidades, setUnidades] = useState<Unidad[]>([]);
  const [conmigo, setConmigo] = useState<Conmigo[]>([]);
  const [miembrosDe, setMiembrosDe] = useState<Unidad | null>(null);
  const [opcionesEnlace, setOpcionesEnlace] = useState({ expira_dias: 0, clave: '', permite_descarga: true });
  const inputSubir = useRef<HTMLInputElement>(null);
  const timerBusqueda = useRef<ReturnType<typeof setTimeout>>(undefined);

  const irA = (nuevaRuta: string, nuevaVista: Vista = 'archivos') => {
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

  const cargar = useCallback(async (r: string, v: Vista) => {
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
    setFallo(null);
    try {
      if (v === 'papelera') {
        const res = await api.get<{ carpetas: Item[]; archivos: Item[] }>('/almacen/papelera');
        setItems([...(res.carpetas || []), ...(res.archivos || [])]);
      } else if (v === 'favoritos') {
        const res = await api.get<{ carpetas: Item[]; archivos: Item[] }>('/almacen/favoritos');
        setItems([...(res.carpetas || []), ...(res.archivos || [])].map(i => ({ ...i, es_favorito: true })));
      } else {
        // Pinta al instante lo último conocido de esta carpeta y refresca detrás
        const clave = `alm_cache:${r}`;
        try {
          const previo = sessionStorage.getItem(clave);
          if (previo) { setItems(JSON.parse(previo)); setCargando(false); }
        } catch { /* caché corrupta: se ignora */ }
        const res = await api.get<{ carpetas: Item[]; archivos: Item[] }>(`/almacen/archivos?ruta=${encodeURIComponent(r)}`);
        const lista = [...(res.carpetas || []), ...(res.archivos || [])];
        setItems(lista);
        try { sessionStorage.setItem(clave, JSON.stringify(lista)); } catch { /* llena: se ignora */ }
      }
    } catch (e) {
      showToast('No se pudieron cargar los archivos');
      setFallo(String((e as Error)?.message || ''));
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

  // Vista dividida: solo en el listado de carpetas y en pantallas anchas.
  const [dividida, setDividida] = useVistaDividida();
  const ancha = usePantallaAncha();
  const conPanel = dividida && ancha && vista === 'archivos';
  const [versionListado, setVersionListado] = useState(0);
  // Soltar en cualquiera de los dos paneles: la misma función de mover que «Mover a…».
  const alSoltar = useCallback(async (a: Arrastrado, carpeta: string) => {
    if (await moverOCopiar('mover', a, carpeta)) {
      cargar(ruta, vista); cargarCuota();
      setVersionListado(v => v + 1);
    }
  }, [cargar, cargarCuota, ruta, vista]);
  const { resaltada, propsDe } = useSoltar(alSoltar, conPanel && resultados === null);

  const abrir = (item: Item) => {
    if (vista === 'papelera') return;
    if (vista === 'favoritos' && item.es_carpeta) { irA(item.ruta); return; }
    if (item.es_carpeta) { irA(item.ruta); return; }
    if (item.es_editable) {
      // Ventana NOMBRADA por documento: si ya está abierto, se reutiliza la
      // pestaña en vez de abrir otra (cada editor abierto consume 1 de las
      // 20 conexiones de edición del Document Server Community).
      window.open(`/archivos-almacen/editar?ruta=${encodeURIComponent(item.ruta)}`, `oo-${item.id}`);
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

  // Dentro de una unidad, el diálogo arranca en la carpeta actual (con su prefijo).
  const abrirSelector = (item: Item, accion: AccionDestino) =>
    setSelector({ item, accion, carpeta: carpetaInicialSelector(ruta, vista === 'archivos' && resultados === null) });

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
    ...(!item.es_carpeta ? [{ texto: '🕘 Historial de versiones', fn: () => setVersionesDe(item) }] : []),
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
        {ancha && vista === 'archivos' && (
          <button onClick={() => setDividida(!dividida)} aria-pressed={dividida}
            aria-label="Vista dividida (dos paneles)"
            title={dividida ? 'Cerrar la vista dividida' : 'Vista dividida (dos paneles): abre una segunda carpeta a la derecha para arrastrar entre las dos'}
            className={`${botonModo} border border-[#8a8886] ${dividida ? 'bg-[#deecf9] text-[#106ebe] dark:bg-[#004578] dark:text-white' : 'text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#323130]'}`}>◫</button>
        )}
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

      {vista === 'archivos' && resultados === null && <AvisoCompartido ruta={ruta} />}

      {/* Contenido (y, si está activa, la vista dividida a la derecha) */}
      <div className="flex-1 flex min-h-0">
      <div {...propsDe(ruta)}
        className={`flex-1 min-w-0 overflow-y-auto ${conPanel && resaltada === ruta ? CLASE_RESALTADA : ''}`}>
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
                      onDoubleClick={() => window.open(c.abre_en_linea ? `/almacen-s/${c.token}/editar` : `/almacen-s/${c.token}`, `oo-${c.token}`)}
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
                        <button onClick={() => window.open(`/almacen-s/${c.token}/editar`, `oo-${c.token}`)}
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
                  <button onClick={e => { e.stopPropagation(); setMiembrosDe(u); }}
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
            {fallo
              ? (/403|permis|acceso/i.test(fallo)
                  ? 'No tienes acceso a esta carpeta. Si crees que deberías tenerlo, escribe a Tecnología: tu buzón puede no estar vinculado a una persona del directorio.'
                  : 'No se pudieron cargar los archivos. Vuelve a intentarlo con 🔄.')
              : resultados !== null ? 'Sin resultados' : vista === 'papelera' ? 'La papelera está vacía' : vista === 'favoritos' ? 'Aún no marcas favoritos — clic derecho → ⭐ Agregar a favoritos' : 'Esta carpeta está vacía — usa "Subir" para empezar'}
          </div>
        ) : modo === 'cuadricula' ? (
          <div className="grid gap-3 p-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))' }}>
            {mostrados.map(item => (
              <div key={item.id || item.ruta}
                {...propsArrastrable(item, conPanel)}
                {...(item.es_carpeta ? propsDe(item.ruta) : {})}
                onClick={() => resultados !== null ? irA(item.es_carpeta ? item.ruta : carpetaDe(item.ruta)) : (item.es_carpeta && vista !== 'papelera' ? abrir(item) : undefined)}
                onDoubleClick={() => abrir(item)}
                onContextMenu={e => abrirMenu(e, item)}
                title={`${item.nombre}${item.es_carpeta ? '' : ` — ${item.tamano_humano}`}${resultados !== null ? `\nUbicación: ${carpetaDe(item.ruta)}` : ''}\nClic derecho: opciones`}
                className={`relative rounded-lg border border-[#edebe9] dark:border-[#3b3a39] p-3 cursor-pointer select-none hover:shadow-md hover:border-[#0078d4] dark:hover:border-[#2899f5] transition-all group bg-white dark:bg-[#252423] ${resaltada === item.ruta ? CLASE_RESALTADA : ''}`}>
                <button onClick={e => abrirMenu(e, item)} title="Opciones"
                  className="absolute top-1 right-1 w-7 h-7 rounded-full text-[#605e5c] dark:text-[#a19f9d] opacity-0 group-hover:opacity-100 hover:bg-[#edebe9] dark:hover:bg-[#3b3a39] text-lg leading-none">⋯</button>
                <MiniaturaOIcono item={item} />
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
                  {...propsArrastrable(item, conPanel)}
                  {...(item.es_carpeta ? propsDe(item.ruta) : {})}
                  onContextMenu={e => abrirMenu(e, item)}
                  className={`border-b border-[#f3f2f1] dark:border-[#292827] hover:bg-[#f3f2f1] dark:hover:bg-[#292827] group ${resaltada === item.ruta ? CLASE_RESALTADA : ''}`}>
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
      {conPanel && (
        <VistaDividida rutaIzquierda={ruta} unidades={unidades} version={versionListado}
          alSoltar={alSoltar} onAbrirArchivo={abrir} onCerrar={() => setDividida(false)} />
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
      {miembrosDe && <MiembrosModal unidad={miembrosDe} onCerrar={() => setMiembrosDe(null)} />}

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
      {versionesDe && (
        <VersionesModal item={versionesDe} onCerrar={() => setVersionesDe(null)}
          onRestaurada={() => { setVersionesDe(null); refrescar(); }} />
      )}

      {/* Modal: elegir carpeta destino (mover/copiar) */}
      {selector && (
        <SelectorDestino item={selector.item} accion={selector.accion} carpetaInicial={selector.carpeta}
          unidades={unidades} onCerrar={() => setSelector(null)}
          onHecho={() => { setSelector(null); refrescar(); setVersionListado(v => v + 1); }} />
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
