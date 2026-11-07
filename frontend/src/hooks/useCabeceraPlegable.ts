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
// Altura aproximada que gana el cuerpo al plegar la cabecera (remitente, destinatarios, botones).
// Si el contenido no sobresale al menos esto, plegar deja el cuerpo sin desplazamiento: el navegador
// lo devuelve a 0, eso vuelve a desplegar la cabecera y el correo «rebota y regresa arriba» en bucle
// (invitaciones y correos cortos en pantallas altas, 06/11/2026). En ese caso no se pliega.
const MARGEN_PLEGADO = 240;
// Tras plegar, los eventos de scroll de los siguientes ms son del reajuste del navegador, no del usuario.
const IGNORAR_TRAS_PLEGAR_MS = 400;

export function useCabeceraPlegable(claveMensaje: string | number | undefined) {
  const [plegada, setPlegada] = useState(false);
  const previoRef = useRef(0);

  // Cada mensaje empieza con la cabecera completa.
  useEffect(() => { setPlegada(false); previoRef.current = 0; }, [claveMensaje]);

  const plegadaEnRef = useRef(0);

  const onScroll = useCallback((e: React.UIEvent<HTMLElement>) => {
    const el = e.currentTarget;
    const y = el.scrollTop;
    const previo = previoRef.current;
    previoRef.current = y;
    const sobra = el.scrollHeight - el.clientHeight;
    if (previo < PLEGAR_A_PARTIR_DE && y >= PLEGAR_A_PARTIR_DE) {
      if (sobra < PLEGAR_A_PARTIR_DE + MARGEN_PLEGADO) return;
      plegadaEnRef.current = Date.now();
      setPlegada(true);
    } else if (previo >= DESPLEGAR_ANTES_DE && y < DESPLEGAR_ANTES_DE) {
      if (Date.now() - plegadaEnRef.current < IGNORAR_TRAS_PLEGAR_MS) return;
      setPlegada(false);
    }
  }, []);

  const alternar = useCallback(() => setPlegada(p => !p), []);

  return { plegada, alternar, onScroll };
}
