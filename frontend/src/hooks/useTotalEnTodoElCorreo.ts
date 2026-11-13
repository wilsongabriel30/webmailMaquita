/**
 * ¿Cuántos correos hay con esta búsqueda en TODAS las carpetas?
 *
 * La búsqueda normal mira solo la carpeta abierta. Medido con las búsquedas reales de una semana,
 * en 9 de cada 10 había más resultados en otras carpetas (sobre todo en Enviados) y la persona no
 * lo sabía. Este gancho pregunta el total en todo el correo, sin estorbar: espera a que la carpeta
 * haya respondido, descarta la respuesta si la búsqueda cambió y no repite la misma pregunta.
 */
import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { CARPETA_TODO } from '../lib/busquedaGlobal';
import type { MessagesResponse } from '../types';

const ESPERA_MS = 500;
const recordados = new Map<string, number>();

export function useTotalEnTodoElCorreo(consulta: string, activo: boolean): number | null {
  const texto = consulta.trim();
  // El dato se guarda junto a la búsqueda a la que responde: si la búsqueda cambia, deja de valer.
  const [dato, setDato] = useState<{ texto: string; total: number } | null>(null);

  useEffect(() => {
    if (!texto || !activo || recordados.has(texto)) return;
    let vigente = true;
    const reloj = setTimeout(() => {
      const p = new URLSearchParams({ page: '1', per_page: '1', search: texto });
      api.get<MessagesResponse>(`/mail/messages/${encodeURIComponent(CARPETA_TODO)}?${p}`)
        .then(r => {
          if (recordados.size > 50) recordados.clear();
          recordados.set(texto, r.total);
          if (vigente) setDato({ texto, total: r.total });
        })
        .catch(() => { /* sin el dato, el aviso se queda como estaba */ });
    }, ESPERA_MS);
    return () => { vigente = false; clearTimeout(reloj); };
  }, [texto, activo]);

  if (!texto) return null;
  if (dato && dato.texto === texto) return dato.total;
  return recordados.get(texto) ?? null;
}
