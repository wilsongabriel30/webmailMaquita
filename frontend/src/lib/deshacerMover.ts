/**
 * «Deshacer» tras mover correos: el aviso «Movido a X» lleva un botón que los devuelve a su carpeta.
 *
 * El servidor responde a /mail/bulk-action y /mail/move con `movidos` = {uid origen: uid destino}
 * (lo que informa IMAP con COPYUID). Con ese mapa se mueven de vuelta los UIDs nuevos. Si el
 * servidor no lo informó (servidor sin esa versión o sin COPYUID), el aviso sale sin botón.
 */
import { api } from '../api/client';
import { dismissToast, showToast } from '../components/common/Toast';
import { getFolderDisplayName } from '../folders';

export interface LoteMovido {
  origen: string;
  destino: string;
  /** uid en la carpeta de origen → uid en la carpeta de destino */
  movidos: Record<string, number>;
}

export interface RespuestaMover {
  movidos?: Record<string, number> | null;
}

/** Lote para deshacer a partir de la respuesta del servidor; null si no trae el mapa. */
export function loteDeRespuesta(origen: string, destino: string, respuesta: RespuestaMover | null | undefined): LoteMovido | null {
  const movidos = respuesta?.movidos;
  if (!movidos || !Object.keys(movidos).length) return null;
  return { origen, destino, movidos };
}

/** Devuelve los correos a su carpeta de origen. */
export async function deshacerMovidos(lotes: LoteMovido[]): Promise<boolean> {
  const validos = lotes.filter(l => Object.keys(l.movidos).length);
  if (!validos.length) return false;
  try {
    for (const l of validos) {
      const uids = Object.values(l.movidos);
      await api.post(`/mail/bulk-action/${encodeURIComponent(l.destino)}`, { uids, action: 'move', dest_folder: l.origen });
    }
    const origenes = Array.from(new Set(validos.map(l => getFolderDisplayName(l.origen))));
    showToast(origenes.length === 1 ? `Devuelto a ${origenes[0]}` : 'Correos devueltos a sus carpetas');
    window.dispatchEvent(new CustomEvent('refresh-messages'));
    window.dispatchEvent(new CustomEvent('refresh-folders'));
    return true;
  } catch {
    showToast('No se pudo deshacer: el correo sigue en la carpeta de destino');
    return false;
  }
}

/** Último movimiento que se puede deshacer con Ctrl+Z (o el botón «Deshacer» de la barra). */
const VIGENCIA_MS = 120000;
let ultimo: { lotes: LoteMovido[]; hasta: number; idAviso?: string } | null = null;

/** Acción «Deshacer» para un aviso; undefined si no hay nada que devolver. */
export function accionDeshacer(lotes: LoteMovido[]): { label: string; onClick: () => void } | undefined {
  if (!lotes.some(l => Object.keys(l.movidos).length)) return undefined;
  return {
    label: 'Deshacer',
    onClick: () => {
      if (ultimo && ultimo.lotes === lotes) ultimo = null;
      void deshacerMovidos(lotes);
    },
  };
}

/** Guarda el movimiento para Ctrl+Z; `idAviso` es el aviso que se cierra al deshacer. */
export function recordarParaDeshacer(lotes: LoteMovido[], idAviso?: string | null) {
  if (!lotes.some(l => Object.keys(l.movidos).length)) return;
  ultimo = { lotes, hasta: Date.now() + VIGENCIA_MS, idAviso: idAviso || undefined };
}

/** Deshace el último movimiento (Ctrl+Z). Devuelve false si no había nada reciente que deshacer. */
export async function deshacerUltimo(): Promise<boolean> {
  if (!ultimo || Date.now() > ultimo.hasta) { ultimo = null; return false; }
  const pendiente = ultimo;
  ultimo = null;
  if (pendiente.idAviso) dismissToast(pendiente.idAviso);
  await deshacerMovidos(pendiente.lotes);
  return true;
}
