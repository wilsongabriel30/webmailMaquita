/**
 * ComposePopup — Standalone compose page for popup window
 * Opens via window.open() from calendar or other sections
 * Includes Toolbar ribbon (same as main mail) + ComposePanel
 */
import { useEffect, useRef } from 'react';
import { ComposePanel } from '../compose/ComposePanel';
import { Toolbar } from '../mail/Toolbar';
import { ToastContainer } from '../common/ToastContainer';
import { useMailStore } from '../../store/mailStore';
import { useAuthStore } from '../../store/authStore';
import { useApariencia } from '../../hooks/useApariencia';
import { tomarDatosDeRedaccion } from '../../lib/redaccionEnVentana';

export function ComposePopup() {
  useApariencia({ soloClaro: true });   // color principal elegido en Configuración → Apariencia
  const composeWindows = useMailStore(s => s.composeWindows);
  const openCompose = useMailStore(s => s.openCompose);
  const restoreCompose = useMailStore(s => s.restoreCompose);
  const { user, setUser } = useAuthStore();

  // Authenticate if needed
  useEffect(() => {
    if (!user) {
      fetch('/api/auth/me', { credentials: 'include' })
        .then(r => r.json())
        .then(d => setUser(d.user || null))
        .catch(() => setUser(null));
    }
  }, []);

  const yaInicio = useRef(false);
  const tuvoRedaccion = useRef(false);

  // Al montar: si la ventana recibió datos de redacción (handoff desde la ventana principal),
  // abrir ESA redacción; si no, una nueva vacía. Una sola vez.
  useEffect(() => {
    if (!user || yaInicio.current) return;
    yaInicio.current = true;
    const traspaso = tomarDatosDeRedaccion();
    openCompose(traspaso ? traspaso.mode : 'new', traspaso?.data || undefined);
  }, [user]);

  // Esta página ES una ventana de redacción propia: cuando ComposePanel cierra la redacción
  // al enviar o cancelar (composeWindows queda vacío tras haber tenido una), la ventana se
  // cierra sola con window.close().
  useEffect(() => {
    if (composeWindows.length > 0) { tuvoRedaccion.current = true; return; }
    if (tuvoRedaccion.current && user) { try { window.close(); } catch { /* vacío */ } }
  }, [composeWindows, user]);

  // If minimized, auto-restore (popup has no minimized bar)
  useEffect(() => {
    const minimized = composeWindows.find(w => w.minimized);
    if (minimized) {
      restoreCompose(minimized.id);
    }
  }, [composeWindows]);

  const activeCompose = composeWindows.find(w => !w.minimized);

  if (!user) {
    return (
      <div className="h-screen flex items-center justify-center bg-[#f3f2f1]">
        <div className="animate-spin w-8 h-8 border-2 border-[#0078d4] border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-white overflow-hidden">
      {/* Toolbar with ribbon (same as main mail) */}
      <div className="shrink-0 relative z-[50]">
        <Toolbar />
      </div>

      {/* Compose panel */}
      <div className="flex-1 min-h-0 overflow-auto">
        {activeCompose ? (
          <ComposePanel win={activeCompose} />
        ) : (
          <div className="flex-1 flex items-center justify-center text-[#605e5c] text-[14px] py-8">
            <div className="animate-spin w-6 h-6 border-2 border-[#0078d4] border-t-transparent rounded-full mr-3" />
            Iniciando editor...
          </div>
        )}
      </div>

      <ToastContainer />
    </div>
  );
}
