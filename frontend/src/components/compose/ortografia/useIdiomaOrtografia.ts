/**
 * Idioma del corrector ortográfico del redactor.
 *
 * - Por defecto, español de Ecuador.
 * - Si se responde o reenvía un correo en inglés, empieza en inglés.
 * - Mientras la persona escribe, si el texto está claramente en inglés (o en español), cambia
 *   solo (detección local, sin enviar nada a ningún servidor).
 * - Si la persona lo cambia a mano, manda su elección y se recuerda para ese mensaje.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import type { Editor } from '@tiptap/react';
import { detectarIdioma, textoDeHtml } from '../../../lib/idiomaTexto';
import {
  POR_DEFECTO, deTexto, eleccionGuardada, guardarEleccion, type IdiomaOrtografia,
} from './idiomas';

const ESPERA_MS = 1200;

/** `claveVentana` y `claveBorrador` identifican el mensaje para recordar la elección a mano. */
export function useIdiomaOrtografia(
  editor: Editor | null, claveVentana: string, claveBorrador: string | null, htmlRespondido: string,
) {
  const llaves = useMemo(() => [claveVentana, claveBorrador].filter((c): c is string => !!c), [claveVentana, claveBorrador]);
  const [elegido, setElegido] = useState<IdiomaOrtografia | null>(() => eleccionGuardada(llaves));
  const [delTexto, setDelTexto] = useState<IdiomaOrtografia | null>(null);
  const delCorreo = useMemo(() => {
    const d = htmlRespondido ? detectarIdioma(textoDeHtml(htmlRespondido)) : null;
    return d ? deTexto(d) : null;
  }, [htmlRespondido]);
  // Manda la elección a mano; luego lo que se escribe; luego el correo al que se responde.
  const idioma = elegido ?? delTexto ?? delCorreo ?? POR_DEFECTO;

  // Mientras escribe: detección con una pausa, solo si no eligió a mano.
  useEffect(() => {
    if (!editor || elegido) return;
    let reloj: ReturnType<typeof setTimeout> | undefined;
    const alCambiar = () => {
      clearTimeout(reloj);
      reloj = setTimeout(() => {
        if (editor.isDestroyed) return;
        const d = detectarIdioma(editor.getText());
        if (d) setDelTexto(deTexto(d));
      }, ESPERA_MS);
    };
    editor.on('update', alCambiar);
    return () => { clearTimeout(reloj); editor.off('update', alCambiar); };
  }, [editor, elegido]);

  // El corrector del navegador toma el idioma del atributo `lang` del cuerpo del correo.
  useEffect(() => {
    const dom = editor && !editor.isDestroyed ? (editor.view.dom as HTMLElement) : null;
    if (!dom) return;
    dom.setAttribute('lang', idioma);
    // Apagar y encender el corrector hace que el navegador vuelva a revisar con el idioma nuevo.
    dom.setAttribute('spellcheck', 'false');
    const r = requestAnimationFrame(() => dom.setAttribute('spellcheck', 'true'));
    return () => { cancelAnimationFrame(r); dom.setAttribute('spellcheck', 'true'); };
  }, [editor, idioma]);

  // Cuando la ventana recibe su borrador (primer guardado), la elección pasa también a él.
  useEffect(() => { if (elegido) guardarEleccion(llaves, elegido); }, [llaves]); // eslint-disable-line react-hooks/exhaustive-deps

  const elegir = useCallback((nuevo: IdiomaOrtografia) => {
    setElegido(nuevo);
    guardarEleccion(llaves, nuevo);
  }, [llaves]);

  return { idioma, manual: !!elegido, elegir };
}
