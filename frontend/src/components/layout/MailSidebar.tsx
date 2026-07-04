// ===========================================================================
// MailSidebar — Sidebar de carpetas del webmail Maquita
// Funcionalidades: árbol de carpetas, drag & drop (mensajes y carpetas),
// menú contextual completo, renombrar con doble click, confirmaciones,
// modal de mover carpeta, estadísticas.
// ===========================================================================
import { useEffect, useState, useRef } from 'react';
import { useMailStore } from '../../store/mailStore';
import { api } from '../../api/client';
import { showToast } from '../common/Toast';
import { ContextMenu } from '../common/ContextMenu';
import type { Folder } from '../../types';
import { getFolderDisplayName } from '../../folders';

interface MailStats {
  inbox_total: number;
  inbox_unread: number;
  sent_total: number;
  sent_today: number;
  sent_week: number;
  sent_month: number;
  drafts: number;
  trash: number;
  storage_used_mb: number;
  top_senders: { email: string; name: string; count: number }[];
}

const icons: Record<string, string> = {
  inbox: 'M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4',
  sent: 'M12 19l9 2-9-18-9 18 9-2zm0 0v-8',
  drafts: 'M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z',
  trash: 'M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16',
  junk: 'M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636',
  archive: 'M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4',
  folder: 'M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z',
};
const systemFolders = new Set(['INBOX', 'Sent', 'Drafts', 'Trash', 'Junk', 'Archive']);
const favorites = ['INBOX', 'Sent', 'Drafts'];

