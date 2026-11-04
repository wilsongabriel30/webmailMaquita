import type { Editor, JSONContent } from '@tiptap/core';
import { unirSugerencia } from '../../lib/autocompletar';

/** Texto plano con saltos de línea simples → nodos de texto y saltos de línea de TipTap. */
function enNodos(texto: string): JSONContent[] {
  const nodos: JSONContent[] = [];
  texto.split('\n').forEach((linea, i) => {
    if (i > 0) nodos.push({ type: 'hardBreak' });
    if (linea) nodos.push({ type: 'text', text: linea });
  });
  return nodos;
}

/**
 * Agrega la continuación de la IA al final del texto, unida a la palabra a medias o con un
 * espacio solo cuando corresponde (ver `unirSugerencia`). Los párrafos que trae la sugerencia
 * van como párrafos nuevos. Se insertan nodos (no HTML): un «<» del texto no se interpreta.
 */
export function insertarContinuacion(editor: Editor, sugerencia: string, continuaPalabra = false) {
  const { enLinea, parrafos } = unirSugerencia(editor.getText(), sugerencia, continuaPalabra);
  // Comandos sucesivos y no una cadena: en una cadena, «splitBlock» seguido de «insertContent»
  // calcula posiciones sobre el documento anterior («Position out of range»).
  editor.commands.focus('end');
  if (enLinea) editor.commands.insertContent(enNodos(enLinea));
  for (const p of parrafos) {
    editor.commands.splitBlock();
    editor.commands.insertContent(enNodos(p));
  }
}
