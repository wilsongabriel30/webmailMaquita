import { useEffect, useRef, useState } from 'react';

export interface MenuItem {
  label: string;
  icon?: string;
  onClick: () => void;
  danger?: boolean;
  divider?: boolean;
  disabled?: boolean;
  children?: MenuItem[];
}

interface Props {
  x: number;
  y: number;
  items: MenuItem[];
  onClose: () => void;
}

export function ContextMenu({ x, y, items, onClose }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [openSubmenu, setOpenSubmenu] = useState<number | null>(null);

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
        const hasChildren = !!item.children?.length;
        return (
          <div
            key={i}
            className="relative"
            onMouseEnter={() => setOpenSubmenu(hasChildren ? i : null)}
            onMouseLeave={() => setOpenSubmenu((current) => (current === i ? null : current))}
          >
            <button
              onClick={() => {
                if (hasChildren) {
                  setOpenSubmenu((current) => (current === i ? null : i));
                  return;
                }
                item.onClick();
                onClose();
              }}
              disabled={item.disabled}
              className={`w-full flex items-center gap-2.5 px-3 py-[6px] text-[13px] transition-colors text-left ${
                item.disabled ? 'text-[#c8c6c4] cursor-default' :
                item.danger ? 'text-[#a4262c] hover:bg-[#fde7e9]' :
                'text-[#323130] hover:bg-[#f3f2f1]'
              }`}
            >
              {item.icon && (
                <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={item.icon} />
                </svg>
              )}
              <span className="flex-1">{item.label}</span>
              {hasChildren && (
                <svg className="w-3.5 h-3.5 shrink-0 text-[#605e5c]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 6l6 6-6 6" />
                </svg>
              )}
            </button>
            {hasChildren && openSubmenu === i && (
              <div className="absolute left-full top-[-4px] ml-1 min-w-[220px] bg-white rounded-md shadow-xl border border-[#e1dfdd] py-1 z-[10000]">
                {item.children!.map((child, childIndex) => {
                  if (child.divider) return <div key={childIndex} className="h-px bg-[#edebe9] my-1" />;
                  return (
                    <button
                      key={childIndex}
                      onClick={() => { child.onClick(); onClose(); }}
                      disabled={child.disabled}
                      className={`w-full flex items-center gap-2.5 px-3 py-[6px] text-[13px] transition-colors text-left ${
                        child.disabled ? 'text-[#c8c6c4] cursor-default' :
                        child.danger ? 'text-[#a4262c] hover:bg-[#fde7e9]' :
                        'text-[#323130] hover:bg-[#f3f2f1]'
                      }`}
                    >
                      {child.icon && (
                        <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={child.icon} />
                        </svg>
                      )}
                      {child.label}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
