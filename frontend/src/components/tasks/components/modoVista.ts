// Vista elegida en Tareas («Cuadrícula», «Lista» o «Tablero», 09/11/2026): se recuerda en este navegador.
export type ModoVista = 'cuadricula' | 'lista' | 'tablero';

const CLAVE = 'tareas-modo-vista';

export function leerModoVista(): ModoVista {
  try {
    const v = localStorage.getItem(CLAVE);
    return v === 'lista' || v === 'tablero' ? v : 'cuadricula';
  } catch { return 'cuadricula'; }
}

export function guardarModoVista(m: ModoVista) {
  try { localStorage.setItem(CLAVE, m); } catch { /* sin almacenamiento: solo dura esta sesión */ }
}
