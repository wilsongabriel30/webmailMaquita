/**
 * Nombres de las direcciones internas (06/11/2026).
 *
 * Las personas se muestran por su NOMBRE, no por la dirección. Orden de preferencia:
 *   1. el nombre que la persona guardó en SUS contactos (agenda),
 *   2. el directorio de la organización (buzones, listas, contactos institucionales),
 *   3. el nombre que trae el propio correo (Outlook a veces pone solo la dirección o un
 *      cargo como «Analista Planificación y Procesos»).
 * Se usa /contacts/search (ya busca en ese orden). Se guarda en memoria mientras dure la
 * sesión y se consultan pocas direcciones a la vez.
 */
import { useEffect, useState } from 'react';
import { api } from '../api/client';

interface Sugerencia { email: string; name?: string; display_name?: string; source?: string }

const cache = new Map<string, string | null>();
const enEspera = new Map<string, Array<() => void>>();
const cola: string[] = [];
let activas = 0;
const SIMULTANEAS = 4;

async function consultar(correo: string): Promise<string | null> {
  try {
    const r = await api.get<{ contacts: Sugerencia[] }>(
      `/contacts/search?q=${encodeURIComponent(correo)}&limit=15`);
    for (const e of r?.contacts ?? []) {
      if ((e.email || '').toLowerCase() !== correo) continue;
      const n = (e.name || e.display_name || '').trim().replace(/\s+/g, ' ');
      if (n && !n.includes('@')) return n;
    }
    return null;
  } catch {
    return null;
  }
}

function avanzar(): void {
  while (activas < SIMULTANEAS && cola.length) {
    const correo = cola.shift()!;
    activas++;
    consultar(correo).then(nombre => {
      cache.set(correo, nombre);
      (enEspera.get(correo) ?? []).forEach(f => f());
      enEspera.delete(correo);
    }).finally(() => { activas--; avanzar(); });
  }
}

function solicitar(correo: string, listo: () => void): void {
  const lista = enEspera.get(correo);
  if (lista) { lista.push(listo); return; }
  enEspera.set(correo, [listo]);
  cola.push(correo);
  avanzar();
}

/** Separa «Nombre <correo>», «<correo>» o «correo» en nombre (puede ir vacío) y correo. */
export function partirDireccion(texto: string): { nombre: string; correo: string } {
  const t = texto.trim();
  const m = t.match(/^"?([^"<]*?)"?\s*<([^>]+)>\s*$/);
  if (m) {
    const nombre = m[1].trim();
    const correo = m[2].trim();
    return { nombre: nombre.toLowerCase() === correo.toLowerCase() ? '' : nombre, correo };
  }
  return { nombre: '', correo: t.replace(/^<|>$/g, '') };
}

/** Nombre conocido para una dirección (null mientras se consulta o si no se conoce). */
export function useNombreCorreo(correo: string, necesario = true): string | null {
  const clave = correo.trim().toLowerCase();
  const [, refrescar] = useState(0);
  useEffect(() => {
    if (!necesario || !clave.includes('@') || cache.has(clave)) return;
    let vivo = true;
    solicitar(clave, () => { if (vivo) refrescar(n => n + 1); });
    return () => { vivo = false; };
  }, [clave, necesario]);
  return necesario ? cache.get(clave) ?? null : null;
}
