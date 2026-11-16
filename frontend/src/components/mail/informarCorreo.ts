// «Informar» un correo (suplantación o no deseado) desde cualquier punto de la interfaz: la cinta,
// el menú «…» del correo abierto, el clic derecho de la lista y la barra del lector.
//
// El servidor (/mail/spam/report) hace tres cosas: mueve el correo a Correo no deseado, se lo enseña
// al filtro y deja BLOQUEADO al remitente (salvo los de la propia organización). La interfaz no lo
// decía y un clic por error dejaba a un contacto real en Correo no deseado (informe de Andes,
// 15/11/2026). Ahora siempre se pregunta antes, diciendo lo del bloqueo, y al terminar se avisa.
import { api } from '../../api/client';
import { confirmar } from '../../lib/confirmar';
import { avisoDeInforme, preguntaDeInforme, type MotivoInforme } from '../../lib/textosInforme';

interface RespuestaInforme { moved?: number; bloqueados?: string[] }

/** Pregunta, diciendo que se bloqueará al remitente. Devuelve true si la persona confirma. */
export function confirmarInforme(motivo: MotivoInforme, cantidad = 1): Promise<boolean> {
  return confirmar(preguntaDeInforme(motivo, cantidad));
}

/** Informa los correos al servidor y devuelve el texto del aviso. Lanza si el servidor falla. */
export async function enviarInforme(folder: string, uids: number[], motivo: MotivoInforme): Promise<string> {
  const r = await api.post<RespuestaInforme>('/mail/spam/report', { folder, uids });
  // El servidor responde 200 aunque no haya podido mover nada (p. ej. sin sesión de correo): no se da por hecho.
  if (r && r.moved === 0) throw new Error('No se movió ningún correo');
  return avisoDeInforme(motivo, uids.length, r?.bloqueados || []);
}
