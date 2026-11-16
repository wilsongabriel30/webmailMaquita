/**
 * Error de una respuesta del servidor, con su código de estado.
 *
 * Antes el cliente lanzaba un `Error` solo con el texto, y quien lo recibía no podía distinguir un
 * «demasiadas peticiones» (429) de un fallo de red: la lista de correos decía «Revise la conexión»
 * cuando la conexión estaba bien (informe de Andes, 15/11/2026).
 */
export class ErrorApi extends Error {
  readonly status: number;

  constructor(mensaje: string, status: number) {
    super(mensaje);
    this.name = 'ErrorApi';
    this.status = status;
  }
}

/** El servidor rechazó la petición por el tope de peticiones seguidas (429). */
export function esLimiteDePeticiones(err: unknown): boolean {
  return err instanceof ErrorApi && err.status === 429;
}
