// Qué parte del correo se corrige y cómo se aplica la propuesta en el editor.
// Con texto seleccionado se corrige solo la selección; sin selección, todo lo que escribió la persona
// (la firma y el mensaje citado viven fuera del editor y no se tocan).
import DOMPurify from 'dompurify';
import type { Editor } from '@tiptap/react';

export type Alcance = { texto: string; fragmento: boolean; desde: number; hasta: number };

export const ETIQUETAS_PERMITIDAS = ['p', 'br', 'ul', 'ol', 'li', 'strong', 'b', 'em', 'i', 'u'];

export function limpiarHtml(html: string): string {
  return DOMPurify.sanitize(html, { ALLOWED_TAGS: ETIQUETAS_PERMITIDAS, ALLOWED_ATTR: [] });
}

/** Devuelve el alcance o un mensaje que explica por qué no se puede. */
export function tomarAlcance(editor: Editor): Alcance | string {
  const { from, to, empty } = editor.state.selection;
  if (!empty) {
    const texto = editor.state.doc.textBetween(from, to, '\n\n', ' ').trim();
    if (texto.length >= 3) return { texto, fragmento: true, desde: from, hasta: to };
  }
  const texto = editor.getText({ blockSeparator: '\n\n' }).trim();
  if (texto.length < 10) return 'Escriba al menos una oración para corregir.';
  // Reemplazar el correo entero borraría imágenes y tablas: en ese caso, por partes.
  if (/<(img|table)\b/i.test(editor.getHTML())) {
    return 'El mensaje tiene imágenes o tablas: seleccione el texto que quiere corregir.';
  }
  return { texto, fragmento: false, desde: 0, hasta: editor.state.doc.content.size };
}

export function aplicarPropuesta(editor: Editor, alcance: Alcance, html: string) {
  let contenido = limpiarHtml(html);
  if (!alcance.fragmento) {
    editor.chain().focus().setContent(contenido).run();
    return;
  }
  // Un fragmento dentro de un mismo párrafo vuelve sin <p>, para no partir el párrafo en dos.
  const $desde = editor.state.doc.resolve(alcance.desde);
  const $hasta = editor.state.doc.resolve(alcance.hasta);
  const unSoloParrafo = $desde.sameParent($hasta) && $desde.parent.type.name === 'paragraph';
  const m = contenido.trim().match(/^<p>([\s\S]*)<\/p>$/);
  if (unSoloParrafo && m && !m[1].includes('<p>')) contenido = m[1];
  editor.chain().focus().insertContentAt({ from: alcance.desde, to: alcance.hasta }, contenido).run();
}
