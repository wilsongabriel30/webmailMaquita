/**
 * Botones «Aplicación móvil» de la cinta (correo y calendario) y del menú de Ayuda.
 *
 * Antes mostraban «Aplicación móvil: próximamente» aunque la app Android ya está publicada
 * (manifiesto en /webmail/descargas/maquita-mail.json). Ahora: si hay versión publicada se abre
 * la descarga del APK; si no (o si ya se está dentro de la app), se lleva a Configuración →
 * «Configurar mi correo», que explica cómo usar Outlook, el celular u otros programas.
 */
import { cargarManifiestoApp, dentroDeLaApp, urlApk } from './appAndroid';

export const RUTA_CONFIGURAR_CORREO = '/settings?tab=mailsetup';

/**
 * @param navegar función de navegación interna (useNavigate); si no se pasa, se usa la URL completa.
 * @returns 'apk' si abrió la descarga, 'configurar' si llevó a la guía, 'dentro' si ya está en la app.
 */
export async function abrirAppMovil(navegar?: (ruta: string) => void): Promise<'apk' | 'configurar' | 'dentro'> {
  if (dentroDeLaApp()) return 'dentro';
  const m = await cargarManifiestoApp();
  if (m) {
    window.open(urlApk(), '_blank', 'noopener');
    return 'apk';
  }
  if (navegar) navegar(RUTA_CONFIGURAR_CORREO);
  else window.location.href = `/webmail${RUTA_CONFIGURAR_CORREO}`;
  return 'configurar';
}
