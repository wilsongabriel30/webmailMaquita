// Modos del asistente de redacción (los mismos que entiende /api/ia/redactar/stream en VM 170).
export type ModoRedaccion = 'ortografia' | 'redaccion' | 'formal' | 'breve';

export const MODOS: { id: ModoRedaccion; etiqueta: string; detalle: string }[] = [
  { id: 'ortografia', etiqueta: 'Ortografía y puntuación', detalle: 'Corrige letras, tildes, puntos y comas; ordena en párrafos y viñetas sin cambiar lo que dice' },
  { id: 'redaccion', etiqueta: 'Mejorar redacción', detalle: 'Además hace las oraciones más claras y fluidas' },
  { id: 'formal', etiqueta: 'Más formal', detalle: 'Tono formal e institucional, de usted' },
  { id: 'breve', etiqueta: 'Más breve', detalle: 'Más corto y directo, sin perder datos' },
];

// La cinta abre la vista previa con este evento (detail.modo). «compose-improve-writing», el del
// botón «Mejorar redacción» de la barra principal, la abre en modo «redaccion».
export const EVENTO_REDACCION_IA = 'compose-redaccion-ia';

export function abrirRedaccionIA(modo: ModoRedaccion) {
  window.dispatchEvent(new CustomEvent(EVENTO_REDACCION_IA, { detail: { modo } }));
}
