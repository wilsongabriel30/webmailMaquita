/**
 * Aviso del tope de peticiones (429) cuando la lista de correos YA está en pantalla.
 *
 * Con la lista vacía el aviso ocupa su lugar (`AvisoErrorCarga`). Con correos a la vista no se quita
 * nada, pero tampoco se decía nada: la lista dejaba de actualizarse sin explicación (Andes, 15/11/2026).
 * Como el tope suele rechazar muchas peticiones seguidas, se avisa como mucho una vez cada medio minuto.
 */
import { showToast } from '../common/Toast';
import { esLimiteDePeticiones } from '../../api/errorApi';

const PAUSA_MS = 30_000;
let ultimoAviso = 0;

export const TEXTO_LIMITE_CON_LISTA =
  'Demasiadas acciones seguidas: la lista no se actualizó. Espere unos segundos; sus correos siguen en el servidor.';

/** true si tocaba avisar (y avisó). `ahora` solo existe para poder probarlo. */
export function avisarLimiteConLista(err: unknown, ahora: number = Date.now()): boolean {
  if (!esLimiteDePeticiones(err)) return false;
  if (ahora - ultimoAviso < PAUSA_MS) return false;
  ultimoAviso = ahora;
  showToast(TEXTO_LIMITE_CON_LISTA, undefined, { clave: 'limite-peticiones' });
  return true;
}
