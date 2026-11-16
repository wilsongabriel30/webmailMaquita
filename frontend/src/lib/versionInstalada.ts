// Versión instalada de la interfaz. La fija la compilación (vite.config.ts → complementos/version)
// con lo que da `git describe`, igual que el panel de administración. Vacía si no se conoce.

declare const __VERSION_INSTALADA__: string | undefined;

export function versionInstalada(): string {
  return typeof __VERSION_INSTALADA__ === 'string' ? __VERSION_INSTALADA__ : '';
}

/** Primera línea de «Obtener diagnósticos»: nombre del producto y versión instalada. */
export function lineaDeVersion(nombre: string, version: string = versionInstalada()): string {
  return version ? `${nombre} ${version}` : `${nombre} (versión no disponible)`;
}
