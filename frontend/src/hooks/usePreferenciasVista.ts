/**
 * Preferencias de «Vista» guardadas en la cuenta (11/11/2026).
 *
 * Antes vivían solo en el navegador: se perdían al entrar por otro navegador, otro equipo, la otra
 * dirección del webmail o tras reinstalar la aplicación. Además el panel de lectura «Rellenar pantalla»
 * y «Solo elementos emergentes» se guardaba en el servidor pero no se restauraba al entrar.
 *
 * Al entrar se aplica lo guardado en el servidor; cada cambio se guarda solo (1,5 s después).
 */
import { useEffect } from 'react';
import { api } from '../api/client';
import { useMailStore } from '../store/mailStore';

interface Vista {
  densidad?: string;
  lineas?: number;
  orden?: string;
  modo?: string;
  anchoLista?: number;
  anchoCarpetas?: number;
  coloresCarpetas?: Record<string, string>;
}

function vistaActual(): Vista {
  const s = useMailStore.getState();
  return {
    densidad: s.density, lineas: s.previewLines, orden: s.ordenFila, modo: s.viewMode,
    anchoLista: s.messageListWidth, anchoCarpetas: s.anchoCarpetas, coloresCarpetas: s.coloresCarpetas,
  };
}

function aplicar(v: Vista) {
  const s = useMailStore.getState();
  if (v.densidad === 'compact' || v.densidad === 'medium' || v.densidad === 'full' || v.densidad === 'linea') s.setDensity(v.densidad);
  if (v.lineas === 1 || v.lineas === 2 || v.lineas === 3) s.setPreviewLines(v.lineas);
  if (v.orden === 'asunto' || v.orden === 'remitente') s.setOrdenFila(v.orden);
  if (v.modo === 'conversations' || v.modo === 'messages') s.setViewMode(v.modo);
  if (typeof v.anchoLista === 'number') s.setMessageListWidth(v.anchoLista);
  if (typeof v.anchoCarpetas === 'number') s.setAnchoCarpetas(v.anchoCarpetas);
  if (v.coloresCarpetas && typeof v.coloresCarpetas === 'object') s.setColoresCarpetas(v.coloresCarpetas);
}

export function usePreferenciasVista() {
  useEffect(() => {
    let listo = false;
    let ultimo = '';
    let temporizador: number | undefined;
    const guardar = (texto: string) => { api.put('/settings', { vista: JSON.parse(texto) }).catch(() => { /* queda en este navegador */ }); };

    api.get<{ reading_pane?: string; vista?: Vista | null }>('/settings')
      .then((s) => {
        const rp = s?.reading_pane;
        if (rp === 'fullscreen' || rp === 'popout') useMailStore.getState().setReadingPane(rp);
        const guardada = s?.vista && typeof s.vista === 'object' ? s.vista : null;
        if (guardada && Object.keys(guardada).length > 0) aplicar(guardada);
        else guardar(JSON.stringify(vistaActual()));   // primera vez: sube lo que tenía este navegador
      })
      .catch(() => { /* sin servidor se sigue con lo del navegador */ })
      .finally(() => { ultimo = JSON.stringify(vistaActual()); listo = true; });

    const quitar = useMailStore.subscribe(() => {
      if (!listo) return;
      const ahora = JSON.stringify(vistaActual());
      if (ahora === ultimo) return;
      ultimo = ahora;
      window.clearTimeout(temporizador);
      temporizador = window.setTimeout(() => guardar(ahora), 1500);
    });
    return () => { quitar(); window.clearTimeout(temporizador); };
  }, []);
}
