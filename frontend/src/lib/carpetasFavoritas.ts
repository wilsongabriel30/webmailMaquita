/**
 * Carpetas favoritas elegidas con la ⭐ de la cabecera de la lista (07/11/2026, como Outlook).
 * Las carpetas del sistema siempre están en Favoritos; aquí se guardan las que añade la persona.
 * Se recuerdan en este navegador (comodidad: si se pierden, solo hay que volver a marcarlas).
 */
import { useEffect, useState } from 'react';

export const FAVORITAS_FIJAS = ['INBOX', 'Drafts', 'Sent', 'Junk', 'Trash'];
const CLAVE = 'webmail.carpetasFavoritas';
const EVENTO = 'carpetas-favoritas';

export function leerFavoritas(): string[] {
  try {
    const v = JSON.parse(localStorage.getItem(CLAVE) || '[]');
    return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : [];
  } catch { return []; }
}

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
