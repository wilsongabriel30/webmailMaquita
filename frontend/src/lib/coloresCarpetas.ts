/**
 * Colores de las carpetas (11/11/2026, pedido de varias personas).
 *
 * Cada persona puede pintar sus carpetas: clic derecho → «Color de la carpeta». El color se guarda en la
 * cuenta junto con las demás preferencias de «Vista» (hooks/usePreferenciasVista.ts), así que se ve igual
 * en cualquier navegador o equipo. La clave es el nombre completo de la carpeta en el servidor.
 */
export interface ColorCarpeta { valor: string; nombre: string }

export const PALETA_CARPETAS: ColorCarpeta[] = [
  { valor: '#d13438', nombre: 'Rojo' },
  { valor: '#ca5010', nombre: 'Naranja' },
  { valor: '#c19c00', nombre: 'Amarillo' },
  { valor: '#107c10', nombre: 'Verde' },
  { valor: '#038387', nombre: 'Turquesa' },
  { valor: '#0078d4', nombre: 'Azul' },
  { valor: '#5c2e91', nombre: 'Morado' },
  { valor: '#c239b3', nombre: 'Rosa' },
  { valor: '#8e562e', nombre: 'Café' },
  { valor: '#69797e', nombre: 'Gris' },
];

const HEX = /^#[0-9a-f]{6}$/i;

/** Solo colores #rrggbb y nombres razonables: lo que llega del servidor o del navegador no se da por bueno. */
export function coloresValidos(crudo: unknown): Record<string, string> {
  const limpio: Record<string, string> = {};
  if (!crudo || typeof crudo !== 'object') return limpio;
  for (const [carpeta, color] of Object.entries(crudo as Record<string, unknown>)) {
    if (typeof color === 'string' && HEX.test(color) && carpeta.length > 0 && carpeta.length <= 255) limpio[carpeta] = color.toLowerCase();
    if (Object.keys(limpio).length >= 500) break;
  }
  return limpio;
}

/** Al renombrar o mover una carpeta, su color (y el de sus subcarpetas) la acompaña. */
export function renombrarEnColores(colores: Record<string, string>, viejo: string, nuevo: string): Record<string, string> {
  const salida: Record<string, string> = {};
  for (const [carpeta, color] of Object.entries(colores)) {
    if (carpeta === viejo) salida[nuevo] = color;
    else if (carpeta.startsWith(viejo + '.')) salida[nuevo + carpeta.slice(viejo.length)] = color;
    else salida[carpeta] = color;
  }
  return salida;
}

/** Al borrar una carpeta se olvida su color y el de sus subcarpetas. */
export function quitarDeColores(colores: Record<string, string>, carpeta: string): Record<string, string> {
  const salida: Record<string, string> = {};
  for (const [c, color] of Object.entries(colores)) {
    if (c !== carpeta && !c.startsWith(carpeta + '.')) salida[c] = color;
  }
  return salida;
}
