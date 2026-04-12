import { useState, useEffect, useCallback } from 'react';
import { api } from '../../api/client';
import type { ContactCategory, ContactList, SidebarFilter } from './types';

interface Props {
  activeFilter: SidebarFilter;
  onFilterChange: (f: SidebarFilter) => void;
  deletedCount: number;
  /* FIX: Callback para exponer la función refresh al componente padre.
     Antes usaba un botón oculto con getElementById (DOM hack) que era frágil
     y rompía el contrato React de comunicación padre-hijo via props. */
  onRefreshRef?: (fn: () => void) => void;
  onManageCategories: () => void;
  onManageList: (listId: number, listName: string) => void;
}

export function ContactsSidebar({ activeFilter, onFilterChange, deletedCount, onRefreshRef, onManageCategories, onManageList }: Props) {
  const [categories, setCategories] = useState<ContactCategory[]>([]);
  const [lists, setLists] = useState<ContactList[]>([]);
  const [showLists, setShowLists] = useState(true);
  const [showCats, setShowCats] = useState(true);

  const refresh = useCallback(() => {
    api.get<ContactCategory[]>('/contacts/categories').then(setCategories).catch(() => {});
    api.get<ContactList[]>('/contacts/lists').then(setLists).catch(() => {});
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  /* FIX: Exponer refresh al padre via callback prop en vez de getElementById.
     Se ejecuta una vez al montar, pasando la referencia de la función refresh. */
  useEffect(() => {
    onRefreshRef?.(refresh);
  }, [onRefreshRef, refresh]);

  const Item = ({ label, icon, filter, badge }: {
    label: string; icon: React.ReactNode; filter: SidebarFilter; badge?: number;
  }) => {
    const active = activeFilter === filter;
    return (
      <div
        onClick={() => onFilterChange(filter)}
        style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '8px 16px', cursor: 'pointer',
          background: active ? '#e1dfdd' : 'transparent',
          borderLeft: active ? '3px solid #0078d4' : '3px solid transparent',
          color: active ? '#0078d4' : '#323130',
          fontSize: 13, fontFamily: "'Segoe UI', Calibri, sans-serif",
          transition: 'background 0.1s',
        }}
        onMouseEnter={e => { if (!active) (e.currentTarget as HTMLElement).style.background = '#f3f2f1'; }}
        onMouseLeave={e => { if (!active) (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
      >
        <span style={{ display: 'flex', width: 16, justifyContent: 'center' }}>{icon}</span>
        <span style={{ flex: 1 }}>{label}</span>
        {badge !== undefined && badge > 0 && (
          <span style={{ fontSize: 11, color: '#a19f9d' }}>{badge}</span>
        )}
      </div>
    );
  };

  const Chevron = ({ open }: { open: boolean }) => (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      style={{ transform: open ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.15s' }}>
      <polyline points="9,18 15,12 9,6" />
    </svg>
  );

  const GearIcon = () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" />
    </svg>
  );

  const starIcon = <svg width="16" height="16" viewBox="0 0 24 24" fill="#ffb900" stroke="#ffb900" strokeWidth="1"><polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26" /></svg>;
  const peopleIcon = <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 00-3-3.87" /><path d="M16 3.13a4 4 0 010 7.75" /></svg>;
  const groupIcon = <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>;
  const trashIcon = <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><polyline points="3,6 5,6 21,6" /><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" /></svg>;

  return (
    <div style={{
      width: 228, minWidth: 228, background: '#faf9f8',
      borderRight: '1px solid #edebe9', display: 'flex', flexDirection: 'column',
      fontFamily: "'Segoe UI', Calibri, sans-serif", flexShrink: 0,
      overflowY: 'auto',
    }}>
      <div style={{ padding: '16px 16px 8px' }}>
        <h2 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: '#323130' }}>Contactos</h2>
      </div>

      <Item label="Favoritos" icon={starIcon} filter="favorites" />
      <Item label="Todos los contactos" icon={peopleIcon} filter="all" />

      {/* Listas */}
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '8px 16px', fontSize: 13, fontWeight: 600,
          color: '#605e5c', marginTop: 8,
        }}
      >
        <div
          onClick={() => setShowLists(!showLists)}
          style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', flex: 1 }}
        >
          <Chevron open={showLists} />
          <span style={{ display: 'flex', width: 16, justifyContent: 'center' }}>{groupIcon}</span>
          Listas
        </div>
      </div>
      {showLists && lists.map(l => {
        const active = activeFilter === `list:${l.id}`;
        return (
          <div
            key={l.id}
            onClick={() => onFilterChange(`list:${l.id}`)}
            className="sidebar-list-item"
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '6px 16px 6px 44px', cursor: 'pointer', fontSize: 12,
              background: active ? '#e1dfdd' : 'transparent',
              borderLeft: active ? '3px solid #0078d4' : '3px solid transparent',
              color: active ? '#0078d4' : '#323130',
              position: 'relative',
            }}
            onMouseEnter={e => {
              if (!active) (e.currentTarget as HTMLElement).style.background = '#f3f2f1';
              const gear = e.currentTarget.querySelector('.list-gear-btn') as HTMLElement;
              if (gear) gear.style.opacity = '1';
            }}
            onMouseLeave={e => {
              if (!active) (e.currentTarget as HTMLElement).style.background = 'transparent';
              const gear = e.currentTarget.querySelector('.list-gear-btn') as HTMLElement;
              if (gear) gear.style.opacity = '0';
            }}
          >
            <span style={{ flex: 1 }}>{l.name}</span>
            <span style={{ fontSize: 11, color: '#a19f9d', marginRight: 4 }}>{l.member_count}</span>
            <span
              className="list-gear-btn"
              title="Gestionar lista"
              onClick={e => { e.stopPropagation(); onManageList(l.id, l.name); }}
              style={{
                opacity: 0, transition: 'opacity 0.15s',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: 20, height: 20, borderRadius: 4, cursor: 'pointer',
                color: '#605e5c', flexShrink: 0,
              }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = '#e1dfdd'; }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
            >
              <GearIcon />
            </span>
          </div>
        );
      })}

      <Item label="Eliminados" icon={trashIcon} filter="deleted" badge={deletedCount} />

      {/* Separador */}
      <div style={{ borderTop: '1px solid #edebe9', margin: '8px 16px' }} />

      {/* Categorías */}
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '8px 16px', fontSize: 13, fontWeight: 600,
          color: '#605e5c',
        }}
      >
        <div
          onClick={() => setShowCats(!showCats)}
          style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', flex: 1 }}
        >
          <Chevron open={showCats} />
          Categorías
        </div>
        <span
          title="Gestionar categorías"
          onClick={e => { e.stopPropagation(); onManageCategories(); }}
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            width: 22, height: 22, borderRadius: 4, cursor: 'pointer',
            color: '#605e5c', flexShrink: 0,
          }}
          onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = '#e1dfdd'; }}
          onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
        >
          <GearIcon />
        </span>
      </div>
      {showCats && categories.map(cat => (
        <div
          key={cat.id}
          onClick={() => onFilterChange(`category:${cat.id}`)}
          style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '6px 16px 6px 36px', cursor: 'pointer', fontSize: 12,
            background: activeFilter === `category:${cat.id}` ? '#e1dfdd' : 'transparent',
            borderLeft: activeFilter === `category:${cat.id}` ? '3px solid #0078d4' : '3px solid transparent',
            color: activeFilter === `category:${cat.id}` ? '#0078d4' : '#323130',
          }}
          onMouseEnter={e => { if (activeFilter !== `category:${cat.id}`) (e.currentTarget as HTMLElement).style.background = '#f3f2f1'; }}
          onMouseLeave={e => { if (activeFilter !== `category:${cat.id}`) (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
        >
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: cat.color, flexShrink: 0 }} />
          <span style={{ flex: 1 }}>{cat.name}</span>
          <span style={{ fontSize: 11, color: '#a19f9d' }}>{cat.contact_count}</span>
        </div>
      ))}
    </div>
  );
}
