// Etiquetas de una lista de correos, agrupadas por su carpeta real (05/11/2026).
//
// Antes se pedían todas con la carpeta «actual»: en «Todo el correo» (Virtual.Todo) se mandaban
// uids virtuales y las 1.765 etiquetas migradas de Zimbra desaparecían al buscar en todo el correo.
import { cargarEtiquetasPorTandas } from './etiquetasPorTandas';
import { carpetaEtiquetable } from './carpetaReal';

export interface RefCorreo { folder?: string; uid: number }

/** Clave del mapa de etiquetas: el uid solo, salvo que el correo venga de otra carpeta. */
export function claveEtiquetas(msg: RefCorreo, carpetaActual: string): string {
  const f = msg.folder || carpetaActual;
  return f === carpetaActual ? String(msg.uid) : `${f}/${msg.uid}`;
}

export async function cargarEtiquetasDeMensajes<T>(
  mensajes: RefCorreo[],
  carpetaActual: string,
): Promise<Record<string, T[]>> {
  const porCarpeta = new Map<string, RefCorreo[]>();
  for (const m of mensajes) {
    const f = carpetaEtiquetable(m, carpetaActual);
    if (!f) continue; // buzón virtual: no hay uid real que consultar
    const lista = porCarpeta.get(f) || [];
    lista.push(m);
    porCarpeta.set(f, lista);
  }
  const resultado: Record<string, T[]> = {};
  for (const [carpeta, lista] of porCarpeta) {
    const mapa = await cargarEtiquetasPorTandas<T>(carpeta, lista.map((m) => m.uid));
    for (const m of lista) {
      const etiquetas = mapa[String(m.uid)];
      if (etiquetas && etiquetas.length) resultado[claveEtiquetas(m, carpetaActual)] = etiquetas;
    }
  }
  return resultado;
}
