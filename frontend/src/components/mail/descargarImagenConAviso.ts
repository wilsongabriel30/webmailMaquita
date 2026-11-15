/**
 * descargarImagenConAviso.ts — «Descargar imagen» con su aviso (13/11/2026).
 * Lo usan el menú «⋮» de las imágenes del cuerpo (MenuImagenCuerpo.tsx) y el visor en grande
 * (VisorImagenCuerpo.tsx). Solo avisa si hace falta: se abrió en otra pestaña o no se pudo.
 */
import { descargarImagen } from '../../lib/descargarImagen';
import { showToast } from '../common/Toast';

export async function descargarImagenConAviso(src: string, alt = ''): Promise<void> {
  const resultado = await descargarImagen(src, alt);
  if (resultado === 'pestana') showToast('La imagen está en otro servidor y se abrió en una pestaña nueva: guárdela desde allí con clic derecho → «Guardar imagen como».');
  else if (resultado === 'error') showToast('No se pudo descargar la imagen. Inténtelo de nuevo.');
}
