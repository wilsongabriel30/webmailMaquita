// Regla de las pestañas «Prioritarios» y «Otros» de la Bandeja de entrada (06/11/2026).
//
// Antes «Prioritarios» mostraba TODO y «Otros» lo que la IA no marcó como importante; como la IA
// solo clasifica los últimos 50 correos, lo interno más antiguo o sin clasificar caía en «Otros»
// (caso: las transferencias de Contabilidad). Ahora, en este orden:
//   1. Si la persona lo reclasificó a mano, manda su decisión.
//   2. Marcado con bandera                      → Prioritarios.
//   3. Remitente de un dominio de la casa       → Prioritarios, siempre (sin depender de la IA).
//   3b. Externo, dirigido a la propia persona (su dirección en Para) y con adjuntos → Prioritarios
//       (10/11/2026: un acta de finiquito de una contraparte cayó en «Otros» y no se encontró).
//   4. Sin clasificar todavía                   → Prioritarios (nunca se esconde lo desconocido).
//   5. La IA lo clasificó como bajo (boletines, publicidad, avisos automáticos) → Otros.
//   6. Todo lo demás                            → Prioritarios.
import { api } from '../api/client';
import { useAuthStore } from '../store/authStore';

export type Pestana = 'focused' | 'other';

interface Clasificacion {
  priority: string;
  category?: string;
}

let dominios: Set<string> | null = null;
let pedido: Promise<void> | null = null;

/** Pide una sola vez los dominios de la casa al servidor. */
export function cargarDominiosPropios(): Promise<void> {
  if (dominios) return Promise.resolve();
  if (!pedido) {
    pedido = api
      .get<{ dominios: string[] }>('/mail/priority/dominios')
      .then((r) => {
        dominios = new Set((r.dominios || []).map((d) => d.toLowerCase()));
      })
      .catch(() => {
        pedido = null; // se reintenta en la próxima carga de la lista
      });
  }
  return pedido;
}

function dominioDe(from: string): string {
  const m = from.match(/<([^>]+)>/);
  const correo = (m ? m[1] : from).trim().toLowerCase();
  const i = correo.lastIndexOf('@');
  return i >= 0 ? correo.slice(i + 1) : '';
}

export function esRemitenteInterno(from: string): boolean {
  return !!dominios && dominios.has(dominioDe(from || ''));
}

/** La dirección de la persona aparece en «Para» (no un envío masivo ni solo en copia). */
export function esParaMi(to: string, mia = useAuthStore.getState().user?.username): boolean {
  if (!mia || !to) return false;
  return to.toLowerCase().includes(mia.trim().toLowerCase());
}

export function pestanaDe(
  m: { from: string; to?: string; flagged: boolean; has_attachments?: boolean },
  p?: Clasificacion,
): Pestana {
  if (p && p.category === 'manual') return p.priority === 'low' ? 'other' : 'focused';
  if (m.flagged) return 'focused';
  if (esRemitenteInterno(m.from)) return 'focused';
  if (m.has_attachments && esParaMi(m.to || '')) return 'focused';
  if (!p) return 'focused';
  return p.priority === 'low' ? 'other' : 'focused';
}

export const AYUDA_PESTANAS: Record<Pestana, string> = {
  focused: 'Prioritarios: todo el correo interno, lo marcado con bandera, lo que llega de personas y clientes y lo que te envían directamente con adjuntos',
  other: 'Otros: boletines, publicidad y avisos automáticos de fuera de la institución',
};
