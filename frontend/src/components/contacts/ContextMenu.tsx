import { useEffect, useRef, useState, useCallback } from 'react';
import type { Contact, ContactCategory, ContactList } from './types';

interface Props {
  x: number;
  y: number;
  contact: Contact;
  isTrash: boolean;
  categories: ContactCategory[];
  lists: ContactList[];
  onClose: () => void;
  onSendEmail: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onRestore: () => void;
  onToggleFavorite: () => void;
  onAssignCategory: (categoryId: number, assign: boolean) => void;
  onAddToList: (listId: number) => void;
}

const MENU_WIDTH = 220;
const SUBMENU_WIDTH = 200;

const IconMail = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ flexShrink: 0 }}>
    <rect x="1" y="3" width="14" height="10" rx="1.5" stroke="#605e5c" strokeWidth="1.2" fill="none" />
    <path d="M1.5 4L8 9L14.5 4" stroke="#605e5c" strokeWidth="1.2" fill="none" />
  </svg>
);

const IconEdit = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ flexShrink: 0 }}>
    <path d="M11.5 2.5L13.5 4.5L5 13H3V11L11.5 2.5Z" stroke="#605e5c" strokeWidth="1.2" fill="none" />
  </svg>
);

const IconStar = ({ filled }: { filled: boolean }) => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ flexShrink: 0 }}>
    <path
      d="M8 1.5L9.8 5.8L14.5 6.2L11 9.3L12 14L8 11.5L4 14L5 9.3L1.5 6.2L6.2 5.8Z"
      stroke="#605e5c"
      strokeWidth="1.2"
      fill={filled ? '#ffc107' : 'none'}
    />
  </svg>
);

const IconTrash = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ flexShrink: 0 }}>
    <path d="M3 4H13L12 14H4L3 4Z" stroke="#a80000" strokeWidth="1.2" fill="none" />
    <path d="M2 4H14" stroke="#a80000" strokeWidth="1.2" />
    <path d="M6 2H10" stroke="#a80000" strokeWidth="1.2" />
  </svg>
);

const IconRestore = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ flexShrink: 0 }}>
    <path d="M2 8C2 4.7 4.7 2 8 2C11.3 2 14 4.7 14 8C14 11.3 11.3 14 8 14C5.8 14 3.9 12.8 2.9 11" stroke="#605e5c" strokeWidth="1.2" fill="none" />
    <path d="M2 5V8H5" stroke="#605e5c" strokeWidth="1.2" fill="none" />
  </svg>
);

const IconCategory = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ flexShrink: 0 }}>
    <rect x="2" y="2" width="5" height="5" rx="1" stroke="#605e5c" strokeWidth="1.2" fill="none" />
    <rect x="9" y="2" width="5" height="5" rx="1" stroke="#605e5c" strokeWidth="1.2" fill="none" />
    <rect x="2" y="9" width="5" height="5" rx="1" stroke="#605e5c" strokeWidth="1.2" fill="none" />
    <rect x="9" y="9" width="5" height="5" rx="1" stroke="#605e5c" strokeWidth="1.2" fill="none" />
  </svg>
);

const IconList = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ flexShrink: 0 }}>
    <path d="M5 4H14M5 8H14M5 12H14" stroke="#605e5c" strokeWidth="1.2" />
    <circle cx="2.5" cy="4" r="1" fill="#605e5c" />
    <circle cx="2.5" cy="8" r="1" fill="#605e5c" />
    <circle cx="2.5" cy="12" r="1" fill="#605e5c" />
  </svg>
);

