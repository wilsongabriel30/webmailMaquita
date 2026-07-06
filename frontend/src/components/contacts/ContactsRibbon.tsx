import { useState } from 'react';
import type { SidebarFilter } from './types';

interface Props {
  filter: SidebarFilter;
  hasSelection: boolean;
  isFavorite: boolean;
  selectionCount: number;
  onNewContact: () => void;
  onNewList: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onRestore: () => void;
  onToggleFavorite: () => void;
  onImport: () => void;
  onImportHistory: () => void;
  onExport: () => void;
  onEmptyTrash: () => void;
  onCategorize: () => void;
  onManageCategories: () => void;
  onShowDuplicates: () => void;
  onShowReminders: () => void;
  onShowCustomFields: () => void;
  onBulkDelete: () => void;
  onBulkFavorite: (fav: boolean) => void;
  onShowDirectory: () => void;
  onShowMultiImport: () => void;
  onShowCardDAV: () => void;
}

export function ContactsRibbon({
  filter, hasSelection, isFavorite, selectionCount,
  onNewContact, onNewList, onEdit, onDelete, onRestore,
  onToggleFavorite, onImport, onImportHistory, onExport, onEmptyTrash,
  onCategorize, onManageCategories, onBulkDelete, onBulkFavorite,
  onShowDuplicates, onShowReminders, onShowCustomFields,
  onShowDirectory, onShowMultiImport, onShowCardDAV,
}: Props) {
  const [showNewMenu, setShowNewMenu] = useState(false);
  const [showManageMenu, setShowManageMenu] = useState(false);
  const isTrash = filter === 'deleted';
  const isMulti = selectionCount > 1;

  const RibbonBtn = ({ icon, label, onClick, disabled, danger }: {
    icon: React.ReactNode; label: string; onClick: () => void;
    disabled?: boolean; danger?: boolean;
  }) => (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
        padding: '6px 12px', border: 'none', borderRadius: 4,
        background: 'transparent', cursor: disabled ? 'default' : 'pointer',
        opacity: disabled ? 0.4 : 1,
        color: danger ? '#d13438' : '#323130',
        fontSize: 11, fontFamily: "'Segoe UI', Calibri, sans-serif",
        minWidth: 56,
        transition: 'background 0.1s',
      }}
      onMouseEnter={e => { if (!disabled) (e.currentTarget as HTMLElement).style.background = '#f3f2f1'; }}
      onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
    >
      <span style={{ display: 'flex', width: 20, height: 20, alignItems: 'center', justifyContent: 'center' }}>
        {icon}
      </span>
      <span>{label}</span>
    </button>
  );

  const Divider = () => (
    <div style={{ width: 1, height: 40, background: '#edebe9', margin: '0 4px', flexShrink: 0 }} />
  );

  const plusIcon = <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></svg>;
  const editIcon = <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>;
  const trashIcon = <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><polyline points="3,6 5,6 21,6" /><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" /></svg>;
  const restoreIcon = <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><polyline points="1,4 1,10 7,10" /><path d="M3.51 15a9 9 0 102.13-9.36L1 10" /></svg>;
  const starIcon = <svg width="18" height="18" viewBox="0 0 24 24" fill={isFavorite ? '#ffb900' : 'none'} stroke={isFavorite ? '#ffb900' : 'currentColor'} strokeWidth="1.5"><polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26" /></svg>;
  const gearIcon = <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" /></svg>;
  const emptyTrashIcon = <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><polyline points="3,6 5,6 21,6" /><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" /><line x1="10" y1="11" x2="10" y2="17" /><line x1="14" y1="11" x2="14" y2="17" /></svg>;
  const tagIcon = <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M20.59 13.41l-7.17 7.17a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82z" /><line x1="7" y1="7" x2="7.01" y2="7" /></svg>;

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 2,
      padding: '6px 16px', borderBottom: '1px solid #edebe9',
      background: '#faf9f8', flexShrink: 0,
      fontFamily: "'Segoe UI', Calibri, sans-serif",
      flexWrap: 'wrap',
    }}>
      {/* Nuevo */}
      <div style={{ position: 'relative' }}>
        <RibbonBtn icon={plusIcon} label="Nuevo ▾" onClick={() => setShowNewMenu(!showNewMenu)} />
        {showNewMenu && (
          <div
            style={{
              position: 'absolute', top: '100%', left: 0, zIndex: 100,
              background: '#fff', border: '1px solid #edebe9', borderRadius: 4,
              boxShadow: '0 4px 12px rgba(0,0,0,0.15)', minWidth: 160,
            }}
            onMouseLeave={() => setShowNewMenu(false)}
          >
            <div onClick={() => { onNewContact(); setShowNewMenu(false); }}
              style={{ padding: '8px 16px', fontSize: 13, cursor: 'pointer' }}
              onMouseEnter={e => (e.currentTarget.style.background = '#f3f2f1')}
              onMouseLeave={e => (e.currentTarget.style.background = '#fff')}
            >Nuevo contacto</div>
            <div onClick={() => { onNewList(); setShowNewMenu(false); }}
              style={{ padding: '8px 16px', fontSize: 13, cursor: 'pointer' }}
              onMouseEnter={e => (e.currentTarget.style.background = '#f3f2f1')}
              onMouseLeave={e => (e.currentTarget.style.background = '#fff')}
            >Nueva lista</div>
            <div onClick={() => { onImportHistory(); setShowNewMenu(false); }}
              style={{ padding: '8px 16px', fontSize: 13, cursor: 'pointer', borderTop: '1px solid #edebe9' }}
              onMouseEnter={e => (e.currentTarget.style.background = '#f3f2f1')}
              onMouseLeave={e => (e.currentTarget.style.background = '#fff')}
              title="Crea contactos con las direcciones de tus correos recibidos y enviados"
            >📥 Importar del historial</div>
          </div>
        )}
      </div>

      <Divider />
      <RibbonBtn icon={editIcon} label="Editar" onClick={onEdit} disabled={!hasSelection || isTrash || isMulti} />

      <Divider />
      {isTrash ? (
        <>
          <RibbonBtn icon={restoreIcon} label="Restaurar" onClick={onRestore} disabled={!hasSelection} />
          {isMulti ? (
            <RibbonBtn icon={trashIcon} label={`Eliminar (${selectionCount})`} onClick={onBulkDelete} danger />
          ) : (
            <RibbonBtn icon={trashIcon} label="Eliminar" onClick={onDelete} disabled={!hasSelection} danger />
          )}
        </>
      ) : isMulti ? (
        <RibbonBtn icon={trashIcon} label={`Eliminar (${selectionCount})`} onClick={onBulkDelete} danger />
      ) : (
        <RibbonBtn icon={trashIcon} label="Eliminar" onClick={onDelete} disabled={!hasSelection} danger />
      )}

      <Divider />
      {isMulti && !isTrash ? (
        <RibbonBtn
          icon={starIcon}
          label={`Favorito (${selectionCount})`}
          onClick={() => onBulkFavorite(!isFavorite)}
        />
      ) : (
        <RibbonBtn
          icon={starIcon}
          label={isFavorite ? 'Quitar ★' : 'Favorito'}
          onClick={onToggleFavorite}
          disabled={!hasSelection || isTrash}
        />
      )}

      {/* Categorizar — disponible en seleccion simple o multi, no en papelera */}
      {!isTrash && (
        <>
          <Divider />
          <RibbonBtn
            icon={tagIcon}
            label={isMulti ? `Categorizar (${selectionCount})` : 'Categorizar'}
            onClick={onCategorize}
            disabled={!hasSelection}
          />
        </>
      )}

      {/* Vaciar papelera — solo visible en modo papelera */}
      {isTrash && (
        <>
          <Divider />
          <RibbonBtn icon={emptyTrashIcon} label="Vaciar" onClick={onEmptyTrash} danger />
        </>
      )}

      <Divider />
      <div style={{ position: 'relative' }}>
        <RibbonBtn icon={gearIcon} label="Administrar ▾" onClick={() => setShowManageMenu(!showManageMenu)} />
        {showManageMenu && (
          <div
            style={{
              position: 'absolute', top: '100%', left: 0, zIndex: 100,
              background: '#fff', border: '1px solid #edebe9', borderRadius: 4,
              boxShadow: '0 4px 12px rgba(0,0,0,0.15)', minWidth: 150,
            }}
            onMouseLeave={() => setShowManageMenu(false)}
          >
            <div onClick={() => { onImport(); setShowManageMenu(false); }}
              style={{ padding: '8px 16px', fontSize: 13, cursor: 'pointer' }}
              onMouseEnter={e => (e.currentTarget.style.background = '#f3f2f1')}
              onMouseLeave={e => (e.currentTarget.style.background = '#fff')}
            >Importar CSV</div>
            <div onClick={() => { onExport(); setShowManageMenu(false); }}
              style={{ padding: '8px 16px', fontSize: 13, cursor: 'pointer' }}
              onMouseEnter={e => (e.currentTarget.style.background = '#f3f2f1')}
              onMouseLeave={e => (e.currentTarget.style.background = '#fff')}
            >Exportar</div>
            <div style={{ height: 1, background: '#edebe9', margin: '4px 0' }} />
            <div onClick={() => { onManageCategories(); setShowManageMenu(false); }}
              style={{ padding: '8px 16px', fontSize: 13, cursor: 'pointer' }}
              onMouseEnter={e => (e.currentTarget.style.background = '#f3f2f1')}
              onMouseLeave={e => (e.currentTarget.style.background = '#fff')}
            >Categorías</div>
            <div onClick={() => { onShowCustomFields(); setShowManageMenu(false); }}
              style={{ padding: '8px 16px', fontSize: 13, cursor: 'pointer' }}
              onMouseEnter={e => (e.currentTarget.style.background = '#f3f2f1')}
              onMouseLeave={e => (e.currentTarget.style.background = '#fff')}
            >Campos personalizados</div>
            <div onClick={() => { onShowDuplicates(); setShowManageMenu(false); }}
              style={{ padding: '8px 16px', fontSize: 13, cursor: 'pointer' }}
              onMouseEnter={e => (e.currentTarget.style.background = '#f3f2f1')}
              onMouseLeave={e => (e.currentTarget.style.background = '#fff')}
            >Buscar duplicados</div>
            <div onClick={() => { onShowReminders(); setShowManageMenu(false); }}
              style={{ padding: '8px 16px', fontSize: 13, cursor: 'pointer' }}
              onMouseEnter={e => (e.currentTarget.style.background = '#f3f2f1')}
              onMouseLeave={e => (e.currentTarget.style.background = '#fff')}
            >Recordatorios</div>
            <div style={{ height: 1, background: '#edebe9', margin: '4px 0' }} />
            <div onClick={() => { onShowDirectory(); setShowManageMenu(false); }}
              style={{ padding: '8px 16px', fontSize: 13, cursor: 'pointer' }}
              onMouseEnter={e => (e.currentTarget.style.background = '#f3f2f1')}
              onMouseLeave={e => (e.currentTarget.style.background = '#fff')}
            >Directorio institucional</div>
            <div onClick={() => { onShowMultiImport(); setShowManageMenu(false); }}
              style={{ padding: '8px 16px', fontSize: 13, cursor: 'pointer' }}
              onMouseEnter={e => (e.currentTarget.style.background = '#f3f2f1')}
              onMouseLeave={e => (e.currentTarget.style.background = '#fff')}
            >Importar multi-servicio</div>
            <div onClick={() => { onShowCardDAV(); setShowManageMenu(false); }}
              style={{ padding: '8px 16px', fontSize: 13, cursor: 'pointer' }}
              onMouseEnter={e => (e.currentTarget.style.background = '#f3f2f1')}
              onMouseLeave={e => (e.currentTarget.style.background = '#fff')}
            >Sincronización CardDAV</div>
          </div>
        )}
      </div>

      {selectionCount > 1 && (
        <span style={{ marginLeft: 'auto', fontSize: 12, color: '#605e5c' }}>
          {selectionCount} seleccionados
        </span>
      )}
    </div>
  );
}
