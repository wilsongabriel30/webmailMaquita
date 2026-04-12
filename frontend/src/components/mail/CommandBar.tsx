import { useMailStore } from '../../store/mailStore';
import { api } from '../../api/client';

export function CommandBar() {
  const {
    currentFolder, searchQuery, setSearchQuery, filter, setFilter,
    selectedUids, clearSelection, messages, selectAll,
  } = useMailStore();

  const hasSelection = selectedUids.size > 0;
  const allSelected = messages.length > 0 && selectedUids.size === messages.length;

  const handleBulkAction = async (action: string, destFolder?: string) => {
    if (selectedUids.size === 0) return;
    try {
      await api.post(`/mail/bulk-action/${encodeURIComponent(currentFolder)}`, {
        uids: Array.from(selectedUids),
        action,
        dest_folder: destFolder || '',
      });
      clearSelection();
      useMailStore.getState().setLoadingMessages(true);
      // Trigger refetch
      window.dispatchEvent(new CustomEvent('refresh-messages'));
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="h-11 bg-white border-b border-[#edebe9] flex items-center px-3 gap-1 shrink-0">
      {/* Select all checkbox */}
      <button onClick={() => allSelected ? clearSelection() : selectAll()}
        className="w-8 h-8 rounded flex items-center justify-center hover:bg-[#e1dfdd] transition-colors">
        <div className={`w-4 h-4 border-2 rounded-sm flex items-center justify-center ${
          allSelected ? 'bg-[#0078d4] border-[#0078d4]' : hasSelection ? 'border-[#0078d4] bg-[#0078d4]/20' : 'border-[#8a8886]'
        }`}>
          {(allSelected || hasSelection) && (
            <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
          )}
        </div>
      </button>

      {hasSelection ? (
        <>
          <span className="text-xs text-[#605e5c] mx-2">{selectedUids.size} seleccionado{selectedUids.size > 1 ? 's' : ''}</span>
          <CmdBtn icon="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" label="Eliminar" onClick={() => handleBulkAction('delete')} danger />
          <CmdBtn icon="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" label="Archivar" onClick={() => handleBulkAction('archive')} />
          <CmdBtn icon="M3 19v-8.93a2 2 0 01.89-1.664l7-4.666a2 2 0 012.22 0l7 4.666A2 2 0 0121 10.07V19M3 19a2 2 0 002 2h14a2 2 0 002-2M3 19l6.75-4.5M21 19l-6.75-4.5M3 10l6.75 4.5M21 10l-6.75 4.5" label="Marcar leído" onClick={() => handleBulkAction('mark_read')} />
        </>
      ) : (
        <>
          {/* Filters */}
          <div className="flex items-center gap-px ml-2">
            {(['all', 'unread', 'flagged'] as const).map((f) => (
              <button key={f} onClick={() => setFilter(f)}
                className={`px-2.5 py-1 text-xs rounded transition-colors ${
                  filter === f ? 'bg-[#e1dfdd] text-[#323130] font-medium' : 'text-[#605e5c] hover:bg-[#e1dfdd]'
                }`}>
                {f === 'all' ? 'Todos' : f === 'unread' ? 'No leídos' : 'Marcados'}
              </button>
            ))}
          </div>
        </>
      )}

      <div className="flex-1" />

      {/* Search */}
      <div className="relative w-64">
        <svg className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-[#8a8886]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input id="search-input" type="text" value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Buscar correos..."
          className="w-full pl-8 pr-3 py-1.5 text-xs bg-[#f3f2f1] border border-transparent rounded focus:bg-white focus:border-[#0078d4] outline-none transition-colors" />
      </div>
    </div>
  );
}

function CmdBtn({ icon, label, onClick, danger }: { icon: string; label: string; onClick: () => void; danger?: boolean }) {
  return (
    <button onClick={onClick} title={label}
      className={`h-8 px-2 rounded flex items-center gap-1.5 text-xs transition-colors ${
        danger ? 'text-[#a4262c] hover:bg-red-50' : 'text-[#323130] hover:bg-[#e1dfdd]'
      }`}>
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={icon} />
      </svg>
      <span className="hidden sm:inline">{label}</span>
    </button>
  );
}