function ContextMenu({
  x,
  y,
  contact,
  isTrash,
  categories,
  lists,
  onClose,
  onSendEmail,
  onEdit,
  onDelete,
  onRestore,
  onToggleFavorite,
  onAssignCategory,
  onAddToList,
}: Props) {
  const menuRef = useRef<HTMLDivElement>(null);
  const [hoveredItem, setHoveredItem] = useState<string | null>(null);
  const [position, setPosition] = useState({ left: x, top: y });
  const [submenuSide, setSubmenuSide] = useState<'right' | 'left'>('right');
  const leaveTimerRef = useRef<number | null>(null);

  // Adjust position so menu stays on screen
  useEffect(() => {
    const el = menuRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    let left = x;
    let top = y;
    let side: 'right' | 'left' = 'right';

    if (left + rect.width > window.innerWidth) {
      left = window.innerWidth - rect.width - 8;
    }
    if (top + rect.height > window.innerHeight) {
      top = window.innerHeight - rect.height - 8;
    }
    if (left < 0) left = 8;
    if (top < 0) top = 8;

    if (left + MENU_WIDTH + SUBMENU_WIDTH > window.innerWidth) {
      side = 'left';
    }

    setPosition({ left, top });
    setSubmenuSide(side);
  }, [x, y]);

  // Close on Escape
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [onClose]);

  // Close on click outside
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [onClose]);

  const clearLeaveTimer = useCallback(() => {
    if (leaveTimerRef.current !== null) {
      window.clearTimeout(leaveTimerRef.current);
      leaveTimerRef.current = null;
    }
  }, []);

  const handleMouseLeave = useCallback(() => {
    leaveTimerRef.current = window.setTimeout(() => {
      setHoveredItem(null);
    }, 150);
  }, []);

  const handleMouseEnterMenu = useCallback(() => {
    clearLeaveTimer();
  }, [clearLeaveTimer]);

  useEffect(() => {
    return () => clearLeaveTimer();
  }, [clearLeaveTimer]);

  const itemStyle: React.CSSProperties = {
    padding: '8px 12px',
    fontSize: 13,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    whiteSpace: 'nowrap',
    position: 'relative',
    backgroundColor: 'transparent',
    border: 'none',
    width: '100%',
    textAlign: 'left',
    color: '#323130',
    fontFamily: 'inherit',
  };

  const hoverBg = '#f3f2f1';

  const separatorStyle: React.CSSProperties = {
    height: 1,
    backgroundColor: '#edebe9',
    margin: '4px 0',
  };

  const menuStyle: React.CSSProperties = {
    position: 'fixed',
    left: position.left,
    top: position.top,
    backgroundColor: '#ffffff',
    border: '1px solid #edebe9',
    borderRadius: 4,
    boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
    zIndex: 10000,
    minWidth: MENU_WIDTH,
    padding: '4px 0',
    fontFamily: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
  };

  const submenuStyle: React.CSSProperties = {
    position: 'absolute',
    top: 0,
    ...(submenuSide === 'right' ? { left: '100%' } : { right: '100%' }),
    backgroundColor: '#ffffff',
    border: '1px solid #edebe9',
    borderRadius: 4,
    boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
    zIndex: 10001,
    minWidth: SUBMENU_WIDTH,
    padding: '4px 0',
    maxHeight: 300,
    overflowY: 'auto',
  };

  const MenuItem: React.FC<{
    icon?: React.ReactNode;
    label: string;
    onClick?: () => void;
    red?: boolean;
    hasSubmenu?: boolean;
    submenuId?: string;
  }> = ({ icon, label, onClick, red, hasSubmenu, submenuId }) => {
    const [hovered, setHovered] = useState(false);

    return (
      <div
        style={{
          ...itemStyle,
          backgroundColor: hovered || hoveredItem === submenuId ? hoverBg : 'transparent',
          color: red ? '#a80000' : '#323130',
        }}
        onMouseEnter={() => {
          setHovered(true);
          if (submenuId) {
            clearLeaveTimer();
            setHoveredItem(submenuId);
          } else {
            setHoveredItem(null);
          }
        }}
        onMouseLeave={() => {
          setHovered(false);
          if (submenuId) handleMouseLeave();
        }}
        onClick={(e) => {
          if (hasSubmenu) {
            e.stopPropagation();
            return;
          }
          onClick?.();
          onClose();
        }}
      >
        {icon && <span style={{ display: 'flex', alignItems: 'center' }}>{icon}</span>}
        <span style={{ flex: 1 }}>{label}</span>
        {hasSubmenu && <span style={{ marginLeft: 8, fontSize: 11, color: '#605e5c' }}>&#9656;</span>}

        {/* Category submenu */}
        {submenuId === 'categories' && hoveredItem === 'categories' && (
          <div
            style={submenuStyle}
            onMouseEnter={() => {
              clearLeaveTimer();
              setHoveredItem('categories');
            }}
            onMouseLeave={handleMouseLeave}
          >
            {categories.length === 0 && (
              <div style={{ ...itemStyle, color: '#a19f9d', cursor: 'default' }}>Sin categorías</div>
            )}
            {categories.map((cat) => {
              const isAssigned = contact.categories?.some((c: any) =>
                typeof c === 'number' ? c === cat.id : c?.id === cat.id
              );
              return (
                <CategoryItem
                  key={cat.id}
                  category={cat}
                  checked={!!isAssigned}
                  onClick={() => {
                    onAssignCategory(cat.id, !isAssigned);
                  }}
                />
              );
            })}
          </div>
        )}

        {/* Lists submenu */}
        {submenuId === 'lists' && hoveredItem === 'lists' && (
          <div
            style={submenuStyle}
            onMouseEnter={() => {
              clearLeaveTimer();
              setHoveredItem('lists');
            }}
            onMouseLeave={handleMouseLeave}
          >
            {lists.length === 0 && (
              <div style={{ ...itemStyle, color: '#a19f9d', cursor: 'default' }}>Sin listas</div>
            )}
            {lists.map((list) => (
              <ListItem
                key={list.id}
                list={list}
                onClick={() => {
                  onAddToList(list.id);
                  onClose();
                }}
              />
            ))}
          </div>
        )}
      </div>
    );
  };

  const CategoryItem: React.FC<{
    category: ContactCategory;
    checked: boolean;
    onClick: () => void;
  }> = ({ category, checked, onClick }) => {
    const [hovered, setHovered] = useState(false);
    return (
      <div
        style={{
          ...itemStyle,
          backgroundColor: hovered ? hoverBg : 'transparent',
        }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        onClick={(e) => {
          e.stopPropagation();
          onClick();
        }}
      >
        <span
          style={{
            width: 14,
            height: 14,
            border: '1.5px solid #605e5c',
            borderRadius: 2,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            backgroundColor: checked ? '#0078d4' : 'transparent',
            borderColor: checked ? '#0078d4' : '#605e5c',
          }}
        >
          {checked && (
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
              <path d="M2 5L4.5 7.5L8 3" stroke="#fff" strokeWidth="1.5" />
            </svg>
          )}
        </span>
        <span
          style={{
            width: 10,
            height: 10,
            borderRadius: '50%',
            backgroundColor: (category as any).color || '#0078d4',
            flexShrink: 0,
          }}
        />
        <span>{(category as any).name || (category as any).nombre || ''}</span>
      </div>
    );
  };

  const ListItem: React.FC<{
    list: ContactList;
    onClick: () => void;
  }> = ({ list, onClick }) => {
    const [hovered, setHovered] = useState(false);
    return (
      <div
        style={{
          ...itemStyle,
          backgroundColor: hovered ? hoverBg : 'transparent',
        }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        onClick={onClick}
      >
        <span>{(list as any).name || (list as any).nombre || ''}</span>
      </div>
    );
  };

  return (
    <div
      ref={menuRef}
      style={menuStyle}
      onMouseEnter={handleMouseEnterMenu}
      onMouseLeave={handleMouseLeave}
    >
      {isTrash ? (
        <>
          <MenuItem icon={<IconRestore />} label="Restaurar" onClick={onRestore} />
          <MenuItem icon={<IconTrash />} label="Eliminar permanentemente" onClick={onDelete} red />
        </>
      ) : (
        <>
          <MenuItem icon={<IconMail />} label="Enviar correo" onClick={onSendEmail} />
          <div style={separatorStyle} />
          <MenuItem icon={<IconEdit />} label="Editar" onClick={onEdit} />
          <MenuItem
            icon={<IconStar filled={!!contact.is_favorite} />}
            label={contact.is_favorite ? 'Quitar de favoritos' : 'Agregar a favoritos'}
            onClick={onToggleFavorite}
          />
          <div style={separatorStyle} />
          <MenuItem
            icon={<IconCategory />}
            label="Categorizar"
            hasSubmenu
            submenuId="categories"
          />
          <MenuItem
            icon={<IconList />}
            label="Agregar a lista"
            hasSubmenu
            submenuId="lists"
          />
          <div style={separatorStyle} />
          <MenuItem icon={<IconTrash />} label="Eliminar" onClick={onDelete} red />
        </>
      )}
    </div>
  );
}

export { ContextMenu };
