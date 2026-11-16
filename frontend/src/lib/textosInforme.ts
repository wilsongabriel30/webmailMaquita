// Textos de «Informar» un correo: la pregunta de antes y el aviso de después. Sin dependencias, para
// poder probarlos (tests/textosInforme.test.ts). Quien pregunta e informa es
// components/mail/informarCorreo.ts.

export type MotivoInforme = 'suplantacion' | 'no-deseado';

/** Lo que se le pregunta a la persona antes de informar. Separado para poder probarlo. */
export function preguntaDeInforme(motivo: MotivoInforme, cantidad = 1) {
  const varios = cantidad > 1;
  const esto = varios ? `estos ${cantidad} correos` : 'este correo';
  return {
    titulo: motivo === 'suplantacion'
      ? `¿Informar ${esto} como suplantación de identidad?`
      : `¿Marcar ${esto} como no deseado?`,
    texto: [
      motivo === 'suplantacion'
        ? `Se informará como suplantación de identidad o estafa («phishing») y se moverá a Correo no deseado. No abra sus enlaces ni sus adjuntos.`
        : `Se moverá a Correo no deseado y el filtro aprenderá a reconocer correos parecidos.`,
      `${varios ? 'Sus remitentes quedarán bloqueados' : 'El remitente quedará bloqueado'}: sus próximos correos irán directo a Correo no deseado. Los remitentes de su propia organización no se bloquean.`,
      'Puede deshacer el bloqueo en Configuración → Remitentes bloqueados.',
    ],
    aceptar: varios ? 'Informar y bloquear remitentes' : 'Informar y bloquear remitente',
    peligro: true,
  };
}

/** El aviso de después: qué se hizo y a quién se bloqueó (lo dice el servidor). */
export function avisoDeInforme(motivo: MotivoInforme, cantidad: number, bloqueados: string[] = []): string {
  const hecho = motivo === 'suplantacion'
    ? (cantidad > 1 ? `${cantidad} correos informados como suplantación y movidos` : 'Informado como suplantación y movido')
    : (cantidad > 1 ? `${cantidad} correos movidos` : 'Movido');
  const bloqueo = bloqueados.length === 0 ? ''
    : bloqueados.length <= 3 ? ` Remitente${bloqueados.length > 1 ? 's' : ''} bloqueado${bloqueados.length > 1 ? 's' : ''}: ${bloqueados.join(', ')}.`
      : ` ${bloqueados.length} remitentes bloqueados.`;
  return `${hecho} a Correo no deseado.${bloqueo}`;
}
