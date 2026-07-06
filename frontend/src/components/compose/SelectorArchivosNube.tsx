import { useEffect, useState } from 'react';
import { showToast } from '../common/Toast';

/* Selector de archivos de la Nube (Almacén) para adjuntar al correo.
   Navega las carpetas del usuario (/api/almacen), permite marcar varios
   archivos, los descarga con la sesión del correo y los entrega como
   objetos File al redactor (que los adjunta como cualquier adjunto). */

interface ItemNube {
  id: string; nombre: string; ruta: string; es_carpeta: boolean;
  extension?: string; tamano_bytes?: number; tamano_humano?: string;
}

interface Props {
  onCerrar: () => void;
  onElegir: (archivos: File[]) => void;
}

const LIMITE_MB = 25;

export function SelectorArchivosNube({ onCerrar, onElegir }: Props) {
  const [ruta, setRuta] = useState('/');
  const [items, setItems] = useState<ItemNube[]>([]);
  const [cargando, setCargando] = useState(false);
  const [sel, setSel] = useState<Record<string, ItemNube>>({});
  const [bajando, setBajando] = useState(false);
  const [disponible, setDisponible] = useState<boolean | null>(null);

  useEffect(() => {
    setCargando(true);
    fetch(`/api/almacen/archivos?ruta=${encodeURIComponent(ruta)}`, { credentials: 'include' })
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(d => {
        setDisponible(true);
        setItems([...(d.carpetas || []), ...(d.archivos || [])]);
      })
      .catch(() => { setDisponible(false); setItems([]); })
      .finally(() => setCargando(false));
  }, [ruta]);

  const toggle = (it: ItemNube) => {
    setSel(prev => {
      const n = { ...prev };
      if (n[it.ruta]) delete n[it.ruta]; else n[it.ruta] = it;
      return n;
    });
  };

  const adjuntar = async () => {
    const elegidos = Object.values(sel);
    if (elegidos.length === 0) return;
    setBajando(true);
    const archivos: File[] = [];
    for (const it of elegidos) {
      try {
        const res = await fetch(`/api/almacen/archivos/descargar?ruta=${encodeURIComponent(it.ruta)}`, { credentials: 'include' });
        if (!res.ok) throw new Error();
        const blob = await res.blob();
        if (blob.size > LIMITE_MB * 1024 * 1024) {
          showToast(`"${it.nombre}" supera ${LIMITE_MB} MB — omitido (comprime o comparte por enlace)`);
          continue;
        }
        archivos.push(new File([blob], it.nombre, { type: blob.type || 'application/octet-stream' }));
      } catch {
        showToast(`No se pudo adjuntar "${it.nombre}"`);
      }
    }
    setBajando(false);
    if (archivos.length) { onElegir(archivos); onCerrar(); }
  };

  const migas = ruta.split('/').filter(Boolean);
  const nSel = Object.keys(sel).length;

  return (
    <div className="fixed inset-0 z-[60] bg-black/40 flex items-center justify-center p-4" onClick={onCerrar}>
      <div className="bg-white dark:bg-[#252423] rounded-lg shadow-xl w-full max-w-lg max-h-[75vh] flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="px-4 py-3 border-b border-[#edebe9] dark:border-[#3b3a39] flex items-center gap-2">
          <span className="text-lg">☁️</span>
          <div className="font-semibold text-[#323130] dark:text-[#e0e0e0]">Adjuntar desde la Nube</div>
        </div>

        {disponible === false ? (
          <div className="p-8 text-center text-sm text-[#605e5c] dark:text-[#a19f9d]">
            La Nube de archivos no está disponible en esta cuenta.
          </div>
        ) : (
          <>
            {/* Migas de pan */}
            <div className="px-4 py-2 flex items-center gap-1 text-sm flex-wrap border-b border-[#f3f2f1] dark:border-[#3b3a39]">
              <button onClick={() => setRuta('/')} className="text-[#106ebe] hover:underline font-semibold">Mis archivos</button>
              {migas.map((parte, i) => (
                <span key={i} className="flex items-center gap-1 text-[#605e5c] dark:text-[#a19f9d]">
                  <span>›</span>
                  <button onClick={() => setRuta('/' + migas.slice(0, i + 1).join('/'))} className="hover:underline">{parte}</button>
                </span>
              ))}
            </div>

            <div className="flex-1 overflow-y-auto p-1 min-h-[200px]">
              {cargando ? (
                <div className="p-8 text-center text-sm text-[#605e5c] dark:text-[#a19f9d]">Cargando…</div>
              ) : items.length === 0 ? (
                <div className="p-8 text-center text-sm text-[#605e5c] dark:text-[#a19f9d]">Carpeta vacía</div>
              ) : items.map(it => (
                <div key={it.id || it.ruta}
                  onClick={() => it.es_carpeta ? setRuta(it.ruta) : toggle(it)}
                  className={`flex items-center gap-2 px-3 py-2 rounded cursor-pointer text-sm ${sel[it.ruta] ? 'bg-[#deecf9] dark:bg-[#004578]' : 'hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39]'}`}>
                  {!it.es_carpeta && (
                    <input type="checkbox" readOnly checked={!!sel[it.ruta]} className="shrink-0" />
                  )}
                  <span>{it.es_carpeta ? '📁' : '📎'}</span>
                  <span className="flex-1 text-[#323130] dark:text-[#e0e0e0] truncate">{it.nombre}</span>
                  <span className="text-xs text-[#a19f9d]">{it.es_carpeta ? '' : (it.tamano_humano || '')}</span>
                </div>
              ))}
            </div>

            <div className="px-4 py-2 border-t border-[#edebe9] dark:border-[#3b3a39] flex justify-between items-center">
              <span className="text-xs text-[#605e5c] dark:text-[#a19f9d]">{nSel > 0 ? `${nSel} seleccionado${nSel > 1 ? 's' : ''}` : 'Elige uno o más archivos'}</span>
              <div className="flex gap-2">
                <button onClick={onCerrar} className="px-3 py-1.5 rounded text-sm text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#3b3a39]">Cancelar</button>
                <button onClick={adjuntar} disabled={nSel === 0 || bajando}
                  className="px-3 py-1.5 rounded text-sm font-semibold bg-[#0078d4] text-white hover:bg-[#106ebe] disabled:opacity-50">
                  {bajando ? 'Adjuntando…' : `Adjuntar${nSel > 0 ? ` (${nSel})` : ''}`}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
