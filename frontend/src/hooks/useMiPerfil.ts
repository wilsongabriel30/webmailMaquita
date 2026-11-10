/**
 * useMiPerfil — foto efectiva y nombre de la persona conectada (GET /contacts/foto), una vez por sesión (09/11/2026).
 *
 * Lo usa la burbuja de la esquina superior derecha. «Mi foto» (Configuración) avisa con el evento
 * `mi-foto-actualizada` cuando sube o quita la foto para que la burbuja se refresque sin recargar.
 */
import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { olvidarAvatar } from './useAvatares';

export interface MiPerfil {
  photo_url: string;
  display_name: string;
  foto_raices_url?: string;
  foto_propia_url?: string;
  origen_actual?: '' | 'nomina' | 'propio';
  la_gestiona_nomina?: boolean;
}

export const EVENTO_MI_FOTO = 'mi-foto-actualizada';

let perfil: MiPerfil | null = null;
let promesa: Promise<MiPerfil | null> | null = null;
const oyentes = new Set<() => void>();

function cargar(): Promise<MiPerfil | null> {
  if (!promesa) {
    promesa = api.get<MiPerfil>('/contacts/foto')
      .then(p => { perfil = p; return p; })
      .catch(() => null)
      .finally(() => { oyentes.forEach(f => f()); });
  }
  return promesa;
}

/** Avisa a quien muestre el perfil propio de que cambió (lo llama «Mi foto»). */
export function avisarMiFotoActualizada(correo?: string): void {
  if (correo) olvidarAvatar(correo);
  window.dispatchEvent(new Event(EVENTO_MI_FOTO));
}

export function useMiPerfil(): MiPerfil | null {
  const [, refrescar] = useState(0);
  useEffect(() => {
    const listo = () => refrescar(n => n + 1);
    oyentes.add(listo);
    if (!perfil) cargar();
    const alCambiar = () => { promesa = null; cargar(); };
    window.addEventListener(EVENTO_MI_FOTO, alCambiar);
    return () => { oyentes.delete(listo); window.removeEventListener(EVENTO_MI_FOTO, alCambiar); };
  }, []);
  return perfil;
}
