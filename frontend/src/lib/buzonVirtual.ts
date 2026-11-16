/**
 * ¿Tiene este servidor el buzón virtual «Virtual.Todo» (buscar en todas las carpetas)?
 *
 * No todas las instalaciones lo tienen: es un ajuste aparte del servidor de correo. Sin él, pedir
 * `Virtual.Todo` responde 404, y como «Todas las carpetas» es el ámbito por defecto y la elección
 * se guarda, el buscador quedaba inutilizado («No se pudo cargar el correo»; informe de Andes,
 * 15/11/2026). El servidor lo dice en `/mail/search/capacidades` (`todas_las_carpetas`).
 *
 * Mientras no se sabe, cuenta como que NO existe: se busca en la carpeta abierta, que siempre
 * funciona. La última respuesta se recuerda en el navegador para no esconder y volver a mostrar el
 * selector en cada carga; se vuelve a preguntar una vez por carga de la aplicación.
 */
import { useEffect, useSyncExternalStore } from 'react';
import { api } from '../api/client';
import { ErrorApi } from '../api/errorApi';

const CLAVE = 'maquita_buzon_virtual';

function recordado(): boolean | null {
  try {
    const v = localStorage.getItem(CLAVE);
    return v === '1' ? true : v === '0' ? false : null;
  } catch { return null; }
}

let existe: boolean | null = recordado();
let pedido: Promise<void> | null = null;
const oyentes = new Set<() => void>();

function fijar(v: boolean) {
  if (existe === v) return;
  existe = v;
  try { localStorage.setItem(CLAVE, v ? '1' : '0'); } catch { /* sin almacenamiento */ }
  oyentes.forEach(f => f());
}

/** True solo si el servidor confirmó que el buzón virtual existe. */
export function hayBuzonVirtual(): boolean {
  return existe === true;
}

/** Avisa cuando cambia la respuesta. Devuelve la función para dejar de escuchar. */
export function alCambiarBuzonVirtual(f: () => void): () => void {
  oyentes.add(f);
  return () => { oyentes.delete(f); };
}

/** Pregunta al servidor (una vez por carga; si falla la red, se reintenta en la siguiente llamada). */
export function consultarBuzonVirtual(): Promise<void> {
  if (!pedido) {
    pedido = api.get<{ todas_las_carpetas?: boolean }>('/mail/search/capacidades')
      .then(r => fijar(r?.todas_las_carpetas === true))
      .catch(() => { pedido = null; });
  }
  return pedido;
}

/**
 * Una petición a `Virtual.Todo` respondió «no existe» (404): se deja de ofrecer en el acto.
 * Devuelve true si el error era ese, para que quien llama no lo trate como fallo de conexión.
 */
export function anotarSiNoHayBuzonVirtual(error: unknown): boolean {
  if (!(error instanceof ErrorApi) || error.status !== 404) return false;
  // Aunque ya constara como inexistente se avisa: quien esté en ese buzón debe salir de él.
  if (existe === false) oyentes.forEach(f => f());
  else fijar(false);
  return true;
}

/** Para componentes: se actualiza sola cuando llega la respuesta del servidor. */
export function useBuzonVirtual(): boolean {
  useEffect(() => { void consultarBuzonVirtual(); }, []);
  return useSyncExternalStore(alCambiarBuzonVirtual, hayBuzonVirtual);
}
