// Importancia (Alta o Baja) del correo que se está redactando (28/10/2026).
// La cinta de redacción vive en la barra principal y puede haber varias redacciones abiertas:
// se recuerda por editor y el cambio se avisa con el editor, para que solo lo aplique esa ventana.
import { useState } from 'react';
import type { Editor } from '@tiptap/react';

export type Importancia = 'normal' | 'high' | 'low';

export const EVENTO_IMPORTANCIA = 'compose-importance-change';

export function useImportanciaRedaccion(editor: Editor | null) {
  const [porEditor, setPorEditor] = useState<Map<Editor, Importancia>>(() => new Map());
  const importancia: Importancia = (editor && porEditor.get(editor)) || 'normal';

  const cambiar = (valor: Importancia) => {
    if (!editor) return;
    setPorEditor(prev => new Map(prev).set(editor, valor));
    window.dispatchEvent(new CustomEvent(EVENTO_IMPORTANCIA, { detail: { editor, valor } }));
  };

  return { importancia, cambiar };
}
