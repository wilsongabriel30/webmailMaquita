import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import type { Item, Unidad } from './tipos';
import { espacioDeRuta, migasDelEspacio, padreDentroDelEspacio } from './rutasEspacio';
import { iconoDe, nombreRaizEspacio } from './utilidadesArchivos';
import { CLASE_RESALTADA, propsArrastrable, useSoltar, type Arrastrado } from './arrastre';

/* Vista dividida: un segundo panel a la derecha, con su propio listado navegable,
   para arrastrar elementos entre dos carpetas sin salir de la pestaña (arrastrar
   entre dos pestañas del navegador no es posible). Soltar aquí o allá pasa por la
   MISMA función de mover que «Mover a…» (FilesView → moverOCopiar), con los mismos
   avisos; después se refrescan los dos paneles (`version`).

   Las rutas del panel van con el prefijo de su espacio (/unidades/<id>/…) y «subir»
   nunca pasa de la raíz de ese espacio. */

interface Props {
  rutaIzquierda: string;
  unidades: Unidad[];
  /** Cambia cuando hay que volver a listar (algo se movió en cualquiera de los paneles). */
  version: number;
  alSoltar: (a: Arrastrado, carpeta: string) => void;
  onAbrirArchivo: (item: Item) => void;
  onCerrar: () => void;
}

const BOTON = 'w-8 h-8 inline-flex items-center justify-center rounded border border-[#c8c6c4] dark:border-[#605e5c] text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39] disabled:opacity-40 disabled:cursor-default';

export function VistaDividida({ rutaIzquierda, unidades, version, alSoltar, onAbrirArchivo, onCerrar }: Props) {
  const [ruta, setRuta] = useState(rutaIzquierda);
  const [items, setItems] = useState<Item[]>([]);
  const [estado, setEstado] = useState<'cargando' | 'listo' | 'error'>('cargando');
  const { resaltada, propsDe } = useSoltar(alSoltar, true);

  const [recarga, setRecarga] = useState(0);

  const navegar = (r: string) => {
    if (r === ruta) return;
    setItems([]);
    setEstado('cargando');
    setRuta(r);
  };

  useEffect(() => {
    let vivo = true;
    api.get<{ carpetas: Item[]; archivos: Item[] }>(`/almacen/archivos?ruta=${encodeURIComponent(ruta)}`)
      .then(res => {
        if (!vivo) return;
        setItems([...(res.carpetas || []), ...(res.archivos || [])]);
        setEstado('listo');
      })
      .catch(() => { if (vivo) { setItems([]); setEstado('error'); } });
    return () => { vivo = false; };
  }, [ruta, version, recarga]);

  const espacio = espacioDeRuta(ruta);
  const padre = padreDentroDelEspacio(ruta);
  const raizNombre = nombreRaizEspacio(espacio.unidadId, unidades);
  const migas = migasDelEspacio(ruta);

  return (
    <aside role="region" aria-label="Segundo panel de la vista dividida"
      className="w-[min(480px,45%)] shrink-0 flex flex-col border-l border-[#edebe9] dark:border-[#3b3a39] bg-white dark:bg-[#1b1a19]">
      <div className="flex items-center gap-1 px-3 py-2 border-b border-[#edebe9] dark:border-[#3b3a39] bg-[#faf9f8] dark:bg-[#252423]">
        <select value={espacio.raiz} onChange={e => navegar(e.target.value)}
          aria-label="Espacio que muestra el segundo panel"
          className="flex-1 min-w-0 px-2 py-1 rounded border border-[#8a8886] text-sm bg-white dark:bg-[#1b1a19] text-[#323130] dark:text-[#e0e0e0]">
          <option value="/">📁 Mis archivos</option>
          {unidades.map(u => <option key={u.id} value={`/unidades/${u.id}`}>👥 {u.nombre}</option>)}
        </select>
        <button type="button" className={BOTON} disabled={padre === null} onClick={() => padre !== null && navegar(padre)}
          aria-label="Subir un nivel" title="Subir un nivel">⬆</button>
        <button type="button" className={BOTON} onClick={() => navegar(rutaIzquierda)}
          aria-label="Ir a la carpeta de la izquierda" title="Ir a la carpeta que se ve a la izquierda">⇤</button>
        <button type="button" className={BOTON} onClick={() => setRecarga(n => n + 1)}
          aria-label="Actualizar el segundo panel" title="Actualizar">🔄</button>
        <button type="button" className={BOTON} onClick={onCerrar}
          aria-label="Cerrar la vista dividida" title="Cerrar la vista dividida">✕</button>
      </div>
      <nav aria-label="Ubicación del segundo panel" className="flex items-center gap-1 px-3 py-1.5 text-xs text-[#605e5c] dark:text-[#a19f9d] flex-wrap">
        {migas.map((m, i) => (
          <span key={m.ruta} className="flex items-center gap-1">
            {i > 0 && <span aria-hidden="true">›</span>}
            <button type="button" onClick={() => navegar(m.ruta)} {...propsDe(m.ruta)}
              aria-current={i === migas.length - 1 ? 'location' : undefined}
              className={`hover:underline rounded px-0.5 ${m.esRaiz ? 'font-semibold text-[#106ebe]' : ''} ${resaltada === m.ruta ? CLASE_RESALTADA : ''}`}>
              {m.esRaiz ? raizNombre : m.parte}
            </button>
          </span>
        ))}
      </nav>
      <div {...propsDe(ruta)}
        className={`flex-1 overflow-y-auto p-1 ${resaltada === ruta ? CLASE_RESALTADA : ''}`}>
        {estado === 'cargando' && items.length === 0 ? (
          <div className="p-6 text-center text-sm text-[#605e5c] dark:text-[#a19f9d]">Cargando…</div>
        ) : estado === 'error' ? (
          <div className="p-6 text-center text-sm text-[#605e5c] dark:text-[#a19f9d]">No se pudo abrir esta carpeta.</div>
        ) : items.length === 0 ? (
          <div className="p-6 text-center text-sm text-[#605e5c] dark:text-[#a19f9d]">Carpeta vacía.<br />Arrastra aquí elementos para moverlos.</div>
        ) : (
          <ul aria-label={`Contenido de ${migas.length > 1 ? migas[migas.length - 1].parte : raizNombre}`}>
            {items.map(item => (
              <li key={item.id || item.ruta}>
                <button type="button"
                  {...propsArrastrable(item, true)}
                  {...(item.es_carpeta ? propsDe(item.ruta) : {})}
                  onClick={() => item.es_carpeta && navegar(item.ruta)}
                  onDoubleClick={() => !item.es_carpeta && onAbrirArchivo(item)}
                  onKeyDown={e => { if (e.key === 'Enter' && !item.es_carpeta) { e.preventDefault(); onAbrirArchivo(item); } }}
                  title={item.es_carpeta ? `Abrir «${item.nombre}» (o suelta aquí para moverlo dentro)` : `${item.nombre} — doble clic para abrir`}
                  className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-left text-sm text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#292827] ${resaltada === item.ruta ? CLASE_RESALTADA : ''}`}>
                  <span aria-hidden="true">{iconoDe(item)}</span>
                  <span className="flex-1 truncate">{item.nombre}</span>
                  {!item.es_carpeta && <span className="text-[11px] text-[#a19f9d]">{item.tamano_humano}</span>}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}
