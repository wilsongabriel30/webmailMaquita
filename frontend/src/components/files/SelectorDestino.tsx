import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../../api/client';
import { showToast } from '../common/Toast';
import type { Item, Unidad } from './tipos';
import { migasDelEspacio, espacioDeRuta } from './rutasEspacio';
import { nombreRaizEspacio } from './utilidadesArchivos';
import { moverOCopiar, type AccionDestino } from './moverElemento';

/* Diálogo «Mover a…» / «Copiar a…»: elegir la carpeta destino navegando.
   Dentro de una unidad arranca en la carpeta actual y las migas van desde la raíz
   de ESA unidad, con su prefijo (/unidades/<id>/…): así reorganizar dentro de la
   unidad deja el archivo en la unidad. Antes arrancaba siempre en «Mis archivos» y
   el destino caía en el espacio personal (ver rutasEspacio.ts). */

interface Props {
  item: Item;
  accion: AccionDestino;
  carpetaInicial: string;
  unidades: Unidad[];
  onCerrar: () => void;
  onHecho: () => void;
}

export function SelectorDestino({ item, accion, carpetaInicial, unidades, onCerrar, onHecho }: Props) {
  const [carpeta, setCarpeta] = useState(carpetaInicial);
  const [subcarpetas, setSubcarpetas] = useState<Item[] | null>(null);
  const [enviando, setEnviando] = useState(false);

  const cerrar = useRef(onCerrar);
  useEffect(() => { cerrar.current = onCerrar; }, [onCerrar]);

  const listar = useCallback((destino: string) =>
    api.get<{ carpetas: Item[] }>(`/almacen/archivos?ruta=${encodeURIComponent(destino)}`)
      .then(res => (res.carpetas || []).filter(c => c.ruta !== item.ruta)), [item.ruta]);

  const abrir = (destino: string) => {
    listar(destino)
      .then(c => { setCarpeta(destino); setSubcarpetas(c); })
      .catch(() => showToast('No se pudo abrir el selector'));
  };

  // Si ni siquiera abre la carpeta de partida, el diálogo no tiene nada que ofrecer.
  useEffect(() => {
    let vivo = true;
    listar(carpetaInicial)
      .then(c => { if (vivo) setSubcarpetas(c); })
      .catch(() => { showToast('No se pudo abrir el selector'); cerrar.current(); });
    return () => { vivo = false; };
  }, [listar, carpetaInicial]);
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => { if (e.key === 'Escape') cerrar.current(); };
    window.addEventListener('keydown', tecla);
    return () => window.removeEventListener('keydown', tecla);
  }, []);

  const confirmar = async () => {
    setEnviando(true);
    const hecho = await moverOCopiar(accion, item, carpeta);
    setEnviando(false);
    if (hecho) onHecho();
  };

  const espacio = espacioDeRuta(carpeta);
  const migas = migasDelEspacio(carpeta);
  const raizNombre = nombreRaizEspacio(espacio.unidadId, unidades);
  const destinoLegible = [raizNombre, ...migas.slice(1).map(m => m.parte)].join(' › ');
  const titulo = accion === 'mover' ? '📂 Mover a…' : '📋 Copiar a…';

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={onCerrar}>
      <div role="dialog" aria-modal="true" aria-labelledby="selector-destino-titulo"
        className="bg-white dark:bg-[#252423] rounded-lg shadow-xl w-full max-w-md max-h-[70vh] flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="px-4 py-3 border-b border-[#edebe9] dark:border-[#3b3a39]">
          <div id="selector-destino-titulo" className="font-semibold text-[#323130] dark:text-[#e0e0e0]">{titulo}</div>
          <div className="text-xs text-[#605e5c] dark:text-[#a19f9d] truncate">{item.nombre}</div>
        </div>
        <nav aria-label="Ubicación del destino" className="px-4 py-2 flex items-center gap-1 text-sm flex-wrap border-b border-[#f3f2f1] dark:border-[#3b3a39]">
          <button onClick={() => abrir('/')} className="text-[#106ebe] hover:underline font-semibold">Mis archivos</button>
          {migas.filter(m => !(m.esRaiz && espacio.tipo === 'propio')).map(m => (
            <span key={m.ruta} className="flex items-center gap-1 text-[#605e5c] dark:text-[#a19f9d]">
              <span aria-hidden="true">›</span>
              <button onClick={() => abrir(m.ruta)} className={`hover:underline ${m.esRaiz ? 'font-semibold text-[#106ebe]' : ''}`}>
                {m.esRaiz ? `👥 ${raizNombre}` : m.parte}
              </button>
            </span>
          ))}
        </nav>
        <div className="flex-1 overflow-y-auto p-2 min-h-[150px]">
          {subcarpetas === null ? (
            <div className="p-6 text-center text-sm text-[#605e5c] dark:text-[#a19f9d]">Cargando…</div>
          ) : subcarpetas.length === 0 ? (
            <div className="p-6 text-center text-sm text-[#605e5c] dark:text-[#a19f9d]">Sin subcarpetas aquí</div>
          ) : subcarpetas.map(c => (
            <button key={c.ruta} onClick={() => abrir(c.ruta)}
              className="block w-full text-left px-3 py-2 rounded text-sm text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39]">
              📁 {c.nombre}
            </button>
          ))}
        </div>
        <div className="px-4 py-2 border-t border-[#edebe9] dark:border-[#3b3a39] flex justify-between items-center gap-2">
          <span className="text-xs text-[#605e5c] dark:text-[#a19f9d] truncate" title={destinoLegible}>Destino: {destinoLegible}</span>
          <div className="flex gap-2">
            <button onClick={onCerrar} className="px-3 py-1.5 rounded text-sm text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39]">Cancelar</button>
            <button onClick={confirmar} disabled={enviando}
              className="px-3 py-1.5 rounded text-sm font-semibold bg-[#0078d4] text-white hover:bg-[#106ebe] disabled:opacity-50">
              {accion === 'mover' ? 'Mover aquí' : 'Copiar aquí'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
