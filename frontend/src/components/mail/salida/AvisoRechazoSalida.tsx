/**
 * AvisoRechazoSalida.tsx — Aviso cuando un correo de la cola no puede salir (24/11/2026).
 *
 * Antes lo mostraba la ventana emergente de la bandeja de salida. Ahora que la bandeja es una
 * carpeta, este componente (siempre montado, sin interfaz propia) escucha el rechazo y muestra un
 * aviso fijo con un botón «Ver» que lleva a la carpeta Bandeja de salida.
 */
import { useEffect } from 'react';
import { showToast } from '../../common/Toast';
import { avisoDeRechazo } from '../../../lib/colaSalidaLegible';
import { useMailStore } from '../../../store/mailStore';
import { CARPETA_SALIDA } from '../../../lib/carpetaSalida';

export function AvisoRechazoSalida() {
  useEffect(() => {
    const rechazo = (ev: Event) => {
      const d = (ev as CustomEvent<{ asunto?: string; mensaje?: string }>).detail || {};
      showToast(
        avisoDeRechazo(d.asunto, d.mensaje),
        { label: 'Ver', onClick: () => useMailStore.getState().setCurrentFolder(CARPETA_SALIDA) },
        { fijo: true, clave: 'outbox-rechazado' },
      );
    };
    window.addEventListener('outbox-rechazado', rechazo);
    return () => window.removeEventListener('outbox-rechazado', rechazo);
  }, []);
  return null;
}
