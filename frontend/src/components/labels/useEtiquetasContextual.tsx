/**
 * useEtiquetasContextual — submenú «Etiquetas» del clic derecho en la lista (05/11/2026).
 * Devuelve el elemento de menú para un correo y el diálogo de «Nueva etiqueta…» ya montado.
 */
import { useCallback, useEffect, useState } from 'react';
import type { MenuItem } from '../common/ContextMenu';
import { showToast } from '../common/Toast';
import { useLabels } from '../../hooks/useLabels';
import { carpetaEtiquetable, AVISO_SIN_ETIQUETAS_EN_TODO } from '../../lib/carpetaReal';
import { asignarEtiquetaA, type CorreoRef } from './asignarEtiquetas';
import { DialogoEtiqueta } from './DialogoEtiqueta';

export const ICONO_ETIQUETA = 'M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z';

export function useEtiquetasContextual(carpetaActual: string) {
  const { labels, fetchLabels, createLabel } = useLabels();
  const [nuevaPara, setNuevaPara] = useState<CorreoRef | null>(null);

  useEffect(() => { if (labels.length === 0) fetchLabels(); }, [labels.length, fetchLabels]);

  const alternar = useCallback(async (msg: CorreoRef, labelId: number, tenia: boolean) => {
    try {
      const r = await asignarEtiquetaA(labelId, [msg], carpetaActual, tenia);
      if (r.omitidos) showToast(AVISO_SIN_ETIQUETAS_EN_TODO);
    } catch { showToast('No se pudo cambiar la etiqueta'); }
  }, [carpetaActual]);

  const itemMenu = useCallback((msg: CorreoRef, asignadas: { id: number | string }[]): MenuItem => {
    if (!carpetaEtiquetable(msg, carpetaActual)) {
      return { label: 'Etiquetas (abre la carpeta del correo)', icon: ICONO_ETIQUETA, disabled: true, onClick: () => {} };
    }
    const ids = new Set(asignadas.map((a) => Number(a.id)));
    const hijos: MenuItem[] = labels.map((l) => ({
      label: `${ids.has(l.id) ? '✓ ' : ''}${l.name}`,
      onClick: () => { void alternar(msg, l.id, ids.has(l.id)); },
    }));
    hijos.push({ label: '', onClick: () => {}, divider: true });
    hijos.push({ label: 'Nueva etiqueta…', icon: 'M12 4v16m8-8H4', onClick: () => setNuevaPara(msg) });
    return { label: 'Etiquetas', icon: ICONO_ETIQUETA, onClick: () => {}, children: hijos };
  }, [labels, carpetaActual, alternar]);

  const dialogo = (
    <DialogoEtiqueta abierto={!!nuevaPara} onCerrar={() => setNuevaPara(null)}
      onGuardar={async (nombre, color) => {
        const nueva = await createLabel(nombre, color);
        if (nuevaPara) await asignarEtiquetaA(nueva.id, [nuevaPara], carpetaActual);
        showToast(`Etiqueta «${nombre}» creada`);
      }} />
  );

  return { itemMenu, dialogo };
}
