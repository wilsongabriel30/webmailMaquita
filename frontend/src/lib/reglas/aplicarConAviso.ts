import { dismissToast, showToast } from '../../components/common/Toast';
import { aplicarReglaAExistentes, textoResultado } from './aplicarRegla';
import type { Regla } from './tipos';

/* Aplicar una regla a los correos ya recibidos avisando del progreso y del resultado
   (lo usan la ventana de la regla y el botón «Aplicar ahora» de Ajustes). */

function motivo(err: unknown): string {
  const m = err instanceof Error ? err.message : '';
  return m && !/^HTTP \d+$/.test(m) && m !== 'Session expired' ? m : '';
}

/** Aplica la regla a lo ya recibido avisando del progreso y del resultado. Devuelve true si se aplicó. */
export async function aplicarConAviso(regla: Regla): Promise<boolean> {
  const id = showToast(`Aplicando «${regla.name}» a los correos anteriores…`, undefined, { fijo: true });
  try {
    const r = await aplicarReglaAExistentes(regla);
    dismissToast(id);
    showToast(textoResultado(r));
    if (r.movidos || r.papelera) window.dispatchEvent(new CustomEvent('refresh-messages'));
    return true;
  } catch (err) {
    dismissToast(id);
    showToast(`No se pudo aplicar la regla a los correos anteriores${motivo(err) ? `: ${motivo(err)}` : ''}`, undefined, { fijo: true });
    return false;
  }
}
