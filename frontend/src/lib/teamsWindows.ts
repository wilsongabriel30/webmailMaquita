import { useEffect, useState } from 'react';

/** Manifiesto de la aplicación de Windows (`/static/teams/teams-windows-version.json`), el mismo
 *  que usa la app para actualizarse sola: el enlace siempre apunta a la última versión publicada.
 *  `nombre` (opcional) es el de la app de la organización; no va escrito en el código (lo comprueba el CI). */
export interface ManifiestoTeams { version: string; url: string; tamano?: number; fecha?: string; nombre?: string; }

let enCurso: Promise<ManifiestoTeams | null> | null = null;

function cargar(): Promise<ManifiestoTeams | null> {
  if (!enCurso) {
    enCurso = fetch('/static/teams/teams-windows-version.json', { cache: 'no-store' })
      .then(r => (r.ok ? r.json() : null))
      .then(d => (d && d.version && d.url ? (d as ManifiestoTeams) : null))
      .catch(() => null);
    // Se vuelve a pedir pasados 10 minutos, por si se publica una versión nueva con la página abierta.
    setTimeout(() => { enCurso = null; }, 10 * 60 * 1000);
  }
  return enCurso;
}

export function useManifiestoTeams(): ManifiestoTeams | null {
  const [m, setM] = useState<ManifiestoTeams | null>(null);
  useEffect(() => {
    let vivo = true;
    cargar().then(d => { if (vivo) setM(d); });
    return () => { vivo = false; };
  }, []);
  return m;
}

export function megasTeams(bytes?: number): string {
  return bytes ? `${Math.round(bytes / 1048576)} MB` : '';
}

/** La app es para computadoras con Windows: en el celular no se ofrece. */
export function esCelular(): boolean {
  return /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
}
