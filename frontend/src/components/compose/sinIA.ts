/**
 * Un solo comportamiento para todos los botones de IA del redactor (informe de Andes, 15/11/2026).
 *
 * Sin IA configurada cada botón respondía distinto: uno decía «IA ocupada», otro abría la vista previa
 * vacía y otro daba un 404. Ahora los botones no se pintan (ver `useIADisponible`) y, si la acción llega
 * por otra vía (un evento de la barra, o antes de saberse si hay IA), todos dan este mismo aviso.
 */
import { showToast } from '../common/Toast';
import { AVISO_SIN_IA, hayIA } from '../asistente-lateral/iaDisponible';

/** Hay IA, pero esta vez no contestó (ocupada, caída o respuesta no válida). */
export const AVISO_IA_SIN_RESPUESTA = 'El asistente de IA no respondió. Inténtelo de nuevo en unos segundos.';

/** true (y avisa) si la instalación no tiene IA: quien llama no sigue. */
export async function avisarSiNoHayIA(): Promise<boolean> {
  if (await hayIA()) return false;
  showToast(AVISO_SIN_IA);
  return true;
}
