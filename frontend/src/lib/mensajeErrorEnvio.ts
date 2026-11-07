// Traduce el error crudo de un envío a una frase que entienda cualquier persona.
//
// El servidor devuelve a veces el texto del SMTP tal cual («Error al enviar: (550, b'5.1.1 …')»)
// y el redactor le anteponía otro «Error al enviar: ». A quien escribe solo le sirve saber qué
// pasó y qué hacer; el detalle técnico queda en la consola para quien dé soporte.

const DIRECCION = /[\w.+-]+@[\w-]+(?:\.[\w-]+)+/;

export function textoErrorEnvio(crudo: string): string {
  const texto = (crudo || '').replace(/^(Error al enviar:\s*)+/i, '').trim();
  if (texto) console.warn('[correo] detalle del error al enviar:', crudo);

  if (/\b55[03]\b|5\.1\.[0-9]|user unknown|no such user|mailbox unavailable|recipient address rejected/i.test(texto)) {
    const dir = texto.match(DIRECCION)?.[0];
    return dir
      ? `No se envió: la dirección ${dir} no existe o no acepta correo. Revise que esté bien escrita.`
      : 'No se envió: alguna de las direcciones no existe o no acepta correo. Revise que estén bien escritas.';
  }
  if (/\b552\b|5\.3\.4|too large|demasiado grande|413/i.test(texto)) {
    return 'No se envió: el correo es demasiado grande. Quite algún adjunto o envíelo por partes.';
  }
  if (/HTTP 5\d\d|\b5\d\d\b|internal server error|servidor/i.test(texto)) {
    return 'No se envió: el servidor de correo tuvo un problema. Inténtelo de nuevo en unos minutos; el correo se volvió a abrir para que no pierda lo escrito.';
  }
  if (/HTTP 4\d\d|401|403/i.test(texto)) {
    return 'No se envió: su sesión ya no es válida. Copie el texto, cierre sesión y vuelva a entrar.';
  }
  return 'No se pudo enviar el correo. Inténtelo de nuevo; el correo se volvió a abrir para que no pierda lo escrito.';
}
