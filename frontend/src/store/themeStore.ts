import { create } from 'zustand';

/**
 * Tema elegido (13/11/2026): claro, oscuro o «según el equipo» (el que tenga la computadora o el teléfono).
 * Se guarda en `maquita_tema`. La clave anterior `theme` (`dark` / `light`) se sigue escribiendo con el
 * tema que se ve en ese momento, para lo que aún la lee.
 */
export type ModoTema = 'claro' | 'oscuro' | 'equipo';
const CLAVE_MODO = 'maquita_tema';

const temaDelEquipo = typeof window !== 'undefined' && typeof window.matchMedia === 'function'
  ? window.matchMedia('(prefers-color-scheme: dark)') : null;

function leerModo(): ModoTema {
  try {
    const v = localStorage.getItem(CLAVE_MODO);
    if (v === 'claro' || v === 'oscuro' || v === 'equipo') return v;
    return localStorage.getItem('theme') === 'dark' ? 'oscuro' : 'claro';
  } catch { return 'claro'; }
}

function esOscuro(modo: ModoTema): boolean {
  return modo === 'oscuro' || (modo === 'equipo' && !!temaDelEquipo?.matches);
}

interface ThemeState {
  dark: boolean;
  modo: ModoTema;
  /** Botón de la barra superior: pasa de claro a oscuro y al revés (deja de seguir al equipo). */
  toggle: () => void;
  setModo: (modo: ModoTema) => void;
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  modo: leerModo(),
  dark: esOscuro(leerModo()),
  setModo: (modo) => {
    const dark = esOscuro(modo);
    try {
      localStorage.setItem(CLAVE_MODO, modo);
      localStorage.setItem('theme', dark ? 'dark' : 'light');
    } catch { /* sin almacenamiento: vale para esta visita */ }
    set({ modo, dark });
  },
  toggle: () => get().setModo(get().dark ? 'claro' : 'oscuro'),
}));

// «Según el equipo»: si el equipo cambia de claro a oscuro (o al revés), el correo lo sigue al momento.
temaDelEquipo?.addEventListener?.('change', () => {
  if (useThemeStore.getState().modo === 'equipo') useThemeStore.setState({ dark: esOscuro('equipo') });
});
