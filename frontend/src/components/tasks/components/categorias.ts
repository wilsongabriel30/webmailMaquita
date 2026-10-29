// Categorías de una tarea (como en Outlook): las seis de color. Se guardan por su nombre en `labels` de la tarea;
// una etiqueta que no es de estas (de tableros antiguos) se muestra en gris.
export const CATEGORIAS = [
  { nombre: 'Categoría roja', color: '#e74856', fondo: '#fde7e9' },
  { nombre: 'Categoría naranja', color: '#f7630c', fondo: '#fdeadf' },
  { nombre: 'Categoría amarilla', color: '#c19c00', fondo: '#fff4ce' },
  { nombre: 'Categoría verde', color: '#16c60c', fondo: '#dff6dd' },
  { nombre: 'Categoría azul', color: '#0078d4', fondo: '#deecf9' },
  { nombre: 'Categoría morada', color: '#8764b8', fondo: '#efe8f7' },
] as const;

export function colorCategoria(nombre: string): { color: string; fondo: string } {
  const c = CATEGORIAS.find(x => x.nombre === nombre);
  return c ? { color: c.color, fondo: c.fondo } : { color: '#605e5c', fondo: '#edebe9' };
}
