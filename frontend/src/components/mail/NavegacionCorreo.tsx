/**
 * Barra del asunto como Outlook (07/11/2026): «X» a la izquierda para cerrar el correo y volver a
 * la lista, y «‹ ›» a la derecha para pasar al correo anterior o al siguiente de la lista.
 * Las flechas usan el MISMO camino que las teclas ↑/↓ (hooks/useKeyboardShortcuts.ts): la lista
 * visible, el resaltado y la apertura sin ráfagas ya están resueltos allí.
 * En la ventana propia del correo (/mensaje) no hay lista detrás: no se muestran.
 */
import { useMailStore } from '../../store/mailStore';

const enVentanaPropia = () => window.location.pathname.endsWith('/mensaje');

const estilo: React.CSSProperties = {
  border: '1px solid #d2d0ce', borderRadius: 4, width: 28, height: 26, cursor: 'pointer', color: '#323130',
  flexShrink: 0, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', padding: 0,
};

export function BotonCerrarCorreo() {
  if (enVentanaPropia()) return null;
  return (
    <button type="button" className="bg-white hover:bg-[#f3f2f1]" style={estilo}
      onClick={() => useMailStore.getState().setSelectedMessage(null)}
      title="Cerrar el correo (Esc)" aria-label="Cerrar el correo">
      <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
        <path d="M3 3l10 10M13 3L3 13" />
      </svg>
    </button>
  );
}

function mover(tecla: 'ArrowUp' | 'ArrowDown') {
  document.dispatchEvent(new KeyboardEvent('keydown', { key: tecla, bubbles: true }));
}

export function FlechasCorreo() {
  if (enVentanaPropia()) return null;
  const flecha = (d: string, titulo: string, tecla: 'ArrowUp' | 'ArrowDown') => (
    <button type="button" className="bg-transparent hover:bg-[#f3f2f1]" style={{ ...estilo, border: 'none' }}
      onClick={() => mover(tecla)} title={titulo} aria-label={titulo}>
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d={d} />
      </svg>
    </button>
  );
  return (
    <span style={{ display: 'inline-flex', gap: 2, flexShrink: 0 }}>
      {flecha('M10 3L5 8l5 5', 'Correo anterior (↑)', 'ArrowUp')}
      {flecha('M6 3l5 5-5 5', 'Correo siguiente (↓)', 'ArrowDown')}
    </span>
  );
}
