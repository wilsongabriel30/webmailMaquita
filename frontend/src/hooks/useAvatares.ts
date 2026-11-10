/**
 * useAvatares — nombre, iniciales y foto de una dirección vía GET /contacts/avatars (09/11/2026).
 *
 * Caché en memoria mientras dure la sesión y agrupación de peticiones: las direcciones que se
 * piden en el mismo instante (una lista de 50 correos, un hilo) salen en UNA sola llamada, y una
 * dirección ya conocida no se vuelve a pedir. Lo comparten el correo abierto, el hilo y la lista
 * para no duplicar llamadas (regla de conexiones lentas: pocas peticiones).
 */
import { useEffect, useState } from 'react';
import { api } from '../api/client';

export interface Avatar { name: string; initials: string; photo_url?: string }

const cache = new Map<string, Avatar>();
const oyentes = new Map<string, Set<() => void>>();
let pendientes = new Set<string>();
let temporizador: ReturnType<typeof setTimeout> | null = null;
const LOTE = 200;
const ESPERA_MS = 30;

function avisar(correo: string): void {
  oyentes.get(correo)?.forEach(f => f());
  oyentes.delete(correo);
}

async function enviarLote(): Promise<void> {
  temporizador = null;
  const correos = Array.from(pendientes);
  pendientes = new Set();
  for (let i = 0; i < correos.length; i += LOTE) {
    const trozo = correos.slice(i, i + LOTE);
    try {
      const datos = await api.get<Record<string, Avatar>>(
        `/contacts/avatars?emails=${encodeURIComponent(trozo.join(','))}`);
      for (const c of trozo) {
        cache.set(c, datos?.[c] ?? { name: '', initials: '' });
        avisar(c);
      }
    } catch {
      // Sin red: se dejan sin resolver para intentarlo en la próxima petición.
      for (const c of trozo) avisar(c);
    }
  }
}

function pedir(correo: string, listo: () => void): void {
  let s = oyentes.get(correo);
  if (!s) { s = new Set(); oyentes.set(correo, s); }
  s.add(listo);
  pendientes.add(correo);
  if (!temporizador) temporizador = setTimeout(enviarLote, ESPERA_MS);
}

/** Avatar conocido para una dirección (undefined mientras se consulta). */
export function avatarEnCache(correo: string): Avatar | undefined {
  return cache.get(correo.trim().toLowerCase());
}

/** Pide (si hace falta) y devuelve el avatar de UNA dirección. */
export function useAvatar(correo: string): Avatar | undefined {
  const clave = (correo || '').trim().toLowerCase();
  const [, refrescar] = useState(0);
  useEffect(() => {
    if (!clave.includes('@') || cache.has(clave)) return;
    let vivo = true;
    const listo = () => { if (vivo) refrescar(n => n + 1); };
    pedir(clave, listo);
    return () => { vivo = false; oyentes.get(clave)?.delete(listo); };
  }, [clave]);
  return clave ? cache.get(clave) : undefined;
}

/** Pide (si hace falta) los avatares de varias direcciones y devuelve el mapa conocido. */
export function useAvatares(correos: string[]): Record<string, Avatar> {
  const claves = correos.map(c => (c || '').trim().toLowerCase()).filter(c => c.includes('@'));
  const firma = claves.join(',');
  const [, refrescar] = useState(0);
  useEffect(() => {
    const faltan = Array.from(new Set(claves.filter(c => !cache.has(c))));
    if (!faltan.length) return;
    let vivo = true;
    const listo = () => { if (vivo) refrescar(n => n + 1); };
    faltan.forEach(c => pedir(c, listo));
    return () => { vivo = false; faltan.forEach(c => oyentes.get(c)?.delete(listo)); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [firma]);
  const salida: Record<string, Avatar> = {};
  for (const c of claves) { const a = cache.get(c); if (a) salida[c] = a; }
  return salida;
}

/** Olvida una dirección (p. ej. la propia tras cambiar la foto) para que se vuelva a pedir. */
export function olvidarAvatar(correo: string): void {
  cache.delete((correo || '').trim().toLowerCase());
}
