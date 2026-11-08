/**
 * Carpetas favoritas de la barra lateral (07/11/2026, como Outlook).
 * Por defecto: Bandeja de entrada, Borradores y Enviados. La persona agrega o quita cualquiera
 * con la ⭐ de la cabecera de la lista o con clic derecho → «Agregar a Favoritos».
 * Todas las carpetas siguen también en la sección «Carpetas»; Favoritos es solo un acceso rápido.
 * Se recuerdan en este navegador (comodidad: si se pierden, solo hay que volver a marcarlas).
 */
import { useEffect, useState } from 'react';

export const FAVORITAS_POR_DEFECTO = ['INBOX', 'Drafts', 'Sent'];
const CLAVE = 'webmail.carpetasFavoritas.v2';
const EVENTO = 'carpetas-favoritas';

export function leerFavoritas(): string[] {
  try {
    const crudo = localStorage.getItem(CLAVE);
    if (crudo === null) return [...FAVORITAS_POR_DEFECTO];
    const v = JSON.parse(crudo);
    return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : [...FAVORITAS_POR_DEFECTO];
  } catch { return [...FAVORITAS_POR_DEFECTO]; }
}

export function esFavorita(carpeta: string): boolean {
  return leerFavoritas().includes(carpeta);
}

/** Agrega o quita la carpeta. Devuelve true si quedó como favorita. */
export function alternarFavorita(carpeta: string): boolean {
  const actuales = leerFavoritas();
  const ya = actuales.includes(carpeta);
  const nuevas = ya ? actuales.filter(c => c !== carpeta) : [...actuales, carpeta];
  try { localStorage.setItem(CLAVE, JSON.stringify(nuevas)); } catch { /* sin almacenamiento: no se recuerda */ }
  window.dispatchEvent(new CustomEvent(EVENTO));
  return !ya;
}

export function useCarpetasFavoritas(): string[] {
  const [lista, setLista] = useState<string[]>(leerFavoritas);
  useEffect(() => {
    const al = () => setLista(leerFavoritas());
    window.addEventListener(EVENTO, al);
    window.addEventListener('storage', al);
    return () => { window.removeEventListener(EVENTO, al); window.removeEventListener('storage', al); };
  }, []);
  return lista;
}
