// Confirmaciones de los borrados que no tienen vuelta atrás desde la bandeja.
//
// Mover a la Papelera se puede corregir; borrar desde la Papelera o vaciar una carpeta, no.
// Quien viene de Zimbra espera que el programa pregunte antes de borrar para siempre, y un clic
// de más (icono al pasar el ratón, tecla Supr, menú contextual) no debe costarle el correo.
import { AVISO_ELIMINAR_CORREO } from './deepLinkCorreo';
import { getFolderDisplayName } from '../folders';

/** Solo estas carpetas se pueden vaciar de una vez: su contenido ya se descartó una vez. */
export const CARPETAS_VACIABLES = new Set(['Trash', 'Junk', 'Spam']);

export function esCarpetaVaciable(carpeta: string): boolean {
  return CARPETAS_VACIABLES.has(carpeta);
}

/** Pregunta antes de borrar definitivamente; devuelve true si la persona confirma. */
export function confirmarBorradoDefinitivo(cantidad = 1): boolean {
  const cuantos = cantidad > 1 ? `Se borrarán ${cantidad} correos.\n\n` : '';
  return window.confirm(cuantos + AVISO_ELIMINAR_CORREO);
}

/** Pregunta antes de vaciar una carpeta entera; devuelve true si la persona confirma. */
export function confirmarVaciado(carpeta: string): boolean {
  const nombre = getFolderDisplayName(carpeta);
  return window.confirm(
    `Se borrarán DEFINITIVAMENTE todos los correos de «${nombre}». No se podrán recuperar desde la bandeja.\n\n¿Desea continuar?`,
  );
}
