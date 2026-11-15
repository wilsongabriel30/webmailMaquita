/**
 * Aplica el color principal elegido por la persona mientras la pantalla está abierta, y vuelve al
 * aspecto institucional al salir (así la página de ingreso nunca cambia de color).
 */
import { useEffect } from 'react';
import { useThemeStore } from '../store/themeStore';
import { acentoElegido, aplicarAcento, quitarAcento } from '../lib/apariencia';

/** `soloClaro`: pantallas que no tienen tema oscuro (ventana de redacción, correo en su pestaña). */
export function useApariencia(opciones?: { soloClaro?: boolean }) {
  const oscuro = useThemeStore((s) => s.dark) && !opciones?.soloClaro;
  useEffect(() => { aplicarAcento(acentoElegido(), oscuro); }, [oscuro]);
  useEffect(() => quitarAcento, []);
}
