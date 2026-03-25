import { useEffect, useRef } from 'react';

interface MenuItem {
  label: string;
  icon?: string;
  onClick: () => void;
  danger?: boolean;
  divider?: boolean;
  disabled?: boolean;
}

interface Props {
  x: number;
  y: number;
  items: MenuItem[];
  onClose: () => void;
}

export function ContextMenu({ x, y, items, onClose }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('mousedown', handle);
    document.addEventListener('keydown', esc);
    return () => { document.removeEventListener('mousedown', handle); document.removeEventListener('keydown', esc); };
  }, [onClose]);

  // Adjust position to stay in viewport
  const style: React.CSSProperties = { position: 'fixed', left: x, top: y, zIndex: 9999 };

  return (
    <div ref={ref} style={style}
      className="min-w-[200px] bg-white rounded-md shadow-xl border border-[#e1dfdd] py-1 animate-in fade-in duration-100">
      {items.map((item, i) => {
        if (item.divider) return <div key={i} className="h-px bg-[#edebe9] my-1" />;
        return (
          <button key={i} onClick={() => { item.onClick(); onClose(); }} disabled={item.disabled}
            className={`w-full flex items-center gap-2.5 px-3 py-[6px] text-[13px] transition-colors text-left ${
              item.disabled ? 'text-[#c8c6c4] cursor-default' :
              item.danger ? 'text-[#a4262c] hover:bg-[#fde7e9]' :
              'text-[#323130] hover:bg-[#f3f2f1]'
            }`}>
            {item.icon && (
              <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={item.icon} />
              </svg>
            )}
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
