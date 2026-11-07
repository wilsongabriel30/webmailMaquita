// Enciende la videollamada de Meet Maquita al agregar el primer invitado a un evento nuevo (regla en
// ../videollamadaAutomatica.ts). Devuelve la función que se llama cuando la persona mueve el interruptor a mano.
import { useEffect, useRef } from "react";
import { debeEncenderVideollamada } from "../videollamadaAutomatica";

export function useVideollamadaConInvitados(
  esNuevo: boolean,
  invitados: number,
  lugar: string,
  seRepite: boolean,
  encender: () => void,
): () => void {
  const decidido = useRef(false);
  useEffect(() => {
    if (debeEncenderVideollamada(esNuevo, invitados, lugar, decidido.current, seRepite)) {
      decidido.current = true;
      encender();
    }
  }, [esNuevo, invitados, lugar, seRepite, encender]);
  return () => { decidido.current = true; };
}
