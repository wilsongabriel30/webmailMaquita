import { useEffect, useState } from 'react';

/** Manifiesto de la app Android publicado por el servidor (AM-11). */
export interface ManifiestoApp { versionName: string; tamano?: number; fecha?: string; notas?: string; }

const RUTA_JSON = '/webmail/descargas/maquita-mail.json';
let cache: Promise<ManifiestoApp | null> | null = null;

/** Dentro de la propia app no tiene sentido ofrecer su descarga. */
export function dentroDeLaApp(): boolean {
  return typeof navigator !== 'undefined' && /MaquitaMail(App)?\//.test(navigator.userAgent);
}

/** URL del APK en el host actual: vale igual en los portales por empresa. */
export function urlApk(): string {
  return `${window.location.origin}/webmail/descargas/maquita-mail.apk`;
}

export function textoTamano(m: ManifiestoApp): string {
  return m.tamano ? `${(m.tamano / 1048576).toFixed(1)} MB` : '';
}

function cargar(): Promise<ManifiestoApp | null> {
  if (!cache) {
    cache = fetch(RUTA_JSON, { cache: 'no-store' })
      .then(r => (r.ok && (r.headers.get('content-type') || '').includes('json') ? r.json() : null))
      .then(j => (j && typeof j.versionName === 'string' ? (j as ManifiestoApp) : null))
      .catch(() => null);
  }
  return cache;
}

/** Devuelve el manifiesto si hay versión publicada y no se está dentro de la app; si no, null. */
export function useManifiestoApp(): ManifiestoApp | null {
  const [m, setM] = useState<ManifiestoApp | null>(null);
  useEffect(() => {
    if (dentroDeLaApp()) return;
    let vivo = true;
    cargar().then(v => { if (vivo) setM(v); });
    return () => { vivo = false; };
  }, []);
  return m;
}
