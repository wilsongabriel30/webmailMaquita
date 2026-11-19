/**
 * ¿La cinta debe ser la barra reducida de teléfono? (pedido de Dirección, 19/11/2026)
 *
 * Una ventana angosta no es un teléfono: el correo dentro de la app de escritorio y la ventana
 * separada de un mensaje (~680 px) deben conservar la cinta de escritorio, con iconos Y nombres,
 * como el correo de escritorio al achicar la ventana. Lo que no quepa se alcanza desplazando la
 * cinta (flecha de la derecha): no se pierde ninguna acción.
 *
 * La barra de teléfono queda para pantallas realmente pequeñas (menos de 520 px) y para
 * dispositivos táctiles por debajo del ancho de tableta (un teléfono girado).
 */
import { useEffect, useState } from 'react';

const ANCHO_TELEFONO = 520;
const ANCHO_TABLETA = 768;

export function esCintaDeTelefono(ancho: number, tactil: boolean): boolean {
  if (ancho < ANCHO_TELEFONO) return true;
  if (ancho >= ANCHO_TABLETA) return false;
  return tactil;
}

function esTactil(): boolean {
  try {
    return window.matchMedia('(pointer: coarse)').matches;
  } catch {
    return false;
  }
}

export function useCintaDeTelefono(): boolean {
  const [telefono, setTelefono] = useState(() => esCintaDeTelefono(window.innerWidth, esTactil()));
  useEffect(() => {
    const medir = () => setTelefono(esCintaDeTelefono(window.innerWidth, esTactil()));
    window.addEventListener('resize', medir);
    return () => window.removeEventListener('resize', medir);
  }, []);
  return telefono;
}
