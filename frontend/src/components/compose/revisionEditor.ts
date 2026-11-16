/**
 * Botón «Editor» del redactor: la IA revisa el borrador y propone una versión corregida.
 *
 * Usa `POST /api/ai/review`, la IA configurable de la instalación. Antes llamaba a `/api/ia/review`,
 * que solo existe donde hay una pasarela de IA externa publicada por nginx: en las demás instalaciones
 * daba 404 y «Error al conectar con IA» (informe de Andes, 15/11/2026).
 */
import type { Editor } from '@tiptap/react';
import { api } from '../../api/client';
import { textoAParrafos } from '../../lib/autocompletar';
import { showToast } from '../common/Toast';
import { AVISO_IA_SIN_RESPUESTA, avisarSiNoHayIA } from './sinIA';

interface Revision { score: number; feedback: string; suggestions: string[]; corrected_text: string | null }

/** El servidor no revisa textos más cortos. */
const MINIMO_CARACTERES = 10;

export async function revisarBorradorConIA(editor: Editor | null, asunto: string): Promise<void> {
  if (!editor || editor.isDestroyed) return;
  const texto = editor.getText().trim();
  if (!texto) { showToast('No hay texto para revisar'); return; }
  if (texto.length < MINIMO_CARACTERES) { showToast('Escriba un poco más de texto para poder revisarlo'); return; }
  if (await avisarSiNoHayIA()) return;
  showToast('Revisando con IA…');
  let revision: Revision;
  try {
    revision = await api.post<Revision>('/ai/review', { text: texto, subject: asunto });
  } catch {
    showToast(AVISO_IA_SIN_RESPUESTA);
    return;
  }
  // La ventana pudo cerrarse mientras la IA respondía: ya no hay dónde mostrar ni aplicar nada.
  if (editor.isDestroyed) return;
  const sugerencias = revision.suggestions?.length
    ? `\n\nSugerencias:\n${revision.suggestions.map((s) => `• ${s}`).join('\n')}`
    : '';
  const resumen = `Puntuación: ${revision.score}/10\n\n${revision.feedback}${sugerencias}`;
  if (revision.corrected_text && confirm(`${resumen}\n\n¿Desea aplicar la versión corregida?`)) {
    if (editor.isDestroyed) return;
    editor.commands.setContent(textoAParrafos(revision.corrected_text));
    showToast('Correcciones aplicadas');
  } else if (!revision.corrected_text) {
    alert(resumen);
  }
}
