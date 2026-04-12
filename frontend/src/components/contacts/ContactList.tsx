import type { Contact, SidebarFilter } from './types';
import { ContactListItem } from './ContactListItem';

interface Props {
  contacts: Contact[];
  total: number;
  page: number;
  perPage: number;
  search: string;
  loading: boolean;
  filter: SidebarFilter;
  selectedId: number | null;
  checkedIds: Set<number>;
  showCheckboxes: boolean;
  onSelect: (c: Contact) => void;
  onDoubleClick: (c: Contact) => void;
  onToggleFavorite: (c: Contact) => void;
  onCheck: (c: Contact, e: React.MouseEvent) => void;
  onContextMenu: (c: Contact, e: React.MouseEvent) => void;
  onSearchChange: (q: string) => void;
  onPageChange: (p: number) => void;
}

export function ContactList({
  contacts, total, page, perPage, search, loading, filter,
  selectedId, checkedIds, showCheckboxes,
  onSelect, onDoubleClick, onToggleFavorite, onCheck, onContextMenu,
  onSearchChange, onPageChange,
}: Props) {
  const totalPages = Math.ceil(total / perPage);

  // Agrupar alfabéticamente
  const grouped = contacts.reduce<Record<string, Contact[]>>((acc, c) => {
    const firstChar = (c.display_name || '?')[0].toUpperCase();
    const letter = /[A-Z]/.test(firstChar) ? firstChar : '#';
    if (!acc[letter]) acc[letter] = [];
    acc[letter].push(c);
    return acc;
  }, {});
  const sortedLetters = Object.keys(grouped).sort((a, b) => {
    if (a === '#') return 1;
    if (b === '#') return -1;
    return a.localeCompare(b);
  });

  const filterLabel = filter === 'favorites' ? 'Favoritos'
    : filter === 'deleted' ? 'Eliminados'
    : filter.startsWith('category:') ? 'Categoría'
    : filter.startsWith('list:') ? 'Lista'
    : 'Contactos';

  return (
    <div style={{
      width: 320, minWidth: 280, borderRight: '1px solid #edebe9',
      display: 'flex', flexDirection: 'column', background: '#fff',
    }}>
      {/* Header */}
      <div style={{ padding: '16px 16px 12px', borderBottom: '1px solid #edebe9' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: '#323130' }}>
            {filterLabel}
          </h2>
          <span style={{ fontSize: 12, color: '#a19f9d' }}>
            {total} contacto{total !== 1 ? 's' : ''}
          </span>
        </div>
        {/* Buscador */}
        <div style={{ position: 'relative' }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
            stroke="#a19f9d" strokeWidth="2" style={{
              position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
            }}>
            <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            value={search}
            onChange={e => onSearchChange(e.target.value)}
            placeholder="Buscar contactos..."
            style={{
              width: '100%', padding: '8px 12px 8px 34px', fontSize: 13,
              border: '1px solid #edebe9', borderRadius: 4, outline: 'none',
              fontFamily: "'Segoe UI', Calibri, sans-serif", boxSizing: 'border-box',
            }}
            onFocus={e => { e.target.style.borderColor = '#0078d4'; }}
            onBlur={e => { e.target.style.borderColor = '#edebe9'; }}
          />
        </div>
      </div>

      {/* Lista */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {loading && contacts.length === 0 ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
            <div className="contacts-spinner" style={{
              width: 24, height: 24, border: '2px solid #edebe9',
              borderTopColor: '#0078d4', borderRadius: '50%',
            }} />
          </div>
        ) : contacts.length === 0 ? (
          <div style={{
            flex: 1, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', padding: 40, color: '#a19f9d',
          }}>
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#d2d0ce" strokeWidth="1">
              <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" /><circle cx="12" cy="7" r="4" />
            </svg>
            <p style={{ fontSize: 14, marginTop: 12, color: '#605e5c' }}>
              {search ? 'No se encontraron contactos' : 'No hay contactos'}
            </p>
          </div>
        ) : (
          sortedLetters.map(letter => (
            <div key={letter}>
              <div style={{
                padding: '8px 16px', fontSize: 12, fontWeight: 600,
                color: '#0078d4', background: '#faf9f8',
                borderBottom: '1px solid #edebe9',
                position: 'sticky', top: 0, zIndex: 1,
              }}>
                {letter}
              </div>
              {grouped[letter].map(contact => (
                <ContactListItem
                  key={contact.id}
                  contact={contact}
                  isSelected={selectedId === contact.id}
                  checked={checkedIds.has(contact.id)}
                  showCheckboxes={showCheckboxes}
                  onClick={() => onSelect(contact)}
                  onDoubleClick={() => onDoubleClick(contact)}
                  onToggleFavorite={e => { e.stopPropagation(); onToggleFavorite(contact); }}
                  onCheck={e => onCheck(contact, e)}
                  onContextMenu={e => onContextMenu(contact, e)}
                />
              ))}
            </div>
          ))
        )}
      </div>

      {/* Paginación */}
      {totalPages > 1 && (
        <div style={{
          display: 'flex', justifyContent: 'center', alignItems: 'center',
          gap: 8, padding: '10px 16px', borderTop: '1px solid #edebe9', background: '#faf9f8',
        }}>
          <button disabled={page <= 1} onClick={() => onPageChange(page - 1)}
            style={{
              padding: '4px 12px', fontSize: 12, border: '1px solid #edebe9',
              borderRadius: 4, background: '#fff',
              cursor: page <= 1 ? 'default' : 'pointer',
              color: page <= 1 ? '#c8c6c4' : '#323130',
            }}>Anterior</button>
          <span style={{ fontSize: 12, color: '#605e5c' }}>{page} / {totalPages}</span>
          <button disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}
            style={{
              padding: '4px 12px', fontSize: 12, border: '1px solid #edebe9',
              borderRadius: 4, background: '#fff',
              cursor: page >= totalPages ? 'default' : 'pointer',
              color: page >= totalPages ? '#c8c6c4' : '#323130',
            }}>Siguiente</button>
        </div>
      )}

      <style>{'.contacts-spinner { animation: contacts-spin 0.8s linear infinite; } @keyframes contacts-spin { to { transform: rotate(360deg); } }'}</style>
    </div>
  );
}
