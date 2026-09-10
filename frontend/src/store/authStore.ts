import { create } from 'zustand';
import type { UserInfo } from '../types';
import { olvidarLlave } from '../lib/cifradoLocal';
import { getOutboxCount } from '../lib/offlineStore';

interface AuthState {
  user: UserInfo | null;
  loading: boolean;
  setUser: (user: UserInfo | null) => void;
  setLoading: (loading: boolean) => void;
  logout: () => void;
}

/** Olvidar la llave del cache local al cerrar sesion... salvo que haya correo sin enviar.
 *
 *  El cache de correos guardados para leer sin conexion se cifra con una llave que vive en el
 *  navegador. Si no se borra al cerrar sesion, en un equipo compartido la persona siguiente la
 *  hereda junto con los correos. Eso es lo que hay que evitar.
 *
 *  Pero la cola de salida se cifra con esa MISMA llave. Borrarla con correos pendientes los deja
 *  ilegibles para siempre: seria perder un correo ya escrito, que es peor. Asi que si queda algo
 *  en la cola, la llave se conserva y se dice por que.
 */
async function limpiarCacheLocal(): Promise<void> {
  try {
    const pendientes = await getOutboxCount();
    if (pendientes > 0) {
      console.info(
        `Quedan ${pendientes} correo(s) sin enviar: se conserva el cache local para no perderlos. ` +
          'Se enviaran al volver a entrar.',
      );
      return;
    }
    await olvidarLlave();
  } catch {
    // Si no se puede mirar la cola, no se borra nada: ante la duda, no perder correo.
  }
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  loading: true,
  setUser: (user) => set({ user, loading: false }),
  setLoading: (loading) => set({ loading }),
  logout: () => {
    // No se espera a que termine: cerrar la sesion en pantalla es inmediato y la limpieza va sola.
    void limpiarCacheLocal();
    set({ user: null, loading: false });
  },
}));
