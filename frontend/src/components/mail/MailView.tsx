import { Toolbar } from './Toolbar';
import { MessageList } from './MessageList';
import { MessageView } from './MessageView';
import { ComposePanel } from '../compose/ComposePanel';
import { ToastContainer } from '../common/Toast';
import { useMailStore } from '../../store/mailStore';

export function MailView() {
  const { composeWindows, restoreCompose, readingPane } = useMailStore();

  const activeCompose = composeWindows.find(w => !w.minimized);
  const minimized = composeWindows.filter(w => w.minimized);

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Toolbar — outside overflow so dropdowns work */}
      <div className="shrink-0 relative z-[50]">
        <Toolbar />
      </div>

      {/* Content: layout changes based on readingPane */}
      {readingPane === 'right' && (
        /* ── DERECHA: lista izquierda + lectura derecha (default Outlook) ── */
        <div className="flex-1 flex overflow-hidden min-h-0">
          <MessageList />
          <div className="flex-1 min-w-0 flex flex-col">
            {activeCompose ? (
              <ComposePanel win={activeCompose} />
            ) : (
              <MessageView />
            )}
          </div>
        </div>
      )}

      {readingPane === 'bottom' && (
        /* ── ABAJO: lista arriba + lectura abajo (split horizontal) ── */
        <div className="flex-1 flex flex-col overflow-hidden min-h-0">
          <div className="h-[45%] min-h-[150px] border-b border-[#edebe9] overflow-hidden">
            <MessageList />
          </div>
          <div className="flex-1 overflow-hidden">
            {activeCompose ? (
              <ComposePanel win={activeCompose} />
            ) : (
              <MessageView />
            )}
          </div>
        </div>
      )}

      {readingPane === 'off' && (
        /* ── OCULTO: solo lista, lectura en pantalla completa al hacer click ── */
        <div className="flex-1 flex overflow-hidden min-h-0">
          {activeCompose ? (
            <ComposePanel win={activeCompose} />
          ) : useMailStore.getState().selectedMessage ? (
            <MessageView />
          ) : (
            <MessageList />
          )}
        </div>
      )}

      {/* Minimized compose tabs */}
      {minimized.length > 0 && (
        <div className="flex gap-1 px-2 py-1 bg-[#faf9f8] border-t border-[#edebe9] shrink-0">
          {minimized.map(win => (
            <button key={win.id} onClick={() => restoreCompose(win.id)}
              className="bg-white border border-[#edebe9] rounded-[2px] px-3 py-1.5 text-[12px] text-[#323130] font-medium hover:bg-[#f3f2f1] transition-colors max-w-[200px] truncate flex items-center gap-1.5 shadow-sm">
              <svg className="w-3 h-3 text-[#0078d4] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
              {win.data.subject || 'Nuevo mensaje'}
            </button>
          ))}
        </div>
      )}

      <ToastContainer />
    </div>
  );
}
