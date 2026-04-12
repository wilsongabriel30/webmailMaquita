import { useState } from 'react';
import { Avatar } from './Avatar';
import type { Contact } from './types';

interface Props {
  contact: Contact;
  isSelected: boolean;
  checked: boolean;
  showCheckboxes: boolean;
  onClick: () => void;
  onDoubleClick: () => void;
  onToggleFavorite: (e: React.MouseEvent) => void;
  onCheck: (e: React.MouseEvent) => void;
  onContextMenu: (e: React.MouseEvent) => void;
}

export function ContactListItem({
  contact, isSelected, checked, showCheckboxes,
  onClick, onDoubleClick, onToggleFavorite, onCheck, onContextMenu,
}: Props) {
  const [hovered, setHovered] = useState(false);

  const showCheckbox = showCheckboxes || hovered;

  return (
    <div
      onClick={onClick}
      onDoubleClick={onDoubleClick}
      onContextMenu={onContextMenu}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '10px 16px', cursor: 'pointer',
        background: isSelected ? '#e1dfdd' : hovered ? '#f3f2f1' : '#fff',
        borderBottom: '1px solid #f3f2f1',
        transition: 'background 0.1s',
        fontFamily: "'Segoe UI', sans-serif",
      }}
    >
      {/* Avatar o checkbox */}
      <div
        style={{
          width: 36, height: 36, flexShrink: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          position: 'relative',
        }}
      >
        {showCheckbox ? (
          <div
            onClick={(e) => { e.stopPropagation(); onCheck(e); }}
            style={{
              width: 18, height: 18, borderRadius: 3,
              border: checked ? 'none' : '1.5px solid #605e5c',
              background: checked ? '#0078d4' : '#fff',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', transition: 'background 0.1s, border 0.1s',
            }}
          >
            {checked && (
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M2.5 6L5 8.5L9.5 3.5" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
          </div>
        ) : (
          <Avatar name={contact.display_name} size={36} />
        )}
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{
            fontSize: 14, fontWeight: 600, color: '#323130',
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            {contact.display_name || '(Sin nombre)'}
          </span>
          {contact.categories?.length > 0 && contact.categories.map(cat => (
            <div key={cat.id} title={cat.name}
              style={{ width: 6, height: 6, borderRadius: '50%', background: cat.color, flexShrink: 0 }} />
          ))}
        </div>
        <div style={{
          fontSize: 12, color: '#605e5c',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        }}>
          {contact.email}
          {contact.job_title && contact.company && (
            <span style={{ color: '#a19f9d' }}> · {contact.job_title}, {contact.company}</span>
          )}
        </div>
      </div>

      {/* Estrella favorito */}
      <div
        onClick={(e) => { e.stopPropagation(); onToggleFavorite(e); }}
        style={{
          cursor: 'pointer', flexShrink: 0, padding: 4,
          opacity: contact.is_favorite || hovered ? 1 : 0,
          transition: 'opacity 0.15s',
        }}
        title={contact.is_favorite ? 'Quitar de favoritos' : 'Agregar a favoritos'}
      >
        <svg width="16" height="16" viewBox="0 0 24 24"
          fill={contact.is_favorite ? '#ffb900' : 'none'}
          stroke={contact.is_favorite ? '#ffb900' : '#a19f9d'}
          strokeWidth="1.5"
        >
          <polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26" />
        </svg>
      </div>
    </div>
  );
}
