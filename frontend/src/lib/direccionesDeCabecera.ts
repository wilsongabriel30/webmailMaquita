/**
 * Direcciones de correo de una o varias cabeceras «Para» / «CC».
 *
 * Una cabecera trae nombres además de direcciones («Ana Pérez <ana@ejemplo.org>, luis@ejemplo.org»),
 * y un nombre entre comillas puede llevar comas o arrobas («"Pérez, Ana" <ana@ejemplo.org>»). Quien
 * necesita solo las direcciones (p. ej. recuperar un correo enviado) no puede partir por comas: el
 * 19/11/2026 la recuperación falló porque se enviaba al servidor el nombre junto con la dirección.
 *
 * Devuelve las direcciones en minúsculas, sin repetir y en el orden en que aparecen.
 */
const NOMBRE_ENTRE_COMILLAS = /"(?:[^"\\]|\\.)*"/g;
const DIRECCION = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;

export function direccionesDeCabecera(...cabeceras: (string | null | undefined)[]): string[] {
  const lista: string[] = [];
  for (const cabecera of cabeceras) {
    const sinNombres = (cabecera || '').replace(NOMBRE_ENTRE_COMILLAS, ' ');
    for (const hallada of sinNombres.match(DIRECCION) || []) {
      const direccion = hallada.toLowerCase();
      if (!lista.includes(direccion)) lista.push(direccion);
    }
  }
  return lista;
}
