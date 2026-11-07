/**
 * DialogoEtiqueta.tsx — crear o renombrar una etiqueta y elegir su color (05/11/2026).
 * Lo usan la barra lateral, el menú contextual de la lista y la vista del correo.
 */
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { LABEL_COLORS } from '../../hooks/useLabels';

interface Props {
  abierto: boolean;
  inicial?: { name: string; color: string } | null;
  onCerrar: () => void;
  onGuardar: (nombre: string, color: string) => Promise<void> | void;
}

export function DialogoEtiqueta({ abierto, inicial, onCerrar, onGuardar }: Props) {
  const [nombre, setNombre] = useState('');
  const [color, setColor] = useState(LABEL_COLORS[1].value);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!abierto) return;
    setNombre(inicial?.name || '');
    setColor(inicial?.color || LABEL_COLORS[1].value);
    setError('');
  }, [abierto, inicial]);

  if (!abierto) return null;

  const guardar = async () => {
    const n = nombre.trim();
    if (!n) { setError('Escribe un nombre'); return; }
    if (n.length > 60) { setError('Máximo 60 caracteres'); return; }
    setGuardando(true);
    try {
      await onGuardar(n, color);
      onCerrar();
    } catch (e) {
      setError(e instanceof Error && e.message ? e.message : 'No se pudo guardar la etiqueta');
    } finally {
      setGuardando(false);
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-[400] flex items-center justify-center bg-black/30" onMouseDown={onCerrar}>
      <div role="dialog" aria-modal="true" aria-label={inicial ? 'Renombrar etiqueta' : 'Nueva etiqueta'}
        className="bg-white dark:bg-[#1e1e1e] rounded-lg shadow-xl w-[340px] max-w-[94vw] p-4"
        onMouseDown={(e) => e.stopPropagation()}>
        <h3 className="text-[15px] font-semibold text-[#323130] dark:text-[#e0e0e0] mb-3">
          {inicial ? 'Editar etiqueta' : 'Nueva etiqueta'}
        </h3>
        <label className="block text-[12px] text-[#605e5c] mb-1">Nombre</label>
        <input autoFocus value={nombre} onChange={(e) => setNombre(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') guardar(); if (e.key === 'Escape') onCerrar(); }}
          placeholder="Ej.: Proveedores, Urgente, Proyecto X"
          className="w-full text-[13px] px-2 py-1.5 border border-[#c8c6c4] focus:border-[#0078d4] rounded outline-none bg-white dark:bg-[#2a2a2a] text-[#323130] dark:text-[#e0e0e0]" />
        <label className="block text-[12px] text-[#605e5c] mt-3 mb-1">Color</label>
        <div className="flex flex-wrap gap-2 items-center">
          {LABEL_COLORS.map((c) => (
            <button key={c.value} type="button" title={c.name} onClick={() => setColor(c.value)}
              className={`w-6 h-6 rounded-full border-2 ${color === c.value ? 'border-[#323130] dark:border-white scale-110' : 'border-transparent'}`}
              style={{ backgroundColor: c.value }} />
          ))}
          <label className="flex items-center gap-1 text-[11px] text-[#605e5c] cursor-pointer" title="Otro color">
            <input type="color" value={color} onChange={(e) => setColor(e.target.value)} className="w-6 h-6 p-0 border-0 bg-transparent cursor-pointer" />
            Otro
          </label>
        </div>
        <div className="mt-3 flex items-center gap-2">
          <span className="inline-flex items-center px-2 h-[18px] rounded-[3px] text-[11px] font-medium text-white" style={{ backgroundColor: color }}>
            {nombre.trim() || 'Vista previa'}
          </span>
        </div>
        {error && <p className="text-[12px] text-[#d13438] mt-2">{error}</p>}
        <div className="flex justify-end gap-2 mt-4">
          <button type="button" onClick={onCerrar}
            className="px-3 py-1.5 text-[13px] rounded border border-[#c8c6c4] text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#333]">
            Cancelar
          </button>
          <button type="button" onClick={guardar} disabled={guardando}
            className="px-3 py-1.5 text-[13px] rounded bg-[#0078d4] text-white hover:bg-[#106ebe] disabled:opacity-50">
            {guardando ? 'Guardando…' : 'Guardar'}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
