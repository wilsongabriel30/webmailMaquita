// Destinatarios de «Responder a todos».
//
// Regla: quien responde no se escribe a sí mismo. Se quitan la cuenta propia y, si el correo
// está en una cuenta delegada, también esa cuenta; en ambos casos con sus alias personales
// (la misma persona con dirección en otro dominio del servidor). Tampoco se repite nadie.
// Si el correo original lo envió la propia persona (p. ej. desde Enviados), la respuesta va a
// quienes lo recibieron, no a ella misma.
import { useAuthStore } from '../store/authStore';
import { useMailStore } from '../store/mailStore';
import { cuentaDeCarpeta } from './cuentas';

interface MensajeOrigen {
  from: string;
  to?: string;
  cc?: string;
  folder?: string;
}

/** 'Ana <ana@x.com>' -> 'ana@x.com' (en minúsculas) */
export function soloCorreo(direccion: string): string {
  const m = direccion.match(/<([^>]+)>/);
  return (m ? m[1] : direccion).trim().toLowerCase();
}

/** Parte una lista de direcciones por comas, sin romper los nombres entre comillas («Pérez, Ana»). */
export function partirDirecciones(lista: string | undefined | null): string[] {
  if (!lista) return [];
  const partes: string[] = [];
  let actual = '';
  let entreComillas = false;
  let enAngulos = false;
  for (const c of lista) {
    if (c === '"') entreComillas = !entreComillas;
    else if (c === '<' && !entreComillas) enAngulos = true;
    else if (c === '>' && !entreComillas) enAngulos = false;
    if ((c === ',' || c === ';') && !entreComillas && !enAngulos) {
      partes.push(actual);
      actual = '';
    } else {
      actual += c;
    }
  }
  partes.push(actual);
  return partes.map(p => p.trim()).filter(Boolean);
}

/** Direcciones que son «yo»: la cuenta de la sesión, las cuentas propias y la cuenta delegada de la carpeta. */
export function direccionesPropias(carpeta?: string | null): Set<string> {
  const propias = new Set<string>();
  const usuario = useAuthStore.getState().user?.username;
  if (usuario) propias.add(usuario.toLowerCase());
  const estado = useMailStore.getState();
  const delegada = cuentaDeCarpeta(carpeta || estado.currentFolder);
  if (delegada) propias.add(delegada);
  for (const c of estado.cuentas || []) {
    const correo = (c.email || '').toLowerCase();
    if (!correo || !(c.propia || correo === delegada)) continue;
    propias.add(correo);
    for (const a of c.alias || []) propias.add(a.toLowerCase());
  }
  return propias;
}

export function destinatariosResponderATodos(
  msg: MensajeOrigen,
  propias: Set<string> = direccionesPropias(msg.folder),
): { to: string[]; cc: string[] } {
  const vistos = new Set<string>();
  const filtrar = (lista: string[]) => lista.filter(d => {
    const correo = soloCorreo(d);
    if (!correo || propias.has(correo) || vistos.has(correo)) return false;
    vistos.add(correo);
    return true;
  });

  const remitente = soloCorreo(msg.from || '');
  if (remitente && propias.has(remitente)) {
    const to = filtrar(partirDirecciones(msg.to));
    const cc = filtrar(partirDirecciones(msg.cc));
    // Correo enviado solo a uno mismo: no queda nadie más a quien responder.
    return to.length ? { to, cc } : { to: [remitente], cc };
  }

  vistos.add(remitente);
  const cc = filtrar([...partirDirecciones(msg.to), ...partirDirecciones(msg.cc)]);
  return { to: remitente ? [remitente] : [], cc };
}
