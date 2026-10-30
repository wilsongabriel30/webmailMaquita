/**
 * Estado del panel lateral del asistente: si está abierto y la conversación en curso.
 * La conversación vive solo en memoria (se pierde al recargar); lo único que se recuerda
 * en el navegador es si el panel estaba abierto.
 */
import { create } from 'zustand';

export interface FuenteRag {
  subject: string;
  sender: string;
  sim: number;
  /** Carpeta y UID del correo, para abrirlo desde el panel. */
  folder?: string;
  uid?: string;
}

export interface MensajeAsistente {
  id: number;
  rol: 'usuario' | 'asistente';
  texto: string;
  fuentes?: FuenteRag[];
  error?: boolean;
}

const CLAVE_ABIERTO = 'asistente_lateral_abierto';

function leerAbierto(): boolean {
  try { return localStorage.getItem(CLAVE_ABIERTO) === '1'; } catch { return false; }
}

function guardarAbierto(abierto: boolean): void {
  try { localStorage.setItem(CLAVE_ABIERTO, abierto ? '1' : '0'); } catch { /* sin almacenamiento */ }
}

interface EstadoAsistente {
  abierto: boolean;
  mensajes: MensajeAsistente[];
  alternar: () => void;
  cerrar: () => void;
  agregar: (m: Omit<MensajeAsistente, 'id'>) => void;
  reiniciar: () => void;
}

let siguienteId = 1;

export const useAsistenteStore = create<EstadoAsistente>((set, get) => ({
  abierto: leerAbierto(),
  mensajes: [],
  alternar: () => {
    const abierto = !get().abierto;
    guardarAbierto(abierto);
    set({ abierto });
  },
  cerrar: () => {
    guardarAbierto(false);
    set({ abierto: false });
  },
  agregar: (m) => set({ mensajes: [...get().mensajes, { ...m, id: siguienteId++ }] }),
  reiniciar: () => set({ mensajes: [] }),
}));
