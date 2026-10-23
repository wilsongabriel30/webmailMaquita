import { useEffect, useState } from 'react';

/* Preferencia de la vista dividida (apagada por defecto, recordada en este navegador)
   y si la pantalla es lo bastante ancha para ofrecerla: en móvil no se ofrece. */

const CLAVE = 'almacen_vista_dividida';
const CONSULTA_ANCHA = '(min-width: 1024px)';

function leer(): boolean {
  try { return localStorage.getItem(CLAVE) === '1'; } catch { return false; }
}

export function useVistaDividida(): [boolean, (v: boolean) => void] {
  const [activa, setActiva] = useState(leer);
  const cambiar = (v: boolean) => {
    setActiva(v);
    try { localStorage.setItem(CLAVE, v ? '1' : '0'); } catch { /* sin almacenamiento: solo esta vez */ }
  };
  return [activa, cambiar];
}

export function usePantallaAncha(): boolean {
  const [ancha, setAncha] = useState(() => typeof window !== 'undefined' && !!window.matchMedia?.(CONSULTA_ANCHA).matches);
  useEffect(() => {
    const mq = window.matchMedia?.(CONSULTA_ANCHA);
    if (!mq) return;
    const alCambiar = () => setAncha(mq.matches);
    mq.addEventListener('change', alCambiar);
    return () => mq.removeEventListener('change', alCambiar);
  }, []);
  return ancha;
}
