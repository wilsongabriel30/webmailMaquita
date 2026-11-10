/**
 * Botones grande y mediano de la cinta de redacción (extraídos de Ribbon.tsx el 09/11/2026 para
 * que otros módulos de la cinta, como MenuInsertar, los reutilicen sin importar el Ribbon entero).
 */
import type { ReactNode } from 'react';

export function LargeBtn({ icon, label, onClick, disabled, active, hasDropdown }: {
  icon: ReactNode; label: string; onClick: () => void; disabled?: boolean; active?: boolean; hasDropdown?: boolean;
}) {
  const lines = label.split('\n');
  return (
    <button onMouseDown={(e) => e.preventDefault()} onClick={onClick} disabled={disabled} title={lines.join(' ')}
      className={`flex flex-col items-center justify-center min-w-[44px] px-[4px] rounded-[3px] transition-colors h-[62px] ${
        active ? 'bg-[#c7e0f4]' : disabled ? 'opacity-40 cursor-not-allowed' : 'hover:bg-[#e1dfdd]'
      }`}>
      <div className="h-[24px] flex items-center justify-center">{icon}</div>
      <div className="flex items-center gap-[1px] mt-[1px]">
        <span className="text-[12px] leading-[14px] text-[#323130] text-center whitespace-pre-line">{lines.join('\n')}</span>
        {hasDropdown && <svg className="w-[8px] h-[8px] text-[#605e5c] shrink-0 ml-[1px]" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" /></svg>}
      </div>
    </button>
  );
}

export function MedBtn({ icon, label, onClick, hasDropdown }: { icon: ReactNode; label: string; onClick: () => void; hasDropdown?: boolean; }) {
  return (
    <button onMouseDown={(e) => e.preventDefault()} onClick={onClick} title={label}
      className="flex items-center gap-[3px] h-[24px] px-[4px] rounded-[2px] hover:bg-[#e1dfdd] transition-colors">
      {icon}
      <span className="text-[12px] text-[#323130] whitespace-nowrap">{label}</span>
      {hasDropdown && <svg className="w-[7px] h-[7px] text-[#605e5c]" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" /></svg>}
    </button>
  );
}
