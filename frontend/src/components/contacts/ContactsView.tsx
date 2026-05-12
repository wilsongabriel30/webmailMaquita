import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../../api/client';
import { useMailStore } from '../../store/mailStore';
import { useNavigate } from 'react-router-dom';
import type { Contact, ContactsResponse, ContactCategory, ContactList, SidebarFilter } from './types';
import { ContactsSidebar } from './ContactsSidebar';
import { ContactsRibbon } from './ContactsRibbon';
import { ContactList as ContactListPanel } from './ContactList';
import { ContactDetail } from './ContactDetail';
import { ContactForm, contactToFormData, emptyFormData } from './ContactForm';
import type { ContactFormData } from './ContactForm';
import { DeleteDialog } from './DeleteDialog';
import { NewListModal } from './NewListModal';
import { ImportExportModal } from './ImportExportModal';
import { CategoryManager } from './CategoryManager';
import { ListManager } from './ListManager';
import { ContextMenu } from './ContextMenu';
import { DuplicatesModal } from './DuplicatesModal';
import { RemindersModal } from './RemindersModal';
import { CustomFieldsManager as CustomFieldsManagerModal } from './CustomFieldsManager';
import { DirectoryPanel } from './DirectoryPanel';
import { MultiImportModal } from './MultiImportModal';
import { CardDAVSync } from './CardDAVSync';

