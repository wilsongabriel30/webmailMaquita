/**
 * Arrastre de destinatarios entre Para, CC y CCO, y utilidades de los «cuadritos» (chips).
 *
 * Los tres campos son componentes independientes; este módulo guarda qué chip se está
 * arrastrando y cómo quitarlo de su campo de origen, para que el campo de destino lo
 * adopte al soltarlo. También resuelve el nombre de un correo (para el aviso al pasar el
 * ratón) consultando la agenda una sola vez por dirección.
 */
import { api } from '../../api/client';

export type CampoDestinatario = 'to' | 'cc' | 'bcc';

export interface ChipDestinatario {
  email: string;
  display: string;
  source?: string;
  jobTitle?: string;
  department?: string;
  phone?: string;
  photoUrl?: string;
}

export const ETIQUETA_CAMPO: Record<CampoDestinatario, string> = { to: 'Para', cc: 'CC', bcc: 'CCO' };

export function idDeCampo(label: string): CampoDestinatario {
  const l = label.trim().toLowerCase();
  return l === 'para' ? 'to' : l === 'cc' ? 'cc' : 'bcc';
}

/* ── Arrastre en curso (uno solo a la vez) ── */
interface Arrastre { chip: ChipDestinatario; origen: CampoDestinatario; quitar: () => void; }
let arrastreActual: Arrastre | null = null;

export function iniciarArrastre(chip: ChipDestinatario, origen: CampoDestinatario, quitar: () => void, e: React.DragEvent) {
  arrastreActual = { chip, origen, quitar };
  e.dataTransfer.effectAllowed = 'move';
  e.dataTransfer.setData('text/plain', chip.email);
  e.dataTransfer.setData('application/x-destinatario', chip.email);
}

export function arrastreEnCurso(): Arrastre | null { return arrastreActual; }
export function terminarArrastre() { arrastreActual = null; }
export function esArrastreDeDestinatario(e: React.DragEvent): boolean {
  return Array.from(e.dataTransfer.types).includes('application/x-destinatario');
}

/* ── Mover un chip a otro campo desde el menú contextual ── */
const EVENTO_MOVER = 'destinatario-mover';
export interface MoverDetalle { chip: ChipDestinatario; destino: CampoDestinatario; }

export function pedirMover(chip: ChipDestinatario, destino: CampoDestinatario) {
  window.dispatchEvent(new CustomEvent<MoverDetalle>(EVENTO_MOVER, { detail: { chip, destino } }));
}
export function escucharMover(fn: (d: MoverDetalle) => void): () => void {
  const h = (e: Event) => fn((e as CustomEvent<MoverDetalle>).detail);
  window.addEventListener(EVENTO_MOVER, h);
  return () => window.removeEventListener(EVENTO_MOVER, h);
}
/** Para que CC/CCO se muestren cuando se mueve un chip hacia ellos. */
export const EVENTO_MOSTRAR_CAMPO = 'destinatario-mostrar-campo';
export function pedirMostrarCampo(campo: CampoDestinatario) {
  window.dispatchEvent(new CustomEvent<CampoDestinatario>(EVENTO_MOSTRAR_CAMPO, { detail: campo }));
}

/* ── Nombre de un correo según la agenda (con caché) ── */
const nombres = new Map<string, Promise<string>>();
export function nombreDe(email: string): Promise<string> {
  const clave = email.trim().toLowerCase();
  if (!nombres.has(clave)) {
    nombres.set(clave, api.get<{ contacts: { name?: string; email: string }[] }>(
      `/contacts/search?q=${encodeURIComponent(clave)}&limit=5`,
    ).then(r => (r.contacts || []).find(c => (c.email || '').toLowerCase() === clave)?.name || '')
      .catch(() => ''));
  }
  return nombres.get(clave)!;
}

/* ── Contacto en la agenda: existe o no ── */
export async function idContactoDe(email: string): Promise<number | null> {
  try {
    const r = await api.get<{ contacts: { id: number; email?: string; email2?: string; email3?: string }[] }>(
      `/contacts?search=${encodeURIComponent(email)}&per_page=5`,
    );
    const e = email.trim().toLowerCase();
    const c = (r.contacts || []).find(x => [x.email, x.email2, x.email3].some(v => (v || '').toLowerCase() === e));
    return c ? c.id : null;
  } catch { return null; }
}
