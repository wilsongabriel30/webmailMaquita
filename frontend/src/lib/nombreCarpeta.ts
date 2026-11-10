// El servidor de correo usa el punto como separador de jerarquía: «7. Servicios Generales» se
// convertía en una carpeta «7» con una subcarpeta « Servicios Generales» (caso real, 10/11/2026).
// Al crear o renombrar, el punto del nombre se cambia por «․» (U+2024), que se ve igual.
const PUNTO_VISIBLE = '\u2024';

export function nombreHojaSeguro(nombre: string): string {
  return nombre.trim().replace(/\./g, PUNTO_VISIBLE);
}
