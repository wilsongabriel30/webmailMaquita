// Mensajes de la pantalla de entrada en palabras de cualquier persona.
//
// Antes se mostraban tal cual «Failed to fetch» (sin red), «HTTP 502» (servidor ocupado, probable
// con todo el personal entrando a la vez) o «Credenciales incorrectas». Los avisos que el servidor
// ya da en español (intentos agotados, cuánto esperar) se respetan.

export function textoErrorEntrada(mensaje: string, usuario: string): string {
  const m = (mensaje || '').trim();
  if (/failed to fetch|networkerror|load failed|sin conexi[oó]n|network request failed/i.test(m)) {
    return 'No hay conexión con el servidor del correo. Revise su internet y vuelva a intentar.';
  }
  if (/HTTP 5\d\d|\b50[0234]\b|bad gateway|service unavailable|gateway time/i.test(m)) {
    return 'El correo está muy ocupado en este momento. Espere un minuto e inténtelo otra vez.';
  }
  if (/credenciales incorrectas|invalid credentials|HTTP 401/i.test(m) || !m) {
    const sinDominio = usuario.trim() !== '' && !usuario.includes('@');
    return sinDominio
      ? 'El correo o la contraseña no son correctos. Escriba su dirección de correo completa, con @ y el dominio, y revise que la tecla Bloq Mayús esté apagada.'
      : 'El correo o la contraseña no son correctos. Revise que la dirección esté completa y que la tecla Bloq Mayús esté apagada.';
  }
  if (/nombre de usuario inv[aá]lido|HTTP 422/i.test(m)) {
    return 'La dirección de correo tiene caracteres que no corresponden. Escríbala completa, por ejemplo nombre@dominio.com.';
  }
  return m;
}
