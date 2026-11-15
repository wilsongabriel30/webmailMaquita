/**
 * Apariencia del correo elegida por la persona (Configuración → Apariencia, 13/11/2026).
 *
 * Preferencias (se guardan en el navegador y siguen a la cuenta: lib/preferenciasCuenta.ts):
 *   - `maquita_acento`: color principal. Uno de los `id` de lib/aparienciaColores.ts
 *     (`institucional`, `verde`, `turquesa`, `morado`, `magenta`, `rojo`, `naranja`, `pizarra`).
 *   - `maquita_tema`: `claro`, `oscuro` o `equipo` (store/themeStore.ts).
 *   - `maquita_escala_elegida`: `80`, `90`, `100` o `110` (lib/escala.ts).
 *
 * El color se aplica definiendo en <html> las variables `--acento-…` que la compilación dejó en el
 * CSS. Solo se aplica con la sesión abierta: la página de ingreso se queda con el aspecto institucional.
 */
import '../estilos/apariencia.css';
import { ACENTO_INSTITUCIONAL, VARIABLES_ACENTO, colorAcento, variablesDeAcento } from './aparienciaColores';

export const CLAVE_ACENTO = 'maquita_acento';

/** Color principal guardado en este navegador («institucional» si no hay ninguno o no es válido). */
export function acentoElegido(): string {
  try { return colorAcento(localStorage.getItem(CLAVE_ACENTO)).id; } catch { return ACENTO_INSTITUCIONAL; }
}

/** Pone (o quita, si es el institucional) las variables del color en la página. */
export function aplicarAcento(id: string, oscuro: boolean) {
  const estilo = document.documentElement.style;
  const variables = variablesDeAcento(id, oscuro);
  for (const nombre of VARIABLES_ACENTO) {
    if (nombre in variables) estilo.setProperty(nombre, variables[nombre]);
    else estilo.removeProperty(nombre);
  }
}

/** Vuelve al aspecto institucional en pantalla, sin tocar lo guardado (p. ej. al cerrar la sesión). */
export function quitarAcento() {
  aplicarAcento(ACENTO_INSTITUCIONAL, false);
}

/** Guarda el color elegido y lo aplica al momento. */
export function elegirAcento(id: string, oscuro: boolean) {
  const valido = colorAcento(id).id;
  try { localStorage.setItem(CLAVE_ACENTO, valido); } catch { /* sin almacenamiento: vale para esta visita */ }
  aplicarAcento(valido, oscuro);
}