export function ContactsView() {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [deletedCount, setDeletedCount] = useState(0);
  const perPage = 50;
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<SidebarFilter>('all');
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<Contact | null>(null);
  const [editing, setEditing] = useState(false);
  const [showNewContact, setShowNewContact] = useState(false);
  const [showNewList, setShowNewList] = useState(false);
  const [showDelete, setShowDelete] = useState(false);
  const [showImportExport, setShowImportExport] = useState<'import' | 'export' | null>(null);
  const [saving, setSaving] = useState(false);
  const [showEmptyTrashConfirm, setShowEmptyTrashConfirm] = useState(false);
  const searchTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const fetchIdRef = useRef(0);

  /* Multi-select */
  const [checkedIds, setCheckedIds] = useState<Set<number>>(new Set());
  const lastCheckedRef = useRef<number | null>(null);

  /* Context menu */
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; contact: Contact } | null>(null);
  const [sidebarCategories, setSidebarCategories] = useState<ContactCategory[]>([]);
  const [sidebarLists, setSidebarLists] = useState<ContactList[]>([]);

  /* Category Manager modal */
  const [showCategoryManager, setShowCategoryManager] = useState<'manage' | 'assign' | null>(null);

  /* Duplicates modal */
  const [showDuplicates, setShowDuplicates] = useState(false);
  /* Reminders modal */
  const [showReminders, setShowReminders] = useState(false);
  /* Custom Fields manager */
  const [showCustomFields, setShowCustomFields] = useState(false);

  /* Phase 4: Enterprise modals */
  const [showDirectory, setShowDirectory] = useState(false);
  const [showMultiImport, setShowMultiImport] = useState(false);
  const [showCardDAV, setShowCardDAV] = useState(false);

  /* List Manager modal */
  const [managingList, setManagingList] = useState<{ id: number; name: string } | null>(null);

  /* Sidebar refresh ref */
  const sidebarRefreshRef = useRef<(() => void) | null>(null);

  const openCompose = useMailStore(s => s.openCompose);
  const navigate = useNavigate();

  /* ── Fetch contacts ── */
  const fetchContacts = useCallback(async (p: number, q: string, f: SidebarFilter) => {
    const myId = ++fetchIdRef.current;
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(p), per_page: String(perPage), filter: f });
      if (q) params.set('search', q);
      const res = await api.get<ContactsResponse>('/contacts?' + params.toString());
      if (myId === fetchIdRef.current) {
        setContacts(res.contacts);
        setTotal(res.total);
        setPage(res.page);
      }
    } catch { /* silently */ } finally {
      if (myId === fetchIdRef.current) setLoading(false);
    }
  }, []);

  const fetchDeletedCount = useCallback(async () => {
    try {
      const res = await api.get<ContactsResponse>('/contacts?filter=deleted&per_page=1');
      setDeletedCount(res.total);
    } catch { /* silently */ }
  }, []);

  /* Fetch sidebar data for context menu */
  const fetchSidebarData = useCallback(async () => {
    try {
      const [cats, lsts] = await Promise.all([
        api.get<ContactCategory[]>('/contacts/categories'),
        api.get<ContactList[]>('/contacts/lists'),
      ]);
      setSidebarCategories(cats);
      setSidebarLists(lsts);
    } catch { /* silently */ }
  }, []);

  useEffect(() => {
    fetchContacts(1, '', filter);
    fetchDeletedCount();
    fetchSidebarData();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* Search debounce */
  const handleSearch = (val: string) => {
    setSearch(val);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      setSelected(null);
      setCheckedIds(new Set());
      fetchContacts(1, val, filter);
    }, 300);
  };

  /* Filter change */
  const handleFilterChange = (f: SidebarFilter) => {
    setFilter(f);
    setSearch('');
    setSelected(null);
    setEditing(false);
    setShowNewContact(false);
    setCheckedIds(new Set());
    fetchContacts(1, '', f);
  };

  /* Refresh helper */
  const refresh = () => {
    fetchContacts(page, search, filter);
    fetchDeletedCount();
    fetchSidebarData();
    sidebarRefreshRef.current?.();
  };

  /* ── CRUD handlers ── */
  const handleCreate = async (data: ContactFormData) => {
    setSaving(true);
    try {
      await api.post('/contacts', data);
      setShowNewContact(false);
      setEditing(false);
      refresh();
    } finally { setSaving(false); }
  };

  const handleUpdate = async (data: ContactFormData) => {
    if (!selected) return;
    setSaving(true);
    try {
      await api.put('/contacts/' + selected.id, data);
      setEditing(false);
      const params = new URLSearchParams({ page: String(page), per_page: String(perPage), filter });
      if (search) params.set('search', search);
      const res = await api.get<ContactsResponse>('/contacts?' + params.toString());
      setContacts(res.contacts);
      setTotal(res.total);
      const updated = res.contacts.find(c => c.id === selected.id);
      setSelected(updated || null);
      fetchDeletedCount();
      fetchSidebarData();
      sidebarRefreshRef.current?.();
    } catch { /* silently */ } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!selected) return;
    try {
      if (filter === 'deleted') {
        await api.del('/contacts/' + selected.id + '/permanent');
      } else {
        await api.del('/contacts/' + selected.id);
      }
      setShowDelete(false);
      setSelected(null);
      setCheckedIds(prev => { const n = new Set(prev); n.delete(selected.id); return n; });
      refresh();
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Error al eliminar';
      alert(msg);
    }
  };

  const handleEmptyTrash = () => setShowEmptyTrashConfirm(true);
  const handleEmptyTrashConfirmed = async () => {
    setShowEmptyTrashConfirm(false);
    try {
      await api.del('/contacts/trash');
      setSelected(null);
      setCheckedIds(new Set());
      refresh();
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Error al vaciar papelera';
      alert(msg);
    }
  };

  const handleRestore = async () => {
    if (!selected) return;
    try {
      await api.post('/contacts/' + selected.id + '/restore', {});
      setSelected(null);
      refresh();
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Error al restaurar';
      alert(msg);
    }
  };

  const handleToggleFavorite = async (contact?: Contact) => {
    const c = contact || selected;
    if (!c) return;
    try {
      await api.put('/contacts/' + c.id + '/favorite', { favorite: !c.is_favorite });
      if (selected?.id === c.id) {
        setSelected({ ...selected, is_favorite: !c.is_favorite });
      }
      refresh();
    } catch { /* silently */ }
  };

  const handleSendEmail = (contact?: Contact) => {
    const c = contact || selected;
    if (!c) return;
    const emailAddr = c.display_name
      ? `${c.display_name} <${c.email}>`
      : c.email;
    openCompose('new', { to: [emailAddr], subject: '', text_body: '', html_body: '' });
    navigate('/');
  };

  const handleCreateList = async (name: string, description: string) => {
    setSaving(true);
    try {
      await api.post('/contacts/lists', { name, description });
      setShowNewList(false);
      refresh();
    } finally { setSaving(false); }
  };

  /* ── Multi-select handlers ── */
  const handleCheck = (contact: Contact, e: React.MouseEvent) => {
    e.stopPropagation();
    setCheckedIds(prev => {
      const next = new Set(prev);
      if (e.shiftKey && lastCheckedRef.current !== null) {
        /* Shift-click: select range */
        const ids = contacts.map(c => c.id);
        const from = ids.indexOf(lastCheckedRef.current);
        const to = ids.indexOf(contact.id);
        const [start, end] = from < to ? [from, to] : [to, from];
        for (let i = start; i <= end; i++) next.add(ids[i]);
      } else {
        if (next.has(contact.id)) next.delete(contact.id);
        else next.add(contact.id);
      }
      lastCheckedRef.current = contact.id;
      return next;
    });
  };

  const handleBulkDelete = async () => {
    if (checkedIds.size === 0) return;
    try {
      await api.post('/contacts/bulk/delete', { contact_ids: Array.from(checkedIds) });
      setCheckedIds(new Set());
      setSelected(null);
      refresh();
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Error en eliminación masiva';
      alert(msg);
    }
  };

  const handleBulkFavorite = async (fav: boolean) => {
    if (checkedIds.size === 0) return;
    try {
      await api.post('/contacts/bulk/favorite', { contact_ids: Array.from(checkedIds), favorite: fav });
      refresh();
    } catch { /* silently */ }
  };

  /* ── Context menu handlers ── */
  const handleContextMenu = (contact: Contact, e: React.MouseEvent) => {
    e.preventDefault();
    setSelected(contact);
    setContextMenu({ x: e.clientX, y: e.clientY, contact });
  };

  const handleAssignCategory = async (categoryId: number, assign: boolean) => {
    if (!contextMenu) return;
    const contact = contextMenu.contact;
    const currentIds = contact.categories.map(c => c.id);
    const newIds = assign
      ? [...currentIds, categoryId]
      : currentIds.filter(id => id !== categoryId);
    try {
      await api.put(`/contacts/${contact.id}/categories`, { category_ids: newIds });
      refresh();
    } catch { /* silently */ }
    setContextMenu(null);
  };

  const handleAddToList = async (listId: number) => {
    if (!contextMenu) return;
    try {
      await api.post(`/contacts/lists/${listId}/members`, { contact_ids: [contextMenu.contact.id] });
      refresh();
    } catch { /* silently */ }
    setContextMenu(null);
  };

  /* ── Category assign from ribbon (single or multi) ── */
  const handleCategorize = () => {
    if (selected || checkedIds.size > 0) {
      setShowCategoryManager('assign');
    }
  };

  const handleCategorySaved = () => {
    refresh();
  };

  return (
    <div style={{
      display: 'flex', height: '100%', background: '#f3f2f1',
      fontFamily: "'Segoe UI', Calibri, sans-serif",
    }}>
      {/* Sidebar */}
      <ContactsSidebar
        activeFilter={filter}
        onFilterChange={handleFilterChange}
        deletedCount={deletedCount}
        onRefreshRef={(fn) => { sidebarRefreshRef.current = fn; }}
        onManageCategories={() => setShowCategoryManager('manage')}
        onManageList={(id, name) => setManagingList({ id, name })}
      />

      {/* Main content */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Ribbon */}
        <ContactsRibbon
          filter={filter}
          hasSelection={!!selected || checkedIds.size > 0}
          isFavorite={selected?.is_favorite || false}
          selectionCount={checkedIds.size > 0 ? checkedIds.size : (selected ? 1 : 0)}
          onNewContact={() => { setSelected(null); setShowNewContact(true); setEditing(true); setCheckedIds(new Set()); }}
          onNewList={() => setShowNewList(true)}
          onEdit={() => { if (selected) setEditing(true); }}
          onDelete={() => {
            if (checkedIds.size > 1) { handleBulkDelete(); }
            else if (selected) { setShowDelete(true); }
          }}
          onRestore={handleRestore}
          onToggleFavorite={() => handleToggleFavorite()}
          onImport={() => setShowImportExport('import')}
          onExport={() => setShowImportExport('export')}
          onEmptyTrash={handleEmptyTrash}
          onCategorize={handleCategorize}
          onManageCategories={() => setShowCategoryManager('manage')}
          onBulkDelete={handleBulkDelete}
          onBulkFavorite={handleBulkFavorite}
          onShowDuplicates={() => setShowDuplicates(true)}
          onShowReminders={() => setShowReminders(true)}
          onShowCustomFields={() => setShowCustomFields(true)}
          onShowDirectory={() => setShowDirectory(true)}
          onShowMultiImport={() => setShowMultiImport(true)}
          onShowCardDAV={() => setShowCardDAV(true)}
        />

        {/* Content area */}
        <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          {/* Contact list */}
          <ContactListPanel
            contacts={contacts}
            total={total}
            page={page}
            perPage={perPage}
            search={search}
            loading={loading}
            filter={filter}
            selectedId={selected?.id || null}
            checkedIds={checkedIds}
            showCheckboxes={checkedIds.size > 0}
            onSelect={(c) => { setSelected(c); setEditing(false); setShowNewContact(false); }}
            onDoubleClick={(c) => { setSelected(c); setEditing(true); setShowNewContact(false); }}
            onToggleFavorite={(c) => handleToggleFavorite(c)}
            onCheck={handleCheck}
            onContextMenu={handleContextMenu}
            onSearchChange={handleSearch}
            onPageChange={(p) => fetchContacts(p, search, filter)}
          />

          {/* Detail / Form */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: '#fff', overflow: 'hidden' }}>
            {showNewContact && editing ? (
              <ContactForm
                key="new-contact"
                initial={emptyFormData()}
                onSave={handleCreate}
                onCancel={() => { setShowNewContact(false); setEditing(false); }}
                saving={saving}
                title="Nuevo contacto"
              />
            ) : selected && editing ? (
              <ContactForm
                key={`edit-${selected.id}`}
                initial={contactToFormData(selected)}
                onSave={handleUpdate}
                onCancel={() => setEditing(false)}
                saving={saving}
                title="Editar contacto"
              />
            ) : selected ? (
              <ContactDetail
                contact={selected}
                onSendEmail={() => handleSendEmail()}
                onEdit={() => setEditing(true)}
                onDelete={() => setShowDelete(true)}
                onRestore={filter === 'deleted' ? handleRestore : undefined}
                onNavigateToContact={(cid) => {
                  const found = contacts.find(c => c.id === cid);
                  if (found) setSelected(found);
                }}
              />
            ) : (
              <div style={{
                flex: 1, display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center', color: '#a19f9d',
              }}>
                <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#d2d0ce" strokeWidth="1">
                  <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" /><circle cx="12" cy="7" r="4" />
                </svg>
                <p style={{ fontSize: 14, marginTop: 12 }}>Selecciona un contacto para ver sus detalles</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Modals ── */}

      {showDelete && selected && (
        <DeleteDialog
          name={selected.display_name || selected.email}
          permanent={filter === 'deleted'}
          onConfirm={handleDelete}
          onCancel={() => setShowDelete(false)}
        />
      )}

      {showEmptyTrashConfirm && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 9999,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          backgroundColor: 'rgba(0,0,0,0.4)',
        }}>
          <div style={{
            background: '#fff', borderRadius: 8, padding: 24, width: 400,
            boxShadow: '0 8px 32px rgba(0,0,0,0.25)',
            fontFamily: "'Segoe UI', Calibri, sans-serif",
          }}>
            <h3 style={{ margin: 0, fontSize: 18, fontWeight: 600, color: '#323130' }}>
              Vaciar papelera
            </h3>
            <p style={{ fontSize: 14, color: '#605e5c', margin: '12px 0 24px' }}>
              ¿Eliminar permanentemente <strong>{deletedCount}</strong> contacto{deletedCount !== 1 ? 's' : ''} de la papelera? Esta acción no se puede deshacer.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button onClick={() => setShowEmptyTrashConfirm(false)} style={{
                padding: '8px 20px', fontSize: 13, fontWeight: 600,
                border: '1px solid #8a8886', borderRadius: 4, background: '#fff',
                color: '#323130', cursor: 'pointer',
              }}>Cancelar</button>
              <button onClick={handleEmptyTrashConfirmed} style={{
                padding: '8px 20px', fontSize: 13, fontWeight: 600,
                border: 'none', borderRadius: 4, background: '#d13438',
                color: '#fff', cursor: 'pointer',
              }}>Vaciar papelera</button>
            </div>
          </div>
        </div>
      )}

      {showNewList && (
        <NewListModal
          onSave={handleCreateList}
          onClose={() => setShowNewList(false)}
          saving={saving}
        />
      )}

      {showImportExport && (
        <ImportExportModal
          mode={showImportExport}
          onClose={() => setShowImportExport(null)}
          onImportDone={refresh}
        />
      )}

      {/* Category Manager — manage or assign mode */}
      {showCategoryManager && (
        <CategoryManager
          mode={showCategoryManager}
          contactId={selected?.id}
          currentCategoryIds={selected?.categories?.map(c => c.id) || []}
          onClose={() => setShowCategoryManager(null)}
          onSaved={handleCategorySaved}
        />
      )}

      {/* List Manager */}
      {managingList && (
        <ListManager
          listId={managingList.id}
          listName={managingList.name}
          onClose={() => setManagingList(null)}
          onSaved={() => { refresh(); }}
          onDeleted={() => { setManagingList(null); handleFilterChange('all'); }}
        />
      )}

      {/* Duplicates Modal */}
      {showDuplicates && (
        <DuplicatesModal
          isOpen={showDuplicates}
          onClose={() => setShowDuplicates(false)}
          onMerged={refresh}
        />
      )}

      {/* Reminders Modal */}
      {showReminders && (
        <RemindersModal
          isOpen={showReminders}
          onClose={() => setShowReminders(false)}
          onNavigateToContact={(cid) => {
            setShowReminders(false);
            const found = contacts.find(c => c.id === cid);
            if (found) setSelected(found);
          }}
        />
      )}

      {/* Custom Fields Manager */}
      {showCustomFields && (
        <CustomFieldsManagerModal
          isOpen={showCustomFields}
          onClose={() => setShowCustomFields(false)}
        />
      )}

      {/* Directory Panel */}
      {showDirectory && (
        <DirectoryPanel
          isOpen={showDirectory}
          onClose={() => setShowDirectory(false)}
        />
      )}

      {/* Multi Import Modal */}
      {showMultiImport && (
        <MultiImportModal
          isOpen={showMultiImport}
          onClose={() => setShowMultiImport(false)}
          onImportComplete={refresh}
        />
      )}

      {/* CardDAV Sync */}
      {showCardDAV && (
        <CardDAVSync
          isOpen={showCardDAV}
          onClose={() => setShowCardDAV(false)}
        />
      )}

      {/* Context Menu */}
      {contextMenu && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          contact={contextMenu.contact}
          isTrash={filter === 'deleted'}
          categories={sidebarCategories}
          lists={sidebarLists}
          onClose={() => setContextMenu(null)}
          onSendEmail={() => { handleSendEmail(contextMenu.contact); setContextMenu(null); }}
          onEdit={() => { setSelected(contextMenu.contact); setEditing(true); setContextMenu(null); }}
          onDelete={() => { setSelected(contextMenu.contact); setShowDelete(true); setContextMenu(null); }}
          onRestore={() => { setSelected(contextMenu.contact); handleRestore(); setContextMenu(null); }}
          onToggleFavorite={() => { handleToggleFavorite(contextMenu.contact); setContextMenu(null); }}
          onAssignCategory={handleAssignCategory}
          onAddToList={handleAddToList}
        />
      )}
    </div>
  );
}
