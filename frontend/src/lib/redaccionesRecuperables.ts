/**
 * Correos a medio escribir que sobreviven a una recarga de la página (13/10/2026).
 *
 * La copia de estadoRedaccion.ts vive en memoria: aguanta minimizar o cambiar de carpeta,
 * pero una recarga (versión nueva del webmail, cambio de cuenta, un fallo de carga, F5) la
 * borraba y lo escrito quedaba solo en Borradores, a veces sin lo último ni los adjuntos.
 *
 * Aquí se guarda en sessionStorage —es de la pestaña, sobrevive a la recarga y no se cruza
 * con otras pestañas— lo mínimo para reabrir cada ventana: destinatarios, asunto, texto y el
 * UID del borrador del servidor (que tiene los adjuntos). Se anota al escribir, al guardar el
 * borrador y justo antes de salir de la página. Al volver a cargar, RecuperarRedacciones.tsx
 * reabre las ventanas como «Editar borrador», con el texto más reciente.
 *
 * La clave lleva la persona y la cuenta activa: cada cuenta recupera solo lo suyo.
 */
import { cuentaActiva } from './cuentaActiva';

export interface RedaccionGuardada {
  id: string;
  draftUid: number | null;
  to: string;
  cc: string;
  bcc: string;
  subject: string;
  /** Cuerpo + cita, sin firma (igual que el borrador del servidor). */
  html: string;
  inReplyTo: string;
  references: string;
  actualizado: number;
}

function clave(): string {
  let persona = '';
  try {
    persona = (JSON.parse(localStorage.getItem('ultima_sesion') || 'null')?.username || '').toLowerCase();
  } catch {
    /* sin almacenamiento: clave sin persona */
  }
  return `maquita_redacciones:${persona}:${cuentaActiva() || 'propia'}`;
}

function leerTodas(): Record<string, RedaccionGuardada> {
  try {
    return JSON.parse(sessionStorage.getItem(clave()) || '{}') || {};
  } catch {
    return {};
  }
}

function escribirTodas(todas: Record<string, RedaccionGuardada>): void {
  try {
    if (Object.keys(todas).length) sessionStorage.setItem(clave(), JSON.stringify(todas));
    else sessionStorage.removeItem(clave());
  } catch {
    /* almacenamiento lleno o bloqueado: queda el borrador del servidor */
  }
}

/** Sin destinatarios, asunto ni texto: no hay nada que recuperar. */
function vacia(r: RedaccionGuardada): boolean {
  const texto = r.html.replace(/<img\b/gi, 'x<').replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').trim();
  return !r.to.trim() && !r.cc.trim() && !r.bcc.trim() && !r.subject.trim() && !texto && !r.draftUid;
}

export function anotarRedaccion(r: RedaccionGuardada): void {
  const todas = leerTodas();
  if (vacia(r)) delete todas[r.id];
  else todas[r.id] = { ...r, actualizado: Date.now() };
  escribirTodas(todas);
}

/** La ventana se cerró o se envió: ya no hay nada que recuperar. */
export function olvidarRedaccion(id: string): void {
  const todas = leerTodas();
  if (!(id in todas)) return;
  delete todas[id];
  escribirTodas(todas);
}

/** Lo que había abierto en esta pestaña y cuenta; se vacía al leerlo (las ventanas nuevas se vuelven a anotar). */
export function tomarRedaccionesGuardadas(): RedaccionGuardada[] {
  const todas = Object.values(leerTodas()).filter(r => !vacia(r));
  try {
    sessionStorage.removeItem(clave());
  } catch {
    /* nada */
  }
  return todas.sort((a, b) => a.actualizado - b.actualizado);
}

// Ventanas abiertas en pantalla: cada una deja aquí cómo sacar su foto al momento.
const fuentes = new Map<string, () => RedaccionGuardada | null>();

export function registrarFuente(id: string, foto: () => RedaccionGuardada | null): () => void {
  fuentes.set(id, foto);
  return () => {
    if (fuentes.get(id) === foto) fuentes.delete(id);
  };
}

/** Anota ya lo que hay en pantalla en todas las ventanas (antes de salir de la página). */
export function volcarRedacciones(): void {
  for (const foto of fuentes.values()) {
    try {
      const r = foto();
      if (r) anotarRedaccion(r);
    } catch {
      /* una ventana a medio desmontar no impide guardar las demás */
    }
  }
}
