/**
 * ComposePopup — Standalone compose page for popup window
 * Opens via window.open() from calendar or other sections
 * Includes Toolbar ribbon (same as main mail) + ComposePanel
 */
import { useEffect } from 'react';
import { ComposePanel } from '../compose/ComposePanel';
import { Toolbar } from '../mail/Toolbar';
import { ToastContainer } from '../common/Toast';
import { useMailStore } from '../../store/mailStore';
import { useAuthStore } from '../../store/authStore';

export function ComposePopup() {
  const { composeWindows, openCompose, restoreCompose } = useMailStore();
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

  // Auto-open compose on mount
  useEffect(() => {
    if (user && composeWindows.length === 0) {
      openCompose('new');
    }
  }, [user]);

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
