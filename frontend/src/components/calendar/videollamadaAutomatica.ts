// Regla de la videollamada automática (sin React, para poder probarla sola).
// Un evento NUEVO con invitados es una reunión: la videollamada de Meet Maquita se enciende sola al agregar el
// primer invitado, una sola vez y nunca contra la decisión de la persona (si ya movió el interruptor, se respeta).
// No se enciende si el lugar ya trae un enlace (p. ej. una reunión de otra plataforma) ni en un evento que se
// repite: la reunión de Meet tiene una sola fecha y el pase de los invitados externos vale solo en esa ventana.
export function debeEncenderVideollamada(esNuevo: boolean, invitados: number, lugar: string, yaDecidido: boolean, seRepite = false): boolean {
  return esNuevo && !yaDecidido && !seRepite && invitados > 0 && !/https?:\/\//.test(lugar || "");
}
