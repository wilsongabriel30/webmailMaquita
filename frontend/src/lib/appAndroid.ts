import { useEffect, useState } from 'react';
import { nombreApp } from './marca';

/** Manifiesto de la app Android publicado por el servidor (AM-11). */
export interface ManifiestoApp { versionName: string; tamano?: number; fecha?: string; notas?: string; nombre?: string; }

const RUTA_JSON = '/webmail/descargas/maquita-mail.json';
let cache: Promise<ManifiestoApp | null> | null = null;

// Las rutas del servidor (maquita-mail.apk / .json) son internas: no cambian para no romper a
// quien ya tiene la app (su actualizador las consulta). Lo que ve la persona es el nombre del
// archivo descargado, que sigue a la marca: ver nombreArchivoApk().
/** Dentro de la propia app no tiene sentido ofrecer su descarga. «CorreoApp» es el agente neutro
 *  de la app genérica; «MaquitaMail» el de la app de la casa, que se sigue reconociendo. */
export function dentroDeLaApp(): boolean {
  return typeof navigator !== 'undefined' && /(MaquitaMail(App)?|CorreoApp)\//.test(navigator.userAgent);
}

/** URL del APK en el host actual: vale igual en los portales por empresa. */
export function urlApk(): string {
  return `${window.location.origin}/webmail/descargas/maquita-mail.apk`;
}

/** Nombre del archivo que se guarda al descargar: el del producto (`app_name`), apto para archivo. */
export function nombreArchivoApk(nombre: string = nombreApp()): string {
  const limpio = nombre.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^A-Za-z0-9._-]+/g, '-').replace(/^[-.]+|[-.]+$/g, '');
  return `${limpio || 'correo'}.apk`;
}

/** Descarga el APK con el nombre de la marca (mismo origen: el atributo download se respeta). */
export function descargarApk(): void {
  const a = document.createElement('a');
  a.href = urlApk();
  a.download = nombreArchivoApk();
  a.rel = 'noopener';
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export function textoTamano(m: ManifiestoApp): string {
  return m.tamano ? `${(m.tamano / 1048576).toFixed(1)} MB` : '';
}

/** Manifiesto publicado (null si no hay versión); se lee una sola vez por sesión. */
export function cargarManifiestoApp(): Promise<ManifiestoApp | null> {
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
    cargarManifiestoApp().then(v => { if (vivo) setM(v); });
    return () => { vivo = false; };
  }, []);
  return m;
}
