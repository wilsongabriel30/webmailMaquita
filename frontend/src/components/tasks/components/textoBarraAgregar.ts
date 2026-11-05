// Textos de las pastillas de la barra para agregar tareas, como en To Do: «Hoy», «Mañana», «vie, 7 nov»
// para el vencimiento y «8:30, Hoy» para el recordatorio (hora local, 24 h, sin cero a la izquierda).

function diaLocal(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/** Día local de hoy + n, como «AAAA-MM-DD». */
export function diaMas(n: number, ahora = new Date()): string {
  const d = new Date(ahora);
  d.setDate(d.getDate() + n);
  return diaLocal(d);
}

/** «Hoy», «Mañana», «Ayer» o «vie, 7 nov» (con el año si no es el actual). */
export function textoDia(fecha: string, ahora = new Date()): string {
  if (fecha === diaMas(0, ahora)) return 'Hoy';
  if (fecha === diaMas(1, ahora)) return 'Mañana';
  if (fecha === diaMas(-1, ahora)) return 'Ayer';
  const d = new Date(fecha + 'T12:00:00');
  const opciones: Intl.DateTimeFormatOptions = { weekday: 'short', day: 'numeric', month: 'short' };
  if (d.getFullYear() !== ahora.getFullYear()) opciones.year = 'numeric';
  return d.toLocaleDateString('es-ES', opciones).replace(/\./g, '');
}

/** Vencimiento («AAAA-MM-DD») para la pastilla. */
export function textoVencimiento(fecha: string, ahora = new Date()): string {
  return fecha ? textoDia(fecha, ahora) : '';
}

/** Recordatorio (ISO) para la pastilla: «8:30, Hoy». */
export function textoRecordatorio(iso: string, ahora = new Date()): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return `${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}, ${textoDia(diaLocal(d), ahora)}`;
}
