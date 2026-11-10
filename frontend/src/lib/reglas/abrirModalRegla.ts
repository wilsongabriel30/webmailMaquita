import type { Regla } from './tipos';

/* Abrir la ventana «Regla de correo» desde cualquier parte (clic derecho, barra, Ajustes).
   ModalReglaHost la escucha y la pinta. */

export interface PeticionModalRegla {
  regla: Regla;
  /** Índice de la regla que se edita; sin índice se crea una nueva. */
  indice?: number;
  /** Se llama tras guardar correctamente. */
  alGuardar?: (regla: Regla) => void;
}

export const EVENTO_MODAL_REGLA = 'abrir-modal-regla';

export function abrirModalRegla(peticion: PeticionModalRegla) {
  window.dispatchEvent(new CustomEvent<PeticionModalRegla>(EVENTO_MODAL_REGLA, { detail: peticion }));
}
