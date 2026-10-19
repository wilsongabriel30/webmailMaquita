/**
 * T-73 · Dueño de la bandeja de salida.
 *
 * La cola de salida vive en el equipo y sobrevive al cierre de sesión (para no perder correo
 * escrito). Si después entra OTRA persona en el mismo equipo, la cola no debe salir con su
 * sesión: cada correo guarda quién lo escribió y solo se envía, se lista o se descarta con la
 * sesión de esa misma persona. Los correos sin dueño son de antes de este cambio y se tratan
 * como de la sesión abierta, igual que hasta ahora.
 *
 * Módulo sin dependencias: authStore anota aquí el usuario, y offlineStore / syncQueue lo leen
 * sin importar authStore (que ya importa offlineStore).
 */
let usuario: string | null = null;

export function fijarUsuarioSesion(nombre: string | null | undefined): void {
  usuario = nombre ? nombre.trim().toLowerCase() : null;
}

export function usuarioSesion(): string | null {
  return usuario;
}

/** ¿Este correo de la cola es de la sesión abierta? Sin sesión conocida, solo los sin dueño. */
export function esDeLaSesion(correo: { dueno?: string | null }): boolean {
  if (!correo.dueno) return true;
  return usuario !== null && correo.dueno.toLowerCase() === usuario;
}
