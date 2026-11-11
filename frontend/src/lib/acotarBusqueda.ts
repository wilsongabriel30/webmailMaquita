/**
 * Acotar una búsqueda con demasiados resultados (11/11/2026).
 *
 * Caso real: en una bandeja de 117 000 correos, buscar «luis» devolvía 27 529 resultados. El servidor ya
 * entiende `de:`, `asunto:`, `despues:AAAA-MM-DD` y `tiene:adjunto`, pero había que saber escribirlos.
 * Aquí se calculan las opciones que se ofrecen con un clic sobre la lista de resultados.
 */
export interface OpcionAcotar { clave: string; texto: string; consulta: string }

/** A partir de cuántos resultados se ofrece acotar. */
export const UMBRAL_ACOTAR = 100;

const CON_OPERADOR = /^[a-záéíóúñ-]+:/i;
const ES_REMITENTE = /^(de|from):/i;
const ES_ASUNTO = /^(asunto|subject):/i;
const ES_DESDE = /^(despues|después|after|entre|between):/i;
const ES_ADJUNTO = /^(tiene:adjunto|con:adjunto|adjunto:s[ií]|has:attachment)$/i;

/** Parte la consulta respetando las comillas: `de:"ana perez" factura` → [`de:"ana perez"`, `factura`]. */
export function trozos(consulta: string): string[] {
  return (consulta.match(/[^\s"]*"[^"]*"|\S+/g) || []).filter(Boolean);
}

function fechaISO(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function conValor(operador: string, palabras: string[]): string {
  const valor = palabras.join(' ');
  return /\s/.test(valor) ? `${operador}:"${valor.replace(/"/g, '')}"` : `${operador}:${valor}`;
}

export function opcionesParaAcotar(consulta: string, hoy: Date = new Date()): OpcionAcotar[] {
  const partes = trozos(consulta.trim());
  if (partes.length === 0) return [];
  const palabras = partes.filter((p) => !CON_OPERADOR.test(p));
  const operadores = partes.filter((p) => CON_OPERADOR.test(p));
  const opciones: OpcionAcotar[] = [];
  const unir = (...trozosNuevos: string[]) => trozosNuevos.filter(Boolean).join(' ');

  if (palabras.length > 0 && !operadores.some((o) => ES_REMITENTE.test(o) || ES_ASUNTO.test(o))) {
    const visible = palabras.join(' ');
    opciones.push({ clave: 'remitente', texto: `Solo enviados por «${visible}»`, consulta: unir(conValor('de', palabras), ...operadores) });
    opciones.push({ clave: 'asunto', texto: `Solo con «${visible}» en el asunto`, consulta: unir(conValor('asunto', palabras), ...operadores) });
  }
  if (!operadores.some((o) => ES_DESDE.test(o))) {
    const hace30 = new Date(hoy.getTime() - 30 * 24 * 3600 * 1000);
    opciones.push({ clave: 'mes', texto: 'Últimos 30 días', consulta: unir(consulta.trim(), `despues:${fechaISO(hace30)}`) });
    opciones.push({ clave: 'anio', texto: `Solo ${hoy.getFullYear()}`, consulta: unir(consulta.trim(), `despues:${hoy.getFullYear()}-01-01`) });
  }
  if (!operadores.some((o) => ES_ADJUNTO.test(o))) {
    opciones.push({ clave: 'adjunto', texto: 'Con adjuntos', consulta: unir(consulta.trim(), 'tiene:adjunto') });
  }
  return opciones;
}

/** La consulta sin operadores (para «Quitar filtros»); null si no tenía ninguno o si no quedaría nada. */
export function sinOperadores(consulta: string): string | null {
  const partes = trozos(consulta.trim());
  const palabras = partes.filter((p) => !CON_OPERADOR.test(p));
  if (palabras.length === partes.length || palabras.length === 0) return null;
  return palabras.join(' ');
}
