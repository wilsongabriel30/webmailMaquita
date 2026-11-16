// Valores para los campos «datetime-local» y «date» en la hora LOCAL del navegador.
//
// Esos campos no llevan zona horaria: lo que se les pone se lee como hora local. `toISOString()`
// devuelve la hora UTC, así que usarlo para rellenarlos adelantaba la propuesta cinco horas en
// Ecuador («Programar envío» a las 19:58 proponía la 01:58 del día siguiente; informe de Andes).
// Para guardar se hace el camino contrario con `new Date(valorDelCampo).toISOString()`.

const dos = (n: number) => String(n).padStart(2, '0');

/** «AAAA-MM-DD» del instante, en la hora local. Para `<input type="date">`. */
export function paraCampoFecha(instante: Date): string {
  return `${instante.getFullYear()}-${dos(instante.getMonth() + 1)}-${dos(instante.getDate())}`;
}

/** «AAAA-MM-DDTHH:MM» del instante, en la hora local. Para `<input type="datetime-local">`. */
export function paraCampoFechaHora(instante: Date): string {
  return `${paraCampoFecha(instante)}T${dos(instante.getHours())}:${dos(instante.getMinutes())}`;
}
