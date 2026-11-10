// Avisos flotantes: funciones para mostrarlos desde cualquier parte. El componente que los dibuja
// está en ToastContainer.tsx (separado para que el refresco en caliente de Vite funcione).

export interface ToastData {
  id: string;
  message: string;
  action?: { label: string; onClick: () => void };
  /** Si es true, no se cierra solo: queda hasta que la persona lo cierre (avisos de error importantes). */
  fijo?: boolean;
  /** Avisos con la misma clave se funden en uno (p. ej. «Enviados a la papelera: 3») en vez de apilarse. */
  clave?: string;
}

interface Oyentes {
  mostrar: (t: ToastData) => void;
  actualizar: (id: string, message: string, action?: ToastData['action']) => void;
  cerrar: (id: string) => void;
}

let oyentes: Oyentes | null = null;

/** Lo usa ToastContainer para recibir los avisos; devuelve la función para dejar de escuchar. */
export function suscribirAvisos(o: Oyentes) {
  oyentes = o;
  return () => { if (oyentes === o) oyentes = null; };
}

export function showToast(message: string, action?: { label: string; onClick: () => void }, opciones?: { fijo?: boolean; clave?: string }) {
  const id = Math.random().toString(36).slice(2);
  oyentes?.mostrar({ id, message, action, fijo: opciones?.fijo, clave: opciones?.clave });
  return id;
}

export function updateToast(id: string, message: string, action?: ToastData['action']) {
  oyentes?.actualizar(id, message, action);
}

export function dismissToast(id: string) {
  oyentes?.cerrar(id);
}
