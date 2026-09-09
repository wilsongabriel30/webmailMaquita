// Qué NO se pulsa nunca en una instalación viva.
//
// La exploración pulsa lo que encuentra, así que la frontera tiene que estar escrita: nada que
// envíe correo a nadie, borre, vacíe, cierre la sesión de la tanda o cambie configuración.
// Ante la duda, no se pulsa: un botón sin probar es una laguna; un correo enviado sin querer,
// un problema de verdad.
const PROHIBIDO = [
  /enviar|send/i,
  /eliminar|borrar|delete|quitar|descartar/i,
  /vaciar|purgar|limpiar papelera/i,
  /cerrar sesión|cerrar sesion|salir|logout/i,
  /guardar|aplicar|actualizar contraseña|cambiar contraseña/i,
  /desactivar|activar|habilitar|deshabilitar/i,
  /reiniciar|apagar|detener/i,
  /suspender|revocar|expulsar|bloquear/i,
  /mover a|archivar|marcar como spam|spam/i,
  /instalar|desinstalar|importar|exportar|restaurar/i,
  /pagar|comprar|suscribir/i,
  /confirmar|aceptar y|sí, /i,
];

// Se pulsa con confianza: abren algo, cambian de vista o pintan un panel, y se deshacen solos.
const SEGURO_AUNQUE_SUENE_RARO = [
  /nuevo correo|redactar|escribir/i,
  /responder$|responder a todos|reenviar/i, // Abren el redactor; no envían nada por sí solos.
  /buscar|filtrar|ordenar|ver|mostrar|ocultar/i,
  /siguiente|anterior|volver|atrás|atras|cerrar/i,
  /ayuda|acerca de|información|informacion/i,
];

/** ¿Es seguro pulsar este elemento? Devuelve `{ seguro, motivo }`. */
function esSeguroPulsar(texto) {
  const t = (texto || '').trim();
  if (!t) return { seguro: false, motivo: 'sin texto: no se puede saber qué hace' };
  for (const patron of SEGURO_AUNQUE_SUENE_RARO) {
    if (patron.test(t)) return { seguro: true, motivo: 'abre o navega, no compromete nada' };
  }
  for (const patron of PROHIBIDO) {
    if (patron.test(t)) return { seguro: false, motivo: `acción con consecuencias (${patron})` };
  }
  return { seguro: true, motivo: 'sin consecuencias conocidas' };
}

module.exports = { esSeguroPulsar, PROHIBIDO };
