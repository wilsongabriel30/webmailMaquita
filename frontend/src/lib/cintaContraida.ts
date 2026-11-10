// La cinta de opciones recuerda si la persona la contrajo (10/11/2026): en portátiles de poca
// altura muchos la cierran para leer el correo entero y antes volvía a abrirse en cada carga.
const CLAVE = 'maquita_cinta_contraida';

export function leerCintaContraida(): boolean {
  try { return localStorage.getItem(CLAVE) === '1'; } catch { return false; }
}

export function guardarCintaContraida(contraida: boolean): void {
  try { localStorage.setItem(CLAVE, contraida ? '1' : '0'); } catch { /* sin almacenamiento */ }
}
