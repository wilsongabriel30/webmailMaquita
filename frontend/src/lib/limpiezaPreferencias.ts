/**
 * Preferencias guardadas en el navegador que se borran al cerrar sesión (equipos compartidos).
 * Se conservan las que son del equipo y no de la persona: la escala de la interfaz y el ancho de la lista.
 * (Revisión Qwen v1.7.22, H3.)
 */
const CLAVES_DE_LA_PERSONA = [
  'maquita_sig_settings', 'maquita_sig_cache', 'maquita_dictado_modo', 'maquita_buscar_en_todo',
  'maquita_pinned_msgs', 'maquita_errors',
];

export function limpiarPreferenciasLocales() {
  try {
    for (const clave of CLAVES_DE_LA_PERSONA) localStorage.removeItem(clave);
    sessionStorage.clear();
  } catch { /* sin almacenamiento o bloqueado por el navegador */ }
}
