/**
 * Cabecera plegable del panel de lectura (pantallas bajas, 1366×768).
 *
 * Al desplazar el cuerpo del mensaje hacia abajo, la cabecera (remitente, destinatarios,
 * botones) se pliega y solo queda el asunto con un botón para desplegarla; al volver al
 * inicio se despliega sola. El botón permite abrirla o cerrarla a mano en cualquier momento.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

const PLEGAR_A_PARTIR_DE = 60;  // px de desplazamiento para plegar
const DESPLEGAR_ANTES_DE = 8;   // px: al volver arriba se despliega

export function useCabeceraPlegable(claveMensaje: string | number | undefined) {
  const [plegada, setPlegada] = useState(false);
  const previoRef = useRef(0);

  // Cada mensaje empieza con la cabecera completa.
  useEffect(() => { setPlegada(false); previoRef.current = 0; }, [claveMensaje]);

  const onScroll = useCallback((e: React.UIEvent<HTMLElement>) => {
    const y = e.currentTarget.scrollTop;
    const previo = previoRef.current;
    previoRef.current = y;
    if (previo < PLEGAR_A_PARTIR_DE && y >= PLEGAR_A_PARTIR_DE) setPlegada(true);
    else if (previo >= DESPLEGAR_ANTES_DE && y < DESPLEGAR_ANTES_DE) setPlegada(false);
  }, []);

  const alternar = useCallback(() => setPlegada(p => !p), []);

  return { plegada, alternar, onScroll };
}
