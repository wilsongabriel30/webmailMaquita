import { useState } from 'react';

interface Props {
  onSend: () => void;
  onDiscard: () => void;
  onMinimize: () => void;
  onClose: () => void;
  sending: boolean;
  importance: 'normal' | 'high' | 'low';
  onImportanceChange: (v: 'normal' | 'high' | 'low') => void;
}

export function ComposeHeader({ onSend, onDiscard, onMinimize, onClose, sending, importance, onImportanceChange }: Props) {
  const [showMore, setShowMore] = useState(false);

  return (
    <div className="h-[48px] flex items-center px-3 bg-white border-b border-[#edebe9] shrink-0">
      {/* Send button with caret */}
      <div className="flex items-center">
        <button onClick={onSend} disabled={sending}
          className="h-[32px] pl-4 pr-3 bg-[#0078d4] text-white text-[13px] font-semibold rounded-l-[3px] hover:bg-[#106ebe] disabled:opacity-50 transition-colors flex items-center gap-1.5">
          <svg className="w-[16px] h-[16px]" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2 12l7-2 4-8 4 8 7 2-7 2-4 8-4-8-7-2z" />
          </svg>
          {sending ? 'Enviando...' : 'Enviar'}
        </button>
        <button onClick={() => window.dispatchEvent(new CustomEvent("compose-schedule-send"))} className="h-[32px] px-1.5 bg-[#0078d4] text-white rounded-r-[3px] border-l border-[#106ebe] hover:bg-[#106ebe] transition-colors">
          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
          </svg>
        </button>
      </div>

      {importance !== 'normal' && (
        <span className={`ml-3 text-[11px] px-2 py-0.5 rounded ${importance === 'high' ? 'bg-[#fde7e9] text-[#a4262c]' : 'bg-[#f3f2f1] text-[#605e5c]'}`}>
          {importance === 'high' ? 'Importancia alta' : 'Importancia baja'}
        </span>
      )}

      <div className="flex-1" />

      {/* Right actions */}
      <div className="flex items-center gap-px">
        {/* Attach */}
        <HBtn title="Adjuntar">
          <svg className="w-[16px] h-[16px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
          </svg>
        </HBtn>

        <Separator />

        {/* More actions */}
        <div className="relative">
          <HBtn title="Mas acciones" onClick={() => setShowMore(!showMore)}>
            <svg className="w-[16px] h-[16px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h.01M12 12h.01M19 12h.01M6 12a1 1 0 11-2 0 1 1 0 012 0zm7 0a1 1 0 11-2 0 1 1 0 012 0zm7 0a1 1 0 11-2 0 1 1 0 012 0z" />
            </svg>
          </HBtn>
          {showMore && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setShowMore(false)} />
              <div className="absolute right-0 top-full mt-1 w-52 bg-white rounded shadow-lg border border-[#edebe9] z-50 py-1">
                <p className="px-3 py-1 text-[10px] font-semibold text-[#a19f9d] uppercase">Prioridad</p>
                {(['high','normal','low'] as const).map(p => (
                  <button key={p} onClick={() => { onImportanceChange(p); setShowMore(false); }}
                    className={`w-full text-left px-3 py-[6px] text-[13px] hover:bg-[#f3f2f1] flex items-center gap-2 ${importance === p ? 'text-[#0078d4]' : 'text-[#323130]'}`}>
                    <span className={`w-2 h-2 rounded-full ${p === 'high' ? 'bg-[#d13438]' : p === 'low' ? 'bg-[#a19f9d]' : 'bg-[#0078d4]'}`} />
                    {p === 'high' ? 'Alta' : p === 'low' ? 'Baja' : 'Normal'}
                    {importance === p && <svg className="w-3 h-3 ml-auto text-[#0078d4]" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" /></svg>}
                  </button>
                ))}
                <div className="h-px bg-[#edebe9] my-1" />
                <button onClick={() => { setShowMore(false); }} className="w-full text-left px-3 py-[6px] text-[13px] text-[#323130] hover:bg-[#f3f2f1]">Guardar borrador</button>
                <button onClick={() => { setShowMore(false); }} className="w-full text-left px-3 py-[6px] text-[13px] text-[#323130] hover:bg-[#f3f2f1]">Mostrar De</button>
              </div>
            </>
          )}
        </div>

        <Separator />

        {/* Delete draft */}
        <HBtn title="Eliminar borrador" onClick={onDiscard}>
          <svg className="w-[16px] h-[16px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </HBtn>

        <Separator />

        {/* Minimize */}
        <HBtn title="Minimizar" onClick={onMinimize}>
          <svg className="w-[16px] h-[16px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
          </svg>
        </HBtn>

        {/* Close */}
        <HBtn title="Cerrar" onClick={onClose}>
          <svg className="w-[16px] h-[16px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </HBtn>
      </div>
    </div>
  );
}

function HBtn({ title, onClick, children }: { title: string; onClick?: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick} title={title}
      className="w-[32px] h-[32px] rounded-sm flex items-center justify-center text-[#605e5c] hover:bg-[#f3f2f1] hover:text-[#323130] transition-colors">
      {children}
    </button>
  );
}

function Separator() {
  return <div className="w-px h-[20px] bg-[#edebe9] mx-[2px]" />;
}
