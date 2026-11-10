import { useEffect, useRef } from 'react';

/**
 * Al pasar a «Conversaciones agrupadas» con un correo ya abierto, carga su hilo al momento; al
 * volver a «Mensajes individuales», lo quita. Antes el hilo solo se pedía al hacer clic en un correo
 * DESPUÉS de cambiar la vista, y parecía que «organizar por conversación» no hacía nada (10/11/2026).
 */
export function useHiloAlCambiarVista(
  viewMode: string,
  seleccionado: { uid: number; thread_id?: string } | null,
  cargarHilo: (threadId: string, uid: number) => void,
  limpiarHilo: () => void,
) {
  const previo = useRef(viewMode);
  useEffect(() => {
    if (previo.current === viewMode) return;
    previo.current = viewMode;
    if (viewMode === 'conversations') {
      if (seleccionado?.thread_id) cargarHilo(seleccionado.thread_id, seleccionado.uid);
    } else {
      limpiarHilo();
    }
  }, [viewMode, seleccionado, cargarHilo, limpiarHilo]);
}
