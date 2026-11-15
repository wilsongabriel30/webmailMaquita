/**
 * Preferencias guardadas en el navegador que se borran al cerrar sesión (equipos compartidos).
 * Se conservan las que son del equipo y no de la persona: la escala de la interfaz y el ancho de la lista.
 * (Revisión Qwen v1.7.22, H3.)
 */
import { sinGuardarEnCuenta } from './preferenciasCuenta';

const CLAVES_DE_LA_PERSONA = [
  'maquita_sig_settings', 'maquita_sig_cache', 'maquita_dictado_modo', 'maquita_buscar_en_todo',
  'maquita_pinned_msgs', 'maquita_errors',
  // Color principal (Apariencia, 13/11/2026): es de la persona, no del equipo; vuelve con su cuenta al entrar.
  'maquita_acento',
];

export function limpiarPreferenciasLocales() {
  try {
    // Sin avisar a la cuenta: si este borrado se guardara, la persona perdería en su cuenta lo que aquí solo se limpia del equipo.
    sinGuardarEnCuenta(() => { for (const clave of CLAVES_DE_LA_PERSONA) localStorage.removeItem(clave); });
    sessionStorage.clear();
    // Copias de reserva de correos a medio escribir (redaccionesRecuperables.ts): al cerrar
    // sesión a propósito no deben quedar en un equipo compartido.
    const reservas: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.startsWith('maquita_redacciones_reserva:')) reservas.push(k);
    }
    for (const k of reservas) localStorage.removeItem(k);
  } catch { /* sin almacenamiento o bloqueado por el navegador */ }
}
