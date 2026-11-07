/**
 * BotonEtiquetasCorreo.tsx — botón «Etiquetas» en la barra de acciones del correo abierto (05/11/2026).
 * Despliega las etiquetas del usuario con casillas y «Nueva etiqueta…».
 */
import { useEffect, useRef, useState } from 'react';
import { useLabels } from '../../hooks/useLabels';
import { showToast } from '../common/Toast';
import { CARPETA_VIRTUAL, AVISO_SIN_ETIQUETAS_EN_TODO } from '../../lib/carpetaReal';
import { asignarEtiquetaA, etiquetasDelCorreo } from './asignarEtiquetas';
import { DialogoEtiqueta } from './DialogoEtiqueta';
import { ICONO_ETIQUETA } from './useEtiquetasContextual';

interface Props { folder: string; uid: number; estilo: React.CSSProperties }

export function BotonEtiquetasCorreo({ folder, uid, estilo }: Props) {
  const { labels, fetchLabels, createLabel, supported } = useLabels();
  const [abierto, setAbierto] = useState(false);
  const [asignadas, setAsignadas] = useState<Set<number>>(new Set());
  const [nueva, setNueva] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const virtual = folder === CARPETA_VIRTUAL;

  useEffect(() => {
    if (!abierto) return;
    if (labels.length === 0) fetchLabels();
    etiquetasDelCorreo(folder, uid).then((ids) => setAsignadas(new Set(ids))).catch(() => setAsignadas(new Set()));
    const fuera = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setAbierto(false); };
    document.addEventListener('mousedown', fuera);
    return () => document.removeEventListener('mousedown', fuera);
  }, [abierto, folder, uid, labels.length, fetchLabels]);

  if (!supported) return null;

  const alternar = async (id: number) => {
    const tenia = asignadas.has(id);
    const s = new Set(asignadas);
    if (tenia) s.delete(id); else s.add(id);
    setAsignadas(s);
    try { await asignarEtiquetaA(id, [{ folder, uid }], folder, tenia); }
    catch { showToast('No se pudo cambiar la etiqueta'); setAsignadas(asignadas); }
  };

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button style={{ ...estilo, opacity: virtual ? 0.5 : 1 }} title={virtual ? AVISO_SIN_ETIQUETAS_EN_TODO : 'Etiquetas'}
        onClick={() => { if (virtual) { showToast(AVISO_SIN_ETIQUETAS_EN_TODO); return; } setAbierto(!abierto); }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d={ICONO_ETIQUETA} /></svg>
        <span>Etiquetas{asignadas.size ? ` (${asignadas.size})` : ''}</span>
      </button>
      {abierto && (
        <div className="absolute left-0 top-full mt-1 w-[240px] max-h-[320px] overflow-y-auto bg-white dark:bg-[#1e1e1e] rounded shadow-xl border border-[#edebe9] dark:border-[#333] z-[300] py-1">
          {labels.length === 0 && <p className="px-3 py-2 text-[12px] text-[#a19f9d]">Sin etiquetas todavía</p>}
          {labels.map((l) => (
            <label key={l.id} className="flex items-center gap-2 px-3 py-1.5 text-[13px] text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#333] cursor-pointer">
              <input type="checkbox" checked={asignadas.has(l.id)} onChange={() => alternar(l.id)} />
              <span className="w-3 h-3 rounded-sm shrink-0" style={{ backgroundColor: l.color }} />
              <span className="truncate">{l.name}</span>
            </label>
          ))}
          <div className="border-t border-[#edebe9] dark:border-[#333] my-1" />
          <button type="button" onClick={() => { setAbierto(false); setNueva(true); }}
            className="w-full text-left px-3 py-1.5 text-[13px] text-[#106ebe] hover:bg-[#f3f2f1] dark:hover:bg-[#333]">
            + Nueva etiqueta…
          </button>
        </div>
      )}
      <DialogoEtiqueta abierto={nueva} onCerrar={() => setNueva(false)}
        onGuardar={async (nombre, color) => {
          const creada = await createLabel(nombre, color);
          await asignarEtiquetaA(creada.id, [{ folder, uid }], folder);
          setAsignadas((prev) => new Set(prev).add(creada.id));
          showToast(`Etiqueta «${nombre}» creada y asignada`);
        }} />
    </div>
  );
}
