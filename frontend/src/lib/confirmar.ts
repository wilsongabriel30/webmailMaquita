// Confirmaciones propias de la aplicación, pedidas desde cualquier parte: `await confirmar({...})`.
//
// Sustituye a `window.confirm()`, que saca una ventana del navegador con otro aspecto y sin poder
// explicar bien lo que va a pasar. La ventana la dibuja `DialogoConfirmar` (components/common),
// que está montado junto a los avisos flotantes. Mismo esquema que Toast.ts / ToastContainer.tsx.

export interface PeticionConfirmar {
  titulo: string;
  /** Explicación; cada elemento es un párrafo. */
  texto: string | string[];
  /** Rótulo del botón que confirma (por omisión, «Aceptar»). */
  aceptar?: string;
  /** Si es true, el botón que confirma va en rojo: la acción tiene consecuencias. */
  peligro?: boolean;
}

type Mostrar = (peticion: PeticionConfirmar, responder: (acepta: boolean) => void) => void;

let mostrar: Mostrar | null = null;

/** Lo usa DialogoConfirmar para recibir las peticiones; devuelve la función para dejar de escuchar. */
export function suscribirConfirmaciones(m: Mostrar) {
  mostrar = m;
  return () => { if (mostrar === m) mostrar = null; };
}

/** Pregunta y devuelve true si la persona confirma. Cerrar o pulsar Escape equivale a cancelar. */
export function confirmar(peticion: PeticionConfirmar): Promise<boolean> {
  if (!mostrar) {
    // Sin el diálogo montado (no debería ocurrir) se pregunta igual: nunca se actúa sin confirmar.
    const parrafos = Array.isArray(peticion.texto) ? peticion.texto : [peticion.texto];
    return Promise.resolve(window.confirm([peticion.titulo, ...parrafos].join('\n\n')));
  }
  const m = mostrar;
  return new Promise((resolve) => m(peticion, resolve));
}
