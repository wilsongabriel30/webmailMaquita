// Ctrl+clic (Cmd+clic en Mac) sobre una fila de la lista: suma o quita ese correo de la selección.
//
// Hasta ahora solo alternaba la fila pulsada. Con un correo abierto (o resaltado) y sin casillas
// marcadas, Ctrl+clic en otra fila dejaba «seleccionado» solo el segundo: el primero, que la persona
// ve resaltado y da por elegido, no entraba (informe de Andes, 15/11/2026). Como en Outlook, el
// correo resaltado cuenta como el primero de la selección.

/**
 * Devuelve la selección tras un Ctrl+clic sobre `uid`.
 *
 * @param seleccion  UIDs con la casilla marcada antes del clic.
 * @param uid        Fila pulsada.
 * @param resaltado  UID del correo abierto o resaltado en la lista (null si no hay o no está a la vista).
 */
export function seleccionTrasCtrlClic(seleccion: ReadonlySet<number>, uid: number, resaltado: number | null): Set<number> {
  const nueva = new Set(seleccion);
  if (nueva.size === 0 && resaltado !== null && resaltado !== uid) {
    nueva.add(resaltado);
    nueva.add(uid);
    return nueva;
  }
  if (nueva.has(uid)) nueva.delete(uid); else nueva.add(uid);
  return nueva;
}
