// Nombre de una lista con emoji al inicio (como en To Do): el emoji hace de ícono de la lista.
const EMOJI_INICIAL = /^(\p{Extended_Pictographic}(?:️|‍\p{Extended_Pictographic}|\p{Emoji_Modifier})*)\s*/u;

export function separarEmoji(nombre: string): { emoji: string; texto: string } {
  const m = nombre.match(EMOJI_INICIAL);
  if (!m) return { emoji: '', texto: nombre };
  const texto = nombre.slice(m[0].length);
  return { emoji: m[1], texto: texto || nombre };
}

/** Color elegido para la lista, o null si sigue con el gris de fábrica. */
export function colorDeLista(color?: string): string | null {
  return color && color.toLowerCase() !== '#e0e0e0' ? color : null;
}