export function MailSidebar() {
  const [hidden, setHidden] = useState(false);
  useEffect(() => {
    const handler = () => setHidden(prev => !prev);
    window.addEventListener("toggle-sidebar", handler);
    return () => window.removeEventListener("toggle-sidebar", handler);
  }, []);

  const folders = useMailStore(s => s.folders);
  const currentFolder = useMailStore(s => s.currentFolder);
  const setFolders = useMailStore(s => s.setFolders);
  const setCurrentFolder = useMailStore(s => s.setCurrentFolder);
  const setLoadingFolders = useMailStore(s => s.setLoadingFolders);
  const openCompose = useMailStore(s => s.openCompose);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [createParent, setCreateParent] = useState('');
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [renaming, setRenaming] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [ctxMenu, setCtxMenu] = useState<{ x: number; y: number; folder: Folder } | null>(null);
  const [dropTarget, setDropTarget] = useState<string | null>(null);
  const [draggedFolder, setDraggedFolder] = useState<string | null>(null);
  const [stats, setStats] = useState<MailStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [moveModal, setMoveModal] = useState<{ folder: Folder } | null>(null);
  const [confirmModal, setConfirmModal] = useState<{ title: string; message: string; onConfirm: () => void; danger?: boolean } | null>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; folder: Folder } | null>(null);
  const sidebarRef = useRef<HTMLDivElement>(null);

  // Limpiar tooltip al hacer scroll o al salir del sidebar
  useEffect(() => {
    const el = sidebarRef.current;
    if (!el) return;
    const hide = () => { clearTimeout(tooltipTimer.current); setTooltip(null); };
    el.addEventListener('scroll', hide, { passive: true });
    el.addEventListener('mouseleave', hide);
    return () => { el.removeEventListener('scroll', hide); el.removeEventListener('mouseleave', hide); };
  }, []);
  const tooltipTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  // Stats polling
  useEffect(() => {
    let mounted = true;
    const fetchStats = () => {
      setStatsLoading(true);
      api.get<MailStats>('/mail/stats')
        .then(r => { if (mounted) setStats(r); })
        .catch(() => {})
        .finally(() => { if (mounted) setStatsLoading(false); });
    };
    fetchStats();
    const interval = setInterval(fetchStats, 5 * 60 * 1000);
    return () => { mounted = false; clearInterval(interval); };
  }, []);

  const fetchFolders = () => {
    setLoadingFolders(true);
    api.get<{ folders: Folder[] }>('/mail/folders').then(r => setFolders(r.folders)).catch(console.error);
  };

  useEffect(() => { fetchFolders(); }, []);

  // Refrescar contadores de carpetas y stats cuando cambian los mensajes
  // (marcar leidos, eliminar, mover, sync offline). Antes solo se cargaban
  // al montar y el badge de no leidos quedaba congelado hasta recargar.
  useEffect(() => {
    let t: ReturnType<typeof setTimeout> | undefined;
    const h = () => {
      clearTimeout(t);
      t = setTimeout(() => {
        api.get<{ folders: Folder[] }>('/mail/folders').then(r => setFolders(r.folders)).catch(() => {});
        api.get<MailStats>('/mail/stats').then(r => setStats(r)).catch(() => {});
      }, 1200);
    };
    window.addEventListener('refresh-messages', h);
    return () => { clearTimeout(t); window.removeEventListener('refresh-messages', h); };
  }, []);

  // --- Folder operations ---
  const handleCreate = async () => {
    if (!newName.trim()) return;
    const fullName = createParent ? `${createParent}.${newName.trim()}` : newName.trim();
    try { await api.post('/mail/folders', { name: fullName }); showToast(`Carpeta "${newName.trim()}" creada`); } catch {}
    setNewName(''); setCreating(false); setCreateParent(''); fetchFolders();
  };

  const handleRename = async (oldName: string) => {
    // Comparar con el nombre hoja (display), no con el path completo IMAP
    if (!renameValue.trim() || renameValue.trim() === getFolderDisplayName(oldName)) { setRenaming(null); return; }
    // Preserve parent path, only rename the leaf
    const dotIdx = oldName.lastIndexOf('.');
    const newFull = dotIdx > 0 ? oldName.substring(0, dotIdx + 1) + renameValue.trim() : renameValue.trim();
    try {
      await api.put(`/mail/folders/${encodeURIComponent(oldName)}`, { new_name: newFull });
      showToast(`Carpeta renombrada a "${renameValue.trim()}"`);
    } catch (e: any) { showToast(e.message || 'Error al renombrar'); }
    setRenaming(null); fetchFolders();
  };

  const handleDelete = (name: string) => {
    if (systemFolders.has(name)) return;
    setConfirmModal({
      title: 'Eliminar carpeta',
      message: `¿Eliminar "${getFolderDisplayName(name)}" y todo su contenido? Esta acción no se puede deshacer.`,
      danger: true,
      onConfirm: async () => {
        try { await api.del(`/mail/folders/${encodeURIComponent(name)}`); showToast('Carpeta eliminada'); } catch {}
        fetchFolders();
      },
    });
  };

  const handleEmpty = (name: string) => {
    setConfirmModal({
      title: 'Vaciar carpeta',
      message: `¿Eliminar todos los mensajes de "${getFolderDisplayName(name)}"?`,
      danger: true,
      onConfirm: async () => {
        try {
          let total = 0;
          // Vaciar en tandas (el backend limita per_page a 300) hasta que no queden.
          for (let i = 0; i < 50; i++) {
            const res = await api.get<{ messages: { uid: number }[] }>(`/mail/messages/${encodeURIComponent(name)}?per_page=300`);
            const uids = (res.messages || []).map(m => m.uid);
            if (uids.length === 0) break;
            await api.post(`/mail/bulk-action/${encodeURIComponent(name)}`, { uids, action: 'delete', dest_folder: '' });
            total += uids.length;
            if (uids.length < 300) break;
          }
          showToast(total > 0 ? `${total} mensaje(s) eliminados` : 'La carpeta ya estaba vacía');
        } catch { showToast('Error al vaciar la carpeta'); }
        window.dispatchEvent(new CustomEvent('refresh-messages'));
        fetchFolders();
      },
    });
  };

  const handleMarkAllRead = async (name: string) => {
    try {
      const res = await api.get<{ messages: { uid: number; seen: boolean }[]; total: number }>(`/mail/messages/${encodeURIComponent(name)}?per_page=999`);
      const unread = res.messages.filter(m => !m.seen);
      if (unread.length > 0) {
        await api.post(`/mail/bulk-action/${encodeURIComponent(name)}`, { uids: unread.map(m => m.uid), action: 'mark_read', dest_folder: '' });
        showToast(`${unread.length} mensaje(s) marcados como leídos`);
        window.dispatchEvent(new CustomEvent('refresh-messages'));
        fetchFolders();
      } else {
        showToast('Todos los mensajes ya están leídos');
      }
    } catch { showToast('Error al marcar como leídos'); }
  };

  const handleMoveFolder = async (folderName: string, newParent: string) => {
    if (systemFolders.has(folderName)) { showToast('No se puede mover una carpeta del sistema'); return; }
    try {
      await api.post(`/mail/folders/${encodeURIComponent(folderName)}/move`, { new_parent: newParent });
      showToast(`Carpeta movida a ${newParent ? getFolderDisplayName(newParent) : 'raíz'}`);
      fetchFolders();
    } catch (e: any) { showToast(e.message || 'Error al mover carpeta'); }
    setMoveModal(null);
  };

  // --- Context menu items ---
  const getFolderCtxItems = (f: Folder) => {
    const isSystem = systemFolders.has(f.name);
    const folderList = folders.filter(fl => fl.name !== f.name && !fl.name.startsWith(f.name + '.'));
    return [
      // Acciones de contenido
      { label: 'Marcar todo como leído', icon: 'M3 19v-8.93a2 2 0 01.89-1.664l7-4.666a2 2 0 012.22 0l7 4.666A2 2 0 0121 10.07V19M3 19a2 2 0 002 2h14a2 2 0 002-2M3 19l6.75-4.5M21 19l-6.75-4.5M3 10l6.75 4.5M21 10l-6.75 4.5', onClick: () => handleMarkAllRead(f.name) },
      { label: '', icon: '', onClick: () => {}, divider: true },
      // Organización de carpetas
      { label: 'Crear subcarpeta', icon: 'M12 4v16m8-8H4', onClick: () => { setCreateParent(f.name); setCreating(true); setCtxMenu(null); } },
      ...(!isSystem ? [
        { label: 'Renombrar', icon: 'M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z',
          onClick: () => { setRenaming(f.name); setRenameValue(getFolderDisplayName(f.name)); } },
        {
          label: 'Mover a...',
          icon: 'M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4',
          onClick: () => {},
          children: [
            { label: '/ (raíz — nivel principal)', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3', onClick: () => handleMoveFolder(f.name, '') },
            ...folderList.map(target => ({
              label: getFolderDisplayName(target.name),
              icon: icons[target.type] || icons.folder,
              onClick: () => handleMoveFolder(f.name, target.name),
            })),
          ],
        },
      ] : []),
      { label: '', icon: '', onClick: () => {}, divider: true },
      // Acciones peligrosas
      { label: 'Vaciar carpeta', icon: icons.trash, onClick: () => handleEmpty(f.name) },
      ...(!isSystem ? [
        { label: 'Eliminar carpeta', icon: icons.trash, onClick: () => handleDelete(f.name), danger: true },
      ] : []),
    ];
  };

  // --- Build folder tree ---
  type FolderNode = { folder: Folder; children: FolderNode[] };

  const buildTree = (flatFolders: Folder[]): FolderNode[] => {
    const rootNodes: FolderNode[] = [];
    const nodeMap = new Map<string, FolderNode>();
    const sortOrder: Record<string, number> = { inbox: 0, drafts: 1, sent: 2, junk: 3, trash: 4, archive: 5 };
    const sorted = [...flatFolders].sort((a, b) => {
      const oa = sortOrder[a.type] ?? 6, ob = sortOrder[b.type] ?? 6;
      if (oa !== ob) return oa - ob;
      return a.name.localeCompare(b.name);
    });
    for (const f of sorted) {
      const node: FolderNode = { folder: f, children: [] };
      nodeMap.set(f.name, node);
      const dotIdx = f.name.lastIndexOf('.');
      const parentName = dotIdx > 0 ? f.name.substring(0, dotIdx) : null;
      if (parentName && nodeMap.has(parentName)) {
        nodeMap.get(parentName)!.children.push(node);
      } else {
        rootNodes.push(node);
      }
    }
    return rootNodes;
  };

  const fullTree = buildTree(folders);
  const favNodes = fullTree.filter(n => favorites.includes(n.folder.name));
  const otherNodes = fullTree.filter(n => !favorites.includes(n.folder.name));

  const [treeCollapsed, setTreeCollapsed] = useState<Record<string, boolean>>({});
  const toggleTreeNode = (name: string) => setTreeCollapsed(p => ({ ...p, [name]: !p[name] }));

  // --- Render individual folder ---
  const renderFolderButton = (f: Folder, depth: number, hasChildren: boolean) => {
    const active = currentFolder === f.name;
    const displayName = getFolderDisplayName(f.name);
    const isCollapsed = treeCollapsed[f.name];
    const isSystem = systemFolders.has(f.name);
    const isDragOver = dropTarget === f.name;
    const isBeingDragged = draggedFolder === f.name;

    if (renaming === f.name) {
      return (
        <div key={f.name} className="flex items-center gap-1 py-0.5" style={{ paddingLeft: `${8 + depth * 12}px` }}>
          <input value={renameValue} onChange={e => setRenameValue(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleRename(f.name); if (e.key === 'Escape') setRenaming(null); }}
            onBlur={() => handleRename(f.name)}
            autoFocus className="flex-1 text-[12px] px-1.5 py-0.5 border border-[#0078d4] rounded outline-none bg-white dark:bg-[#1e1e1e]" />
        </div>
      );
    }

    return (
      <button key={f.name}
        onClick={() => setCurrentFolder(f.name)}
        // Doble click para renombrar (solo no-sistema)
        onDoubleClick={e => {
          if (isSystem) return;
          e.preventDefault();
          setRenaming(f.name);
          setRenameValue(displayName);
        }}
        // Drag & drop de carpetas
        draggable={!isSystem}
        onDragStart={e => {
          if (isSystem) { e.preventDefault(); return; }
          setDraggedFolder(f.name);
          e.dataTransfer.setData('application/x-folder-name', f.name);
          e.dataTransfer.effectAllowed = 'move';
          // Ghost visual
          const ghost = document.createElement('div');
          ghost.textContent = displayName;
          ghost.style.cssText = 'padding:4px 12px;background:#0078d4;color:#fff;border-radius:4px;font-size:12px;position:fixed;top:-9999px;white-space:nowrap';
          document.body.appendChild(ghost);
          e.dataTransfer.setDragImage(ghost, 0, 0);
          setTimeout(() => document.body.removeChild(ghost), 0);
        }}
        onDragEnd={() => { setDraggedFolder(null); setDropTarget(null); }}
        onContextMenu={e => { e.preventDefault(); setCtxMenu({ x: e.clientX, y: e.clientY, folder: f }); }}
        // Drop zone: acepta mensajes y carpetas
        onDragOver={e => {
          e.preventDefault();
          e.stopPropagation();
          const hasMail = e.dataTransfer.types.includes('application/x-mail-uids');
          const hasFolder = e.dataTransfer.types.includes('application/x-folder-name');
          if (hasMail || hasFolder) {
            e.dataTransfer.dropEffect = 'move';
            setDropTarget(f.name);
          }
        }}
        onDragLeave={e => {
          e.stopPropagation();
          setDropTarget(null);
        }}
        onDrop={async e => {
          e.preventDefault();
          e.stopPropagation();
          setDropTarget(null);

          // Drop de mensajes
          const uidsJson = e.dataTransfer.getData('application/x-mail-uids');
          const srcFolder = e.dataTransfer.getData('application/x-mail-folder');
          if (uidsJson && srcFolder && srcFolder !== f.name) {
            const uids = JSON.parse(uidsJson);
            try {
              await api.post(`/mail/bulk-action/${encodeURIComponent(srcFolder)}`, { uids, action: 'move', dest_folder: f.name });
              showToast(`${uids.length} mensaje${uids.length > 1 ? 's' : ''} movido${uids.length > 1 ? 's' : ''} a ${displayName}`);
              useMailStore.getState().clearSelection();
              useMailStore.getState().setSelectedMessage(null);
              window.dispatchEvent(new CustomEvent('refresh-messages'));
              fetchFolders();
            } catch { showToast('Error al mover mensajes'); }
            return;
          }

          // Drop de carpeta
          const droppedFolder = e.dataTransfer.getData('application/x-folder-name');
          if (droppedFolder && droppedFolder !== f.name && !systemFolders.has(droppedFolder)) {
            if (f.name.startsWith(droppedFolder + '.')) {
              showToast('No se puede mover una carpeta dentro de sí misma');
              return;
            }
            handleMoveFolder(droppedFolder, f.name);
          }
        }}
        // Tooltip con ruta completa al hacer hover
        onMouseEnter={e => {
          clearTimeout(tooltipTimer.current);
          const rect = (e.target as HTMLElement).getBoundingClientRect();
          tooltipTimer.current = setTimeout(() => {
            setTooltip({ x: rect.right + 8, y: rect.top, folder: f });
            // Auto-ocultar tooltip después de 3s
            setTimeout(() => setTooltip(null), 3000);
          }, 600);
        }}
        onMouseLeave={() => { clearTimeout(tooltipTimer.current); setTooltip(null); }}
        className={`w-full flex items-center gap-1.5 px-2 py-[4px] rounded text-[13px] transition-all duration-150 ${
          isBeingDragged ? 'opacity-40' :
          isDragOver ? 'bg-[#deecf9] ring-2 ring-[#0078d4] scale-[1.02]' :
          active ? 'bg-[#e1dfdd] font-semibold text-[#323130]' :
          'text-[#323130] hover:bg-[#e1dfdd]'
        } ${!isSystem ? 'cursor-grab active:cursor-grabbing' : ''}`}
        style={{ paddingLeft: `${8 + depth * 14}px` }}>
        {hasChildren ? (
          <span className="w-[12px] h-[12px] flex items-center justify-center shrink-0 cursor-pointer"
            onClick={ev => { ev.stopPropagation(); toggleTreeNode(f.name); }}>
            <svg className={`w-[10px] h-[10px] text-[#605e5c] transition-transform ${isCollapsed ? '' : 'rotate-90'}`}
              fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
            </svg>
          </span>
        ) : <span className="w-[12px] shrink-0" />}
        <svg className={`w-[15px] h-[15px] shrink-0 transition-colors ${
          isDragOver ? 'text-[#0078d4]' : active ? 'text-[#0078d4]' : 'text-[#605e5c]'
        }`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={icons[f.type] || icons.folder} />
        </svg>
        <span className="truncate flex-1 text-left">{displayName}</span>
        {f.unseen > 0 && <span className="text-[11px] font-bold text-[#005a9e] tabular-nums">{f.unseen}</span>}
      </button>
    );
  };

  const renderNode = (node: FolderNode, depth: number): React.ReactNode => {
    const isCollapsed = treeCollapsed[node.folder.name];
    return (
      <div key={node.folder.name}>
        {renderFolderButton(node.folder, depth, node.children.length > 0)}
        {node.children.length > 0 && !isCollapsed && node.children.map(child => renderNode(child, depth + 1))}
      </div>
    );
  };

  // Flat list for move modal
  const allFolderNames = folders.map(f => f.name);

  return (
    <div className={`bg-[#faf9f8] border-r border-[#edebe9] flex flex-col shrink-0 text-[13px] transition-all duration-200 ease-in-out z-20 overflow-hidden ${hidden ? "w-0 border-r-0" : "w-[220px]"}`}>
      {/* Botón nuevo correo */}
      <div className="px-3 pt-2.5 pb-1.5">
        <button onClick={() => openCompose('new')}
          className="flex items-center gap-2 px-3 py-[5px] bg-white border border-[#8a8886] rounded shadow-sm hover:bg-[#f3f2f1] transition-colors text-[13px] text-[#323130] font-medium">
          <svg className="w-[15px] h-[15px] text-[#0078d4]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
          Nuevo correo
        </button>
      </div>

      {/* Árbol de carpetas */}
      <nav className="flex-1 overflow-y-auto px-1 text-[13px]"
        // Drop zone raíz: soltar carpeta aquí la mueve al nivel raíz
        onDragOver={e => {
          if (e.dataTransfer.types.includes('application/x-folder-name')) {
            e.preventDefault();
          }
        }}
        onDrop={e => {
          const droppedFolder = e.dataTransfer.getData('application/x-folder-name');
          if (droppedFolder && !systemFolders.has(droppedFolder) && droppedFolder.includes('.')) {
            e.preventDefault();
            handleMoveFolder(droppedFolder, '');
          }
        }}
      >
        <SectionHeader title="Favoritos" collapsed={collapsed.fav} onToggle={() => setCollapsed(p => ({...p, fav: !p.fav}))} />
        {!collapsed.fav && favNodes.map(node => renderNode(node, 0))}

        <SectionHeader title="Carpetas" collapsed={collapsed.all} onToggle={() => setCollapsed(p => ({...p, all: !p.all}))} />
        {!collapsed.all && (
          <>
            {otherNodes.map(node => renderNode(node, 0))}
            {creating ? (
              <div className="flex items-center gap-1 px-2 py-1 ml-3">
                <input value={newName} onChange={e => setNewName(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') handleCreate(); if (e.key === 'Escape') { setCreating(false); setCreateParent(''); } }}
                  onBlur={() => { if (!newName.trim()) { setCreating(false); setCreateParent(''); } }}
                  placeholder={createParent ? `Subcarpeta en ${getFolderDisplayName(createParent)}` : 'Nombre de carpeta'} autoFocus
                  className="flex-1 text-[12px] px-1.5 py-0.5 border border-[#0078d4] rounded outline-none bg-white dark:bg-[#1e1e1e]" />
              </div>
            ) : (
              <button onClick={() => { setCreating(true); setCreateParent(''); }}
                className="flex items-center gap-1.5 px-2 py-1 ml-3 text-[12px] text-[#106ebe] hover:bg-[#e1dfdd] rounded transition-colors">
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Nueva carpeta
              </button>
            )}
          </>
        )}
      </nav>

      {/* Mi actividad */}
      <div className="border-t border-[#edebe9] px-1 pb-1 shrink-0">
        <SectionHeader title="Mi actividad" collapsed={collapsed.stats} onToggle={() => setCollapsed(p => ({...p, stats: !p.stats}))} />
        {!collapsed.stats && (
          <div className="px-2 py-1 space-y-[3px] text-[11px] text-[#605e5c] dark:text-[#999]">
            {statsLoading && !stats ? (
              <div className="text-[11px] text-[#a19f9d] italic py-1">Cargando...</div>
            ) : stats ? (
              <>
                <div className="flex items-center gap-1.5">
                  <span className="w-[14px] text-center opacity-70">{"\u{1F4CA}"}</span>
                  <span>Bandeja: <b className="text-[#323130] dark:text-[#e0e0e0]">{stats.inbox_total}</b> mensajes</span>
                  {stats.inbox_unread > 0 && <span className="text-[#106ebe] font-semibold">({stats.inbox_unread} sin leer)</span>}
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-[14px] text-center opacity-70">{"\u{1F4E4}"}</span>
                  <span>Hoy: <b className="text-[#323130] dark:text-[#e0e0e0]">{stats.sent_today}</b></span>
                  <span className="text-[#a19f9d]">|</span>
                  <span>Semana: <b className="text-[#323130] dark:text-[#e0e0e0]">{stats.sent_week}</b></span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-[14px] text-center opacity-70">{"\u{1F4DD}"}</span>
                  <span>Borradores: <b className="text-[#323130] dark:text-[#e0e0e0]">{stats.drafts}</b></span>
                  <span className="text-[#a19f9d]">|</span>
                  <span>Papelera: <b className="text-[#323130] dark:text-[#e0e0e0]">{stats.trash}</b></span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-[14px] text-center opacity-70">{"\u{1F4BE}"}</span>
                  <span>Almacenamiento: <b className="text-[#323130] dark:text-[#e0e0e0]">{stats.storage_used_mb >= 1024 ? (stats.storage_used_mb / 1024).toFixed(1) + ' GB' : stats.storage_used_mb + ' MB'}</b></span>
                </div>
                {stats.top_senders.length > 0 && (
                  <div className="mt-1 pt-1 border-t border-[#edebe9] dark:border-[#333]">
                    <div className="text-[10px] uppercase tracking-wider text-[#605e5c] font-semibold mb-0.5">Top remitentes (30d)</div>
                    {stats.top_senders.map((s, i) => (
                      <div key={i} className="flex items-center gap-1 truncate">
                        <span className="text-[10px] text-[#605e5c] w-3 text-right">{s.count}</span>
                        <span className="truncate">{s.name || s.email}</span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : null}
          </div>
        )}
      </div>

      {/* Context menu */}
      {ctxMenu && <ContextMenu x={ctxMenu.x} y={ctxMenu.y} items={getFolderCtxItems(ctxMenu.folder)} onClose={() => setCtxMenu(null)} />}

      {/* Tooltip */}
      {tooltip && (
        <div className="fixed bg-[#323130] text-white text-[11px] px-2.5 py-1.5 rounded shadow-lg z-[9999] pointer-events-none max-w-[250px]"
          style={{ left: tooltip.x, top: tooltip.y }}>
          <div className="font-medium">{getFolderDisplayName(tooltip.folder.name)}</div>
          {tooltip.folder.name.includes('.') && (
            <div className="text-[10px] text-[#c8c6c4] mt-0.5">Ruta: {tooltip.folder.name.replace(/\./g, ' / ')}</div>
          )}
          <div className="text-[10px] text-[#c8c6c4]">
            {tooltip.folder.unseen > 0 ? `${tooltip.folder.unseen} sin leer` : 'Sin mensajes nuevos'}
            {!systemFolders.has(tooltip.folder.name) && ' — Arrastra para mover'}
          </div>
        </div>
      )}

      {/* Modal mover carpeta */}
      {moveModal && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={() => setMoveModal(null)}>
          <div className="bg-white rounded-lg shadow-xl p-4 w-[320px] max-h-[420px] flex flex-col" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-[#323130] mb-1">
              Mover carpeta
            </h3>
            <p className="text-xs text-[#605e5c] mb-3">
              Selecciona dónde mover &quot;{getFolderDisplayName(moveModal.folder.name)}&quot;
            </p>
            <div className="flex-1 overflow-y-auto space-y-0.5 mb-3 border border-[#edebe9] rounded p-1">
              <button onClick={() => handleMoveFolder(moveModal.folder.name, '')}
                className="w-full text-left px-3 py-1.5 text-sm hover:bg-[#e1dfdd] rounded text-[#323130] flex items-center gap-2">
                <svg className="w-4 h-4 text-[#605e5c] dark:text-[#999]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3" />
                </svg>
                Nivel principal (raíz)
              </button>
              <div className="h-px bg-[#edebe9] my-1" />
              {allFolderNames
                .filter(n => n !== moveModal.folder.name && !n.startsWith(moveModal.folder.name + '.'))
                .map(n => (
                  <button key={n} onClick={() => handleMoveFolder(moveModal.folder.name, n)}
                    className="w-full text-left px-3 py-1.5 text-sm hover:bg-[#e1dfdd] rounded text-[#323130] truncate flex items-center gap-2"
                    style={{ paddingLeft: `${12 + (n.split('.').length - 1) * 14}px` }}>
                    <svg className="w-3.5 h-3.5 text-[#605e5c] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={icons.folder} />
                    </svg>
                    {getFolderDisplayName(n)}
                  </button>
                ))}
            </div>
            <button onClick={() => setMoveModal(null)}
              className="w-full px-3 py-1.5 text-sm text-[#605e5c] hover:bg-[#e1dfdd] rounded border border-[#edebe9] dark:border-[#333]">
              Cancelar
            </button>
          </div>
        </div>
      )}

      {/* Modal de confirmación */}
      {confirmModal && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={() => setConfirmModal(null)}>
          <div className="bg-white rounded-lg shadow-xl p-5 w-[340px]" onClick={e => e.stopPropagation()}>
            <h3 className={`text-sm font-semibold mb-2 ${confirmModal.danger ? 'text-[#a4262c]' : 'text-[#323130]'}`}>
              {confirmModal.title}
            </h3>
            <p className="text-sm text-[#605e5c] mb-4">{confirmModal.message}</p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setConfirmModal(null)}
                className="px-4 py-1.5 text-sm text-[#605e5c] hover:bg-[#e1dfdd] rounded border border-[#edebe9] dark:border-[#333]">
                Cancelar
              </button>
              <button onClick={() => { confirmModal.onConfirm(); setConfirmModal(null); }}
                className={`px-4 py-1.5 text-sm text-white rounded ${
                  confirmModal.danger ? 'bg-[#a4262c] hover:bg-[#8a2121]' : 'bg-[#0078d4] hover:bg-[#106ebe]'
                }`}>
                Confirmar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function SectionHeader({ title, collapsed, onToggle }: { title: string; collapsed?: boolean; onToggle: () => void }) {
  return (
    <button onClick={onToggle}
      className="flex items-center gap-1 px-1.5 py-[3px] w-full text-[11px] font-semibold text-[#605e5c] uppercase tracking-wider hover:bg-[#e1dfdd] rounded transition-colors mt-1.5">
      <svg className={`w-[10px] h-[10px] transition-transform ${collapsed ? '' : 'rotate-90'}`} fill="currentColor" viewBox="0 0 20 20">
        <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
      </svg>
      {title}
    </button>
  );
}
