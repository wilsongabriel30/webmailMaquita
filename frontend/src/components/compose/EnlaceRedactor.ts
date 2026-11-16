/**
 * Enlace del redactor. A diferencia del que trae el editor por defecto, lo que se escribe justo
 * después de un texto vinculado NO queda dentro del enlace: antes, tras vincular una palabra,
 * todo lo que se seguía escribiendo salía azul y subrayado, apuntando al mismo enlace.
 */
import Link from '@tiptap/extension-link';

export const EnlaceRedactor = Link.extend({
  inclusive() {
    return false;
  },
}).configure({ openOnClick: false });
