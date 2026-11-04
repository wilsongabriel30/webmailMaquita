// Fechas como las escribe una persona: «09:30», «Ayer 15:30», «lun 14:20», «3 nov».
//
// La lista usaba «alrededor de 14 horas» (formatDistanceToNow) para todo lo de la última semana:
// obliga a hacer cuentas para saber si un correo es de ayer o de anteayer. Zimbra mostraba la
// hora o la fecha, y así se vuelve a hacer.

const DIA_MS = 86400000;

function hora(d: Date): string {
  return d.toLocaleTimeString('es-EC', { hour: '2-digit', minute: '2-digit', hour12: false });
}

function inicioDelDia(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

/** Fecha corta para la lista de correos. */
export function fechaCortaLista(d: Date, ahora: Date = new Date()): string {
  const dias = Math.round((inicioDelDia(ahora) - inicioDelDia(d)) / DIA_MS);
  if (dias <= 0) return hora(d);
  if (dias === 1) return `Ayer ${hora(d)}`;
  if (dias < 7) {
    const dia = d.toLocaleDateString('es-EC', { weekday: 'short' }).replace('.', '');
    return `${dia} ${hora(d)}`;
  }
  if (d.getFullYear() === ahora.getFullYear()) {
    return d.toLocaleDateString('es-EC', { day: 'numeric', month: 'short' }).replace('.', '');
  }
  return d.toLocaleDateString('es-EC', { day: 'numeric', month: 'short', year: 'numeric' }).replace('.', '');
}
