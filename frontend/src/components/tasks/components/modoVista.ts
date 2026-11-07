// Vista elegida en Tareas («Cuadrícula» o «Lista»): se recuerda en este navegador.
export type ModoVista = 'cuadricula' | 'lista';

const CLAVE = 'tareas-modo-vista';

export function leerModoVista(): ModoVista {
  try { return localStorage.getItem(CLAVE) === 'lista' ? 'lista' : 'cuadricula'; } catch { return 'cuadricula'; }
}

export function guardarModoVista(m: ModoVista) {
  try { localStorage.setItem(CLAVE, m); } catch { /* sin almacenamiento: solo dura esta sesión */ }
}
