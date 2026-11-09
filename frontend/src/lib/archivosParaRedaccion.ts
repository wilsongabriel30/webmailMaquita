/**
 * Archivos que esperan a la próxima ventana de redacción (09/11/2026).
 *
 * Caso: se firma un PDF desde el visor y se pulsa «Responder con el PDF firmado». Quien
 * abre la respuesta es MessageView (con su cita, destinatarios, etc.); el editor se monta
 * después, así que no se le puede pasar el archivo por evento (todavía no escucha). Se deja
 * aquí y ComposePanel lo recoge al montarse. Sin BD ni red: una cola en memoria de la pestaña.
 */
let pendientes: File[] = [];

export function dejarArchivosParaRedaccion(archivos: File[]): void {
  pendientes = [...pendientes, ...archivos];
}

export function tomarArchivosParaRedaccion(): File[] {
  const lista = pendientes;
  pendientes = [];
  return lista;
}
