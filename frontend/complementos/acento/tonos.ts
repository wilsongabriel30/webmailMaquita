/**
 * Familia del color de acento del webmail (13/11/2026).
 *
 * El azul institucional y sus tonos derivados están escritos como valor fijo en cientos de sitios
 * (`bg-[#0078d4]`, `hover:bg-[#106ebe]`, `bg-[#deecf9]`…). En vez de tocar cada sitio, la compilación
 * sustituye cada tono por `var(--acento-…, <valor original>)`: sin preferencia elegida la variable no
 * existe y el navegador usa el valor original, de modo que todo se ve igual que antes.
 *
 * Cada tono se asigna a un escalón de la familia. Hay dos variables por escalón según para qué se usa:
 *   - relleno (fondos, casillas): `--acento-…`
 *   - trazo (texto, bordes, contornos, iconos): `--acento-…-trazo`
 * Así, en tema oscuro, el texto puede aclararse para leerse bien sin cambiar los fondos.
 */

/** Tono (hex en minúsculas, sin #) → escalón de la familia. */
export const TONOS: Record<string, string> = {
  '0078d4': 'acento',
  '106ebe': 'acento-oscuro', '0f6cbd': 'acento-oscuro',
  '005a9e': 'acento-mas-oscuro',
  '004578': 'acento-profundo',
  'deecf9': 'acento-claro', 'e8f4fd': 'acento-claro', 'e5f1fb': 'acento-claro', 'ebf3fc': 'acento-claro', 'e1f0ff': 'acento-claro',
  'eff6fc': 'acento-muy-claro', 'f0f6ff': 'acento-muy-claro', 'f3f9fd': 'acento-muy-claro', 'f5f9fd': 'acento-muy-claro', 'f0f6fc': 'acento-muy-claro',
  'c7e0f4': 'acento-borde', 'a6c8e8': 'acento-borde',
  // Tonos que solo usa el tema oscuro
  '0a84ff': 'acento-vivo', '2899f5': 'acento-vivo',
  '2b95ff': 'acento-vivo-claro', '4da3e8': 'acento-vivo-claro', '71afe5': 'acento-vivo-claro', '6cb6ff': 'acento-vivo-claro', '9cc9f0': 'acento-vivo-claro',
  '1a3a5c': 'acento-sombra', '264f78': 'acento-sombra', '2b4a66': 'acento-sombra',
  '1e3450': 'acento-sombra-profunda', '1a2a3e': 'acento-sombra-profunda', '1a2a3a': 'acento-sombra-profunda', '1f2a36': 'acento-sombra-profunda',
};

/** Propiedades CSS que se consideran «relleno»; el resto son «trazo». */
const RELLENO = new Set(['background', 'background-color', 'background-image', 'accent-color']);

export function esRelleno(propiedad: string): boolean {
  return RELLENO.has(propiedad) || propiedad.startsWith('--tw-gradient');
}

/** `backgroundColor` → `background-color`. */
export function enGuiones(propiedad: string): string {
  return propiedad.startsWith('--') ? propiedad : propiedad.replace(/[A-Z]/g, (m) => '-' + m.toLowerCase());
}

const HEX = /#([0-9a-f]{6})([0-9a-f]{2})?(?![0-9a-f])/gi;
const RGB = /rgba?\(\s*(\d{1,3})\s*[, ]\s*(\d{1,3})\s*[, ]\s*(\d{1,3})\s*(?:[,/]\s*(\d*\.?\d+)(%?)\s*)?\)/gi;
export const HAY_TONO = new RegExp(Object.keys(TONOS).join('|') + '|rgba?\\(\\s*\\d', 'i');

function referencia(hex: string, relleno: boolean): string | null {
  const escalon = TONOS[hex.toLowerCase()];
  if (!escalon) return null;
  return `var(--${escalon}${relleno ? '' : '-trazo'}, #${hex.toLowerCase()})`;
}

function conAlfa(ref: string, porcentaje: number): string {
  return `color-mix(in srgb, ${ref} ${Math.round(porcentaje * 100) / 100}%, transparent)`;
}

/**
 * Sustituye en el valor de una propiedad CSS los tonos de la familia por su variable.
 * Devuelve el mismo texto si no hay nada que cambiar.
 */
export function sustituirEnValor(valor: string, propiedad: string): string {
  if (valor.includes('var(--acento') || valor.includes('url(')) return valor;
  const relleno = esRelleno(enGuiones(propiedad));
  return valor
    .replace(HEX, (todo: string, rgb: string, alfa: string | undefined) => {
      const ref = referencia(rgb, relleno);
      if (!ref) return todo;
      return alfa ? conAlfa(ref, (parseInt(alfa, 16) / 255) * 100) : ref;
    })
    .replace(RGB, (todo: string, r: string, g: string, b: string, a: string | undefined, pct: string | undefined) => {
      const hex = [r, g, b].map((n) => Number(n).toString(16).padStart(2, '0')).join('');
      const ref = referencia(hex, relleno);
      if (!ref) return todo;
      if (a === undefined) return ref;
      return conAlfa(ref, pct ? Number(a) : Number(a) * 100);
    });
}
