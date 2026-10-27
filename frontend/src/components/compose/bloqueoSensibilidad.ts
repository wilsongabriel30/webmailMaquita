// Respuesta del servidor cuando un correo «Confidencial» o «Restringida» va a destinatarios
// externos (422 con sensitivity_blocked). Antes la pantalla mostraba el JSON crudo.
export interface BloqueoSensibilidad {
  etiqueta: string;
  externos: string[];
  puedeForzar: boolean;
}

export function leerBloqueoSensibilidad(errMsg: string): BloqueoSensibilidad | null {
  if (!errMsg.includes('sensitivity_blocked')) return null;
  try {
    const d = JSON.parse(errMsg) as { label?: string; external?: string[]; can_override?: boolean };
    return { etiqueta: d.label || 'Confidencial', externos: d.external || [], puedeForzar: !!d.can_override };
  } catch {
    return { etiqueta: 'Confidencial', externos: [], puedeForzar: false };
  }
}

export function textoBloqueoSensibilidad(b: BloqueoSensibilidad): string {
  const externos = b.externos.length ? '\n\nDestinatarios externos:\n' + b.externos.join(', ') : '';
  return '🔒 Un correo «' + b.etiqueta + '» solo puede enviarse dentro de la organización.' + externos;
}

// Devuelve el motivo si un administrador decide forzar el envío; null si no puede o cancela.
export function pedirMotivoSensibilidad(b: BloqueoSensibilidad): string | null {
  const texto = textoBloqueoSensibilidad(b);
  if (!b.puedeForzar) {
    window.alert(texto + '\n\nQuita la etiqueta o esos destinatarios para poder enviarlo, o solicita autorización a Tecnología.');
    return null;
  }
  const motivo = window.prompt(texto + '\n\nComo administrador puedes enviarlo igual. Escribe el motivo (queda registrado) o cancela:');
  return motivo && motivo.trim() ? motivo.trim() : null;
}
