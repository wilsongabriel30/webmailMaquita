// Versión instalada, para «Ayuda › Obtener diagnósticos» (antes decía siempre «v1.0»).
//
// Es la misma que enseña el panel de administración (Protección → Actualizaciones): la que da
// `git describe` sobre el clon del que se compila (deploy/actualizar/lib/version.py), p. ej.
// «v1.21.1-48-g23b78fc»; sin etiquetas, el commit abreviado. Se fija al compilar: cada actualización
// vuelve a compilar la interfaz, así que siempre corresponde al código que se está sirviendo.
// Quien compile fuera de un clon de git puede indicarla con la variable VERSION_INSTALADA.
import { execFileSync } from 'node:child_process';

const VALIDA = /^[A-Za-z0-9][A-Za-z0-9._+-]{0,79}$/;

export function versionInstalada(carpeta: string = process.cwd(), entorno: Record<string, string | undefined> = process.env): string {
  const indicada = (entorno.VERSION_INSTALADA || '').trim();
  if (indicada) return VALIDA.test(indicada) ? indicada : '';
  try {
    const salida = execFileSync('git', ['describe', '--tags', '--match', 'v*', '--always'], {
      cwd: carpeta, encoding: 'utf8', timeout: 10000, stdio: ['ignore', 'pipe', 'ignore'],
    }).trim();
    return VALIDA.test(salida) ? salida : '';
  } catch {
    return ''; // sin git o fuera de un clon: los diagnósticos dirán que no se conoce
  }
}
