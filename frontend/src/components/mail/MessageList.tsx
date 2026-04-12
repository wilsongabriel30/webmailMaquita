// @ts-nocheck
import { useEffect, useCallback, useRef, useState } from 'react';
import { useMailStore } from '../../store/mailStore';
import { usePolling } from '../../hooks/usePolling';
import { api } from '../../api/client';
import { formatDistanceToNow } from 'date-fns';
import { es } from 'date-fns/locale';
import { ContextMenu, type MenuItem } from '../common/ContextMenu';
import { showToast } from '../common/Toast';
import type { MessagesResponse, MessageFull, MessageSummary } from '../../types';
import { usePriority } from '../../hooks/usePriority';
import { getFolderDisplayName } from '../../folders';

function fmtDate(s: string | null): string {
  if (!s) return '';
  try {
    const d = new Date(s), now = new Date(), diff = now.getTime() - d.getTime();
    if (diff < 86400000 && d.toDateString() === now.toDateString())
      return d.toLocaleTimeString('es-EC', { hour: '2-digit', minute: '2-digit' });
    if (diff < 604800000) return formatDistanceToNow(d, { addSuffix: false, locale: es });
    if (d.getFullYear() === now.getFullYear())
      return d.toLocaleDateString('es-EC', { day: 'numeric', month: 'short' });
    return d.toLocaleDateString('es-EC', { day: 'numeric', month: 'short', year: '2-digit' });
  } catch { return ''; }
}

function extractName(from: string, avatarMap?: Record<string, { name: string; initials: string }>): string {
  if (avatarMap) {
    const email = extractEmail(from);
    const avatar = avatarMap[email];
    if (avatar && avatar.name) return avatar.name;
  }
  const m = from.match(/^"?([^"<]+)"?\s*</);
  return m ? m[1].trim() : from.replace(/<.*>/, '').trim() || from;
}

function extractEmail(from: string): string {
  const m = from.match(/<([^>]+)>/);
  return m ? m[1].toLowerCase() : from.trim().toLowerCase();
}

function getInitials(from: string, avatarMap?: Record<string, { name: string; initials: string }>): string {
  if (avatarMap) {
    const email = extractEmail(from);
    const avatar = avatarMap[email];
    if (avatar && avatar.initials) return avatar.initials;
    if (avatar && avatar.name) {
      const parts = avatar.name.trim().split(/\s+/);
      if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
      return parts[0][0].toUpperCase();
    }
  }
  const name = extractName(from);
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return name.charAt(0).toUpperCase();
}

const palette = ['#0078d4','#107c10','#8764b8','#ca5010','#b4009e','#038387','#4f6bed','#c239b3','#da3b01','#00b7c3'];
function getColor(s: string) { let h=0; for(let i=0;i<s.length;i++) h=s.charCodeAt(i)+((h<<5)-h); return palette[Math.abs(h)%palette.length]; }

// Icons
const flagIcon = 'M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2z';
const deleteIcon = 'M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16';
const archiveIcon = 'M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4';
const unreadIcon = 'M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z';
const replyIcon = 'M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6';
const forwardIcon = 'M21 10h-10a8 8 0 00-8 8v2M21 10l-6 6m6-6l-6-6';
const moveIcon = 'M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z';

/* ---- Thread grouping helper ---- */
interface ThreadGroup {
  thread_id: string;
  messages: MessageSummary[];
  latest: MessageSummary;
  count: number;
  hasUnread: boolean;
  hasFlagged: boolean;
}

function groupByThread(messages: MessageSummary[]): ThreadGroup[] {
  const map = new Map<string, MessageSummary[]>();
  for (const msg of messages) {
    const tid = msg.thread_id || `single-${msg.uid}`;
    if (!map.has(tid)) map.set(tid, []);
    map.get(tid)!.push(msg);
  }
  const groups: ThreadGroup[] = [];
  for (const [tid, msgs] of map) {
    // Sort by date descending within each thread to get latest
    msgs.sort((a, b) => {
      const da = a.date ? new Date(a.date).getTime() : 0;
      const db = b.date ? new Date(b.date).getTime() : 0;
      return db - da;
    });
    groups.push({
      thread_id: tid,
      messages: msgs,
      latest: msgs[0],
      count: msgs.length,
      hasUnread: msgs.some(m => !m.seen),
      hasFlagged: msgs.some(m => m.flagged),
    });
  }
  // Sort groups: flagged first, then by latest message date
  groups.sort((a, b) => {
    if (a.hasFlagged && !b.hasFlagged) return -1;
    if (!a.hasFlagged && b.hasFlagged) return 1;
    const da = a.latest.date ? new Date(a.latest.date).getTime() : 0;
    const db = b.latest.date ? new Date(b.latest.date).getTime() : 0;
    return db - da;
  });
  return groups;
}

export function MessageList() {
  const {
    currentFolder, messages, totalMessages, currentPage, searchQuery, filter,
    loadingMessages, setMessages, setLoadingMessages,
    setSelectedMessage, setLoadingMessage, selectedMessage, selectedUids, toggleSelection,
    openCompose, density, previewLines, viewMode, setThreadMessages, setLoadingThread, clearThread, folders,
  } = useMailStore();

  const [ctxMenu, setCtxMenu] = useState<{ x: number; y: number; msg: MessageSummary } | null>(null);
  const [activeTab, setActiveTab] = useState<'focused' | 'other'>('focused');
  const [avatarMap, setAvatarMap] = useState<Record<string, { name: string; initials: string }>>({});
  const [expandedThreads, setExpandedThreads] = useState<Set<string>>(new Set());
  const [spamScanning, setSpamScanning] = useState(false);
  const [spamResults, setSpamResults] = useState<{ uid: number; score: number; reasons: string[] }[]>([]);
  const lastClickIdx = useRef<number>(-1);
  const prevTotalRef = useRef<number>(0);
  const { priorityMap, loading: priorityLoading, fetchPriority, reclassify } = usePriority();

  // Initialize notification sound
  useEffect(() => {
    const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
    const createBeep = () => {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.frequency.value = 880;
      osc.type = 'sine';
      gain.gain.value = 0.08;
      osc.start();
      gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.3);
      osc.stop(audioCtx.currentTime + 0.3);
    };
    (window as any).__maquitaBeep = createBeep;
    return () => { audioCtx.close(); };
  }, []);

  const fetch_ = useCallback(() => {
    if (!currentFolder) return;
    // Only show loading skeleton on first load (empty list), not on refresh
    if (messages.length === 0) setLoadingMessages(true);
    const p = new URLSearchParams({ page: String(currentPage), per_page: '50' });
    if (searchQuery) p.set('search', searchQuery);
    api.get<MessagesResponse>(`/mail/messages/${encodeURIComponent(currentFolder)}?${p}`)
      .then(r => {
      if (prevTotalRef.current > 0 && r.total > prevTotalRef.current && currentFolder === 'INBOX') {
        const newCount = r.total - prevTotalRef.current;
        try { (window as any).__maquitaBeep?.(); } catch {}
        if (Notification.permission === 'granted') {
          new Notification('Maquita Mail', { body: `${newCount} correo${newCount > 1 ? 's' : ''} nuevo${newCount > 1 ? 's' : ''}`, icon: '/favicon.svg' });
        } else if (Notification.permission !== 'denied') {
          Notification.requestPermission();
        }
        document.title = `(${r.total - (r.messages.filter((m: any) => m.seen).length)}) Maquita Mail`;
      }
      prevTotalRef.current = r.total;
      setMessages(r.messages, r.total, r.page);
    }).catch(console.error);
  }, [currentFolder, currentPage, searchQuery]);

  useEffect(() => { fetch_(); }, [fetch_]);
  useEffect(() => { const h=()=>fetch_(); window.addEventListener('refresh-messages',h); return ()=>window.removeEventListener('refresh-messages',h); }, [fetch_]);
  usePolling(fetch_, 60000, true);

  // Fetch priority classification for INBOX
  useEffect(() => {
    if (currentFolder === 'INBOX' && messages.length > 0) {
      fetchPriority(currentFolder);
    }
  }, [currentFolder, messages.length, fetchPriority]);

  // Spam scan function
  const scanSpam = useCallback(async (autoMove = false) => {
    if (!currentFolder) return;
    setSpamScanning(true);
    try {
      const res = await api.get<{ scanned: number; spam_found: number; moved: number; details: any[] }>(
        `/mail/spam/scan?folder=${encodeURIComponent(currentFolder)}&limit=50&auto_move=${autoMove}`
      );
      setSpamResults(res.details || []);
      if (res.spam_found > 0) {
        if (autoMove && res.moved > 0) {
          showToast(`${res.moved} correo${res.moved > 1 ? "s" : ""} de spam movido${res.moved > 1 ? "s" : ""} a Spam`);
          window.dispatchEvent(new CustomEvent("refresh-messages"));
        } else if (!autoMove) {
          showToast(`${res.spam_found} posible${res.spam_found > 1 ? "s" : ""} spam detectado${res.spam_found > 1 ? "s" : ""}`);
        }
      } else {
        showToast("No se detect\u00f3 spam");
      }
    } catch {
      showToast("Error al escanear spam");
    }
    setSpamScanning(false);
  }, [currentFolder]);

  const reportSpam = useCallback(async (uids: number[]) => {
    try {
      await api.post("/mail/spam/report", { folder: currentFolder, uids });
      showToast(`${uids.length} reportado${uids.length > 1 ? "s" : ""} como spam`);
      window.dispatchEvent(new CustomEvent("refresh-messages"));
    } catch {}
  }, [currentFolder]);

  const markNotSpam = useCallback(async (uids: number[]) => {
    try {
      await api.post("/mail/spam/not-spam", { folder: currentFolder, uids });
      showToast("Movido a Bandeja de entrada");
      window.dispatchEvent(new CustomEvent("refresh-messages"));
    } catch {}
  }, [currentFolder]);

  // Fetch avatar data
  useEffect(() => {
    if (!messages.length) return;
    const emails = [...new Set(messages.map(m => extractEmail(m.from)))];
    const missing = emails.filter(e => !avatarMap[e]);
    if (!missing.length) return;
    const batch = missing.slice(0, 200).join(',');
    api.get<Record<string, { name: string; initials: string }>>(`/contacts/avatars?emails=${encodeURIComponent(batch)}`)
      .then(data => { setAvatarMap(prev => ({ ...prev, ...data })); })
      .catch(() => {});
  }, [messages]);

  const handleFlag = async (uid: number, flagged: boolean) => {
    try {
      await api.post(`/mail/flags/${encodeURIComponent(currentFolder)}/${uid}`, { flags: '\\Flagged', add: !flagged });
      const updated = useMailStore.getState().messages.map(m => m.uid === uid ? { ...m, flagged: !flagged } : m);
      useMailStore.getState().setMessages(updated, totalMessages, currentPage);
    } catch {}
  };

  const handleRowClick = (uid: number, idx: number, e: React.MouseEvent) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      toggleSelection(uid);
      lastClickIdx.current = idx;
      return;
    }
    if (e.shiftKey) {
      e.preventDefault();
      handleShiftClick(idx, e);
      return;
    }
    if (selectedUids.size > 0) {
      toggleSelection(uid);
      lastClickIdx.current = idx;
      return;
    }
    handleSelect(uid);
  };

  const handleSelect = async (uid: number) => {
    // If in Drafts folder, open in compose for editing
    if (currentFolder === 'Drafts') {
      setLoadingMessage(true);
      try {
        const msg = await api.get<MessageFull>(`/mail/message/${encodeURIComponent(currentFolder)}/${uid}`);
        setLoadingMessage(false);
        const toList = msg.to ? msg.to.split(',').map(s => s.trim()).filter(Boolean) : [];
        const ccList = msg.cc ? msg.cc.split(',').map(s => s.trim()).filter(Boolean) : [];
        openCompose('new', {
          to: toList,
          cc: ccList,
          subject: msg.subject || '',
          text_body: '',
          html_body: msg.html_body || msg.text_body || '',
          in_reply_to: msg.in_reply_to || '',
          references: msg.references || '',
          draft_uid: uid,
        });
        return;
      } catch (err) {
        console.error('Error loading draft for edit:', err);
        setLoadingMessage(false);
        return;
      }
    }
    setLoadingMessage(true);
    clearThread();
    try {
      const msg = await api.get<MessageFull>(`/mail/message/${encodeURIComponent(currentFolder)}/${uid}`);
      // Modo 'popout': abrir mensaje en ventana emergente
      if (useMailStore.getState().readingPane === 'popout') {
        const w = window.open('', '_blank', 'width=800,height=600,scrollbars=yes,resizable=yes');
        if (w) {
          const subj = msg.subject || '(sin asunto)';
          const from = msg.from || '';
          const date = msg.date ? new Date(msg.date).toLocaleString('es-EC') : '';
          const body = msg.html_body || ('<pre style="white-space:pre-wrap">' + (msg.text_body || '') + '</pre>');
          w.document.write('<!DOCTYPE html><html><head><meta charset="utf-8"><title>' + subj + '</title></head>'
            + '<body style="font-family:Segoe UI,Calibri,sans-serif;max-width:900px;margin:20px auto;padding:20px;color:#323130;">'
            + '<h2 style="margin:0 0 8px;font-size:20px;">' + subj + '</h2>'
            + '<div style="color:#605e5c;font-size:13px;margin-bottom:16px;border-bottom:1px solid #edebe9;padding-bottom:12px;">'
            + '<b>De:</b> ' + from + '<br/><b>Fecha:</b> ' + date
            + (msg.to ? '<br/><b>Para:</b> ' + msg.to : '')
            + (msg.cc ? '<br/><b>CC:</b> ' + msg.cc : '') + '</div>'
            + '<div style="font-size:14px;line-height:1.6;">' + body + '</div>'
            + '</body></html>');
          w.document.close();
        }
        setLoadingMessage(false);
        return;
      }
      setSelectedMessage(msg);
      // If in conversations mode and message has a thread_id, fetch thread
      if (useMailStore.getState().viewMode === 'conversations' && msg.thread_id) {
        fetchThreadMessages(msg.thread_id, msg.uid);
      }
      const updated = useMailStore.getState().messages.map(m => m.uid === uid ? { ...m, seen: true, flags: m.flags.includes('\\Seen') ? m.flags : [...m.flags, '\\Seen'] } : m);
      useMailStore.getState().setMessages(updated, totalMessages, currentPage);
      const flds = useMailStore.getState().folders.map(f => f.name === currentFolder && f.unseen > 0 ? { ...f, unseen: f.unseen - 1 } : f);
      useMailStore.getState().setFolders(flds);
    } catch (err) {
      console.error(err);
      useMailStore.getState().setLoadingMessage(false);
    }
  };

  const fetchThreadMessages = async (threadId: string, currentUid: number) => {
    setLoadingThread(true);
    try {
      const res = await api.get<{ messages: MessageFull[]; count: number }>(
        `/mail/threads/${encodeURIComponent(currentFolder)}/${encodeURIComponent(threadId)}`
      );
      if (res.messages && res.messages.length > 1) {
        setThreadMessages(res.messages);
        // Expand only the latest message (highest uid or latest date)
        const latestUid = currentUid;
        useMailStore.setState({ threadExpanded: new Set([latestUid]) });
      } else {
        clearThread();
      }
    } catch {
      clearThread();
    }
    setLoadingThread(false);
  };

  const handleThreadHeaderClick = (group: ThreadGroup) => {
    const newExpanded = new Set(expandedThreads);
    if (newExpanded.has(group.thread_id)) {
      newExpanded.delete(group.thread_id);
    } else {
      newExpanded.add(group.thread_id);
    }
    setExpandedThreads(newExpanded);
  };

  const handleShiftClick = (idx: number, e: React.MouseEvent) => {
    if (e.shiftKey && lastClickIdx.current >= 0) {
      const start = Math.min(lastClickIdx.current, idx);
      const end = Math.max(lastClickIdx.current, idx);
      const uidsToSelect = filtered.slice(start, end + 1).map(m => m.uid);
      const s = new Set(useMailStore.getState().selectedUids);
      uidsToSelect.forEach(u => s.add(u));
      useMailStore.setState({ selectedUids: s });
    } else {
      toggleSelection(filtered[idx].uid);
    }
    lastClickIdx.current = idx;
  };

  const quickAction = async (uid: number, action: string, dest?: string) => {
    try {
      await api.post(`/mail/bulk-action/${encodeURIComponent(currentFolder)}`, {
        uids: [uid], action, dest_folder: dest || '',
      });
      showToast(
        action === 'move' ? `Movido a ${dest}` : action === 'delete' ? 'Eliminado' : action === 'archive' ? 'Archivado' : 'Hecho',
        { label: 'Deshacer', onClick: () => {} }
      );
      const sel = useMailStore.getState().selectedMessage;
      if (sel && sel.uid === uid) {
        useMailStore.getState().setSelectedMessage(null);
      }
      window.dispatchEvent(new CustomEvent('refresh-messages'));
    } catch {}
  };

  const filtered = messages.filter(m => {
    if (filter === 'unread') return !m.seen;
    if (filter === 'flagged') return m.flagged;
    return true;
  }).filter(m => {
    // Apply priority filter only in INBOX when priority data is loaded
    if (currentFolder !== 'INBOX' || Object.keys(priorityMap).length === 0) return true;
    const p = priorityMap[m.uid];
    if (!p) return activeTab === 'focused'; // unclassified goes to focused
    if (activeTab === 'focused') return p.priority === 'high';
    return p.priority !== 'high'; // "other" tab shows normal + low
  }).sort((a, b) => {
    if (a.flagged && !b.flagged) return -1;
    if (!a.flagged && b.flagged) return 1;
    return 0;
  });

  const isConversationMode = viewMode === 'conversations';
  const threadGroups = isConversationMode ? groupByThread(filtered) : null;

  const totalPages = Math.ceil(totalMessages / 50);
  const folderLabel = getFolderDisplayName(currentFolder);

  const getCtxItems = (msg: MessageSummary): MenuItem[] => [
    { label: 'Responder', icon: replyIcon, onClick: () => openCompose('reply', { to: [msg.from], subject: `Re: ${msg.subject}`, text_body: '', html_body: '' }) },
    { label: 'Reenviar', icon: forwardIcon, onClick: () => openCompose('forward', { to: [], subject: `RV: ${msg.subject}`, text_body: '', html_body: '' }) },
    { label: '', icon: '', onClick: () => {}, divider: true },
    { label: msg.seen ? 'Marcar como no leído' : 'Marcar como leído', icon: unreadIcon, onClick: () => quickAction(msg.uid, msg.seen ? 'mark_unread' : 'mark_read') },
    { label: msg.flagged ? 'Quitar marca' : 'Marcar con bandera', icon: flagIcon, onClick: () => handleFlag(msg.uid, msg.flagged) },
    { label: '', icon: '', onClick: () => {}, divider: true },
    { label: 'Archivar', icon: archiveIcon, onClick: () => quickAction(msg.uid, 'archive') },
    {
      label: 'Mover a...',
      icon: moveIcon,
      onClick: () => {},
      children: (folders || []).map((folder) => {
        const folderName = typeof folder === 'string' ? folder : folder.name;
        return {
          label: getFolderDisplayName(folderName),
          icon: moveIcon,
          disabled: folderName === currentFolder,
          onClick: () => quickAction(msg.uid, 'move', folderName),
        };
      }),
    },
    { label: '', icon: '', onClick: () => {}, divider: true },
    { label: 'Eliminar', icon: deleteIcon, onClick: () => quickAction(msg.uid, currentFolder === 'Trash' ? 'delete' : 'move', 'Trash'), danger: true },
  ];

  /* ---- Render a single message row ---- */
  const renderMessageRow = (msg: MessageSummary, idx: number, threadCount?: number) => {
    const active = selectedMessage?.uid === msg.uid;
    const checked = selectedUids.has(msg.uid);
    const snippetStyle = previewLines === 1
      ? undefined
      : {
          display: '-webkit-box',
          WebkitBoxOrient: 'vertical' as const,
          WebkitLineClamp: previewLines,
          overflow: 'hidden',
          whiteSpace: 'normal' as const,
        };
    const snippetMinHeight = previewLines === 1 ? undefined : `${previewLines * 16}px`;
    return (
      <div key={msg.uid}
        draggable
        onDragStart={(e) => {
          const uids = selectedUids.has(msg.uid) && selectedUids.size > 0
            ? Array.from(selectedUids) : [msg.uid];
          e.dataTransfer.setData('application/x-mail-uids', JSON.stringify(uids));
          e.dataTransfer.setData('application/x-mail-folder', currentFolder);
          e.dataTransfer.effectAllowed = 'move';
          const badge = document.createElement('div');
          badge.textContent = uids.length > 1 ? `${uids.length} mensajes` : msg.subject || '1 mensaje';
          badge.style.cssText = 'padding:4px 10px;background:#0078d4;color:#fff;border-radius:4px;font-size:12px;position:absolute;top:-9999px';
          document.body.appendChild(badge);
          e.dataTransfer.setDragImage(badge, 0, 0);
          setTimeout(() => document.body.removeChild(badge), 0);
        }}
        onClick={(e) => handleRowClick(msg.uid, idx, e)}
        onContextMenu={(e) => { e.preventDefault(); setCtxMenu({ x: e.clientX, y: e.clientY, msg }); }}
        className={`group relative flex gap-2.5 pl-1 pr-3 ${density === "full" ? "py-[14px]" : density === "medium" ? "py-[10px]" : "py-[6px]"} cursor-pointer border-b border-[#f3f2f1] transition-all ${
          checked ? 'bg-[#deecf9]' : active ? 'bg-[#eff6fc]' : 'hover:bg-[#f3f2f1]'
        }`}>

        {/* Unread dot + spam indicator */}
        <div className="w-[4px] shrink-0 flex items-start pt-4">
          <div className={`w-[6px] h-[6px] rounded-full ${
            spamResults.some(s => s.uid === msg.uid) ? 'bg-[#ca5010]' : !msg.seen ? 'bg-[#0078d4]' : ''
          }`} title={spamResults.find(s => s.uid === msg.uid)?.reasons?.join(', ') || ''} />
        </div>

        {/* Checkbox / Avatar */}
        <div className="shrink-0 pt-0.5"
          onClick={e => { e.stopPropagation(); handleShiftClick(idx, e); }}>
          <div className={`w-[32px] h-[32px] rounded-full flex items-center justify-center text-[11px] font-semibold cursor-pointer transition-all ${
            checked ? 'bg-[#0078d4] text-white' : 'text-white group-hover:ring-2 group-hover:ring-[#c8c6c4]'
          }`} style={checked ? {} : { backgroundColor: getColor(msg.from) }}>
            {checked ? (
              <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" /></svg>
            ) : getInitials(msg.from, avatarMap)}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 min-w-0 flex-1">
              <span className={`text-[13px] truncate ${!msg.seen ? 'font-semibold text-[#323130]' : 'text-[#605e5c]'}`}>
                {extractName(msg.from, avatarMap)}
              </span>
              {/* Thread count badge */}
              {threadCount && threadCount > 1 && (
                <span className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full bg-[#0078d4] text-white text-[10px] font-semibold shrink-0">
                  {threadCount}
                </span>
              )}
            </div>
            <div className="flex items-center gap-1 shrink-0 ml-2">
              {msg.has_attachments && (
                <svg className="w-[12px] h-[12px] text-[#605e5c]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                </svg>
              )}
              {msg.importance === 'high' && (
                <svg className="w-[12px] h-[12px] text-[#d13438]" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
              )}
              <span className="text-[11px] text-[#a19f9d] group-hover:hidden">{fmtDate(msg.date)}</span>
            </div>
          </div>
          <p className={`text-[13px] truncate leading-[18px] ${!msg.seen ? 'font-medium text-[#323130]' : 'text-[#605e5c]'}`}>
            {msg.subject || '(Sin asunto)'}
          </p>
          <p
            className={`text-[12px] text-[#a19f9d] leading-[16px] ${previewLines === 1 ? 'truncate' : ''}`}
            style={{ ...snippetStyle, minHeight: snippetMinHeight }}
          >
            {msg.snippet || '\u00A0'}
          </p>
        </div>

        {/* Flag */}
        <div className="flex flex-col items-center justify-between shrink-0 py-0.5">
          <button onClick={e => { e.stopPropagation(); handleFlag(msg.uid, msg.flagged); }}
            className={`transition-colors ${msg.flagged ? 'text-[#d13438]' : 'text-transparent group-hover:text-[#a19f9d] hover:!text-[#d13438]'}`}
            title={msg.flagged ? 'Quitar marca' : 'Marcar'}>
            <svg className="w-[14px] h-[14px]" fill={msg.flagged ? 'currentColor' : 'none'} stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={flagIcon} />
            </svg>
          </button>
        </div>

        {/* Quick actions on hover */}
        <div className="hidden group-hover:flex items-start gap-0.5 absolute right-2 top-1 bg-[#f3f2f1] rounded shadow-sm border border-[#e1dfdd] p-0.5">
          <QA icon={deleteIcon} title="Eliminar" onClick={e => { e.stopPropagation(); quickAction(msg.uid, currentFolder === 'Trash' ? 'delete' : 'move', 'Trash'); }} />
          <QA icon={archiveIcon} title="Archivar" onClick={e => { e.stopPropagation(); quickAction(msg.uid, 'archive'); }} />
          <QA icon={unreadIcon} title={msg.seen ? 'No leído' : 'Leído'}
            onClick={e => { e.stopPropagation(); quickAction(msg.uid, msg.seen ? 'mark_unread' : 'mark_read'); }} />
          <QA icon={flagIcon} title="Marcar" filled={msg.flagged}
            onClick={e => { e.stopPropagation(); handleFlag(msg.uid, msg.flagged); }} />
        </div>
      </div>
    );
  };

  /* ---- Render thread group (conversation mode) ---- */
  const renderThreadGroup = (group: ThreadGroup, gIdx: number) => {
    const isExpanded = expandedThreads.has(group.thread_id);
    const msg = group.latest;

    if (group.count === 1) {
      // Single message thread - render normally
      return renderMessageRow(msg, gIdx);
    }

    return (
      <div key={group.thread_id}>
        {/* Thread header - shows latest message with count */}
        {renderMessageRow(msg, gIdx, group.count)}

        {/* Expanded thread children */}
        {isExpanded && (
          <div className="border-l-2 border-[#0078d4] ml-3">
            {group.messages.slice(1).map((childMsg, cIdx) => (
              <div key={childMsg.uid} className="pl-2">
                {renderMessageRow(childMsg, gIdx + cIdx + 1)}
              </div>
            ))}
          </div>
        )}

        {/* Expand/collapse button for threads with multiple messages */}
        {group.count > 1 && (
          <button
            onClick={(e) => { e.stopPropagation(); handleThreadHeaderClick(group); }}
            className="w-full flex items-center justify-center py-0.5 text-[11px] text-[#0078d4] hover:bg-[#f3f2f1] transition-colors border-b border-[#f3f2f1]"
          >
            {isExpanded ? (
              <span className="flex items-center gap-1">
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" /></svg>
                Ocultar {group.count - 1} mensaje{group.count - 1 > 1 ? 's' : ''} anterior{group.count - 1 > 1 ? 'es' : ''}
              </span>
            ) : (
              <span className="flex items-center gap-1">
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                Ver {group.count - 1} mensaje{group.count - 1 > 1 ? 's' : ''} anterior{group.count - 1 > 1 ? 'es' : ''}
              </span>
            )}
          </button>
        )}
      </div>
    );
  };

  return (
    <div className="message-list-container w-[360px] border-r border-[#edebe9] flex flex-col shrink-0 bg-white">
      {/* Header with tabs */}
      <div className="border-b border-[#edebe9]">
        <div className="flex items-center justify-between px-4 pt-2">
          <div className="flex items-center gap-2">
            <input type="checkbox"
              checked={selectedUids.size > 0 && selectedUids.size === filtered.length}
              ref={(el) => { if (el) el.indeterminate = selectedUids.size > 0 && selectedUids.size < filtered.length; }}
              onChange={(e) => {
                if (e.target.checked) {
                  const s = new Set(filtered.map(m => m.uid));
                  useMailStore.setState({ selectedUids: s });
                } else {
                  useMailStore.getState().clearSelection();
                }
              }}
              className="w-4 h-4 rounded border-[#c8c6c4] text-[#0078d4] cursor-pointer accent-[#0078d4]"
              title="Seleccionar todos" />
            <h2 className="text-[14px] font-semibold text-[#323130] cursor-pointer hover:text-[#0078d4] transition-colors" onClick={() => { useMailStore.getState().setFilter("all"); setActiveTab("focused"); }}>{folderLabel}</h2>
          </div>
          <div className="flex items-center gap-1">
            {/* View mode toggle */}
            <button
              onClick={() => useMailStore.getState().setViewMode(isConversationMode ? 'messages' : 'conversations')}
              className={`px-1.5 py-0.5 rounded transition-colors mr-1 ${
                isConversationMode ? 'text-[#0078d4]' : 'text-[#a19f9d] hover:text-[#605e5c]'
              }`}
              title={isConversationMode ? 'Vista de conversaciones (clic para cambiar a mensajes)' : 'Vista de mensajes (clic para cambiar a conversaciones)'}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {isConversationMode ? (
                  /* Conversation/stack icon */
                  <g strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}>
                    <path d="M19 7H5a2 2 0 00-2 2v8a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2z" />
                    <path d="M5 7V5a2 2 0 012-2h10a2 2 0 012 2v2" />
                  </g>
                ) : (
                  /* List icon */
                  <g strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}>
                    <path d="M4 6h16M4 12h16M4 18h16" />
                  </g>
                )}
              </svg>
            </button>
            <div className="w-px h-4 bg-[#e1dfdd]" />
            <button
              onClick={() => scanSpam(true)}
              disabled={spamScanning}
              className={`px-1.5 py-0.5 rounded transition-colors mr-1 ${
                spamScanning ? 'text-[#ca5010] animate-pulse' : 'text-[#a19f9d] hover:text-[#ca5010] hover:bg-[#fde7e9]'
              }`}
              title={spamScanning ? 'Escaneando...' : 'Escanear spam con IA'}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
              </svg>
            </button>
            {spamResults.length > 0 && (
              <span className="text-[10px] text-[#ca5010] font-bold mr-1" title="Spam detectado">
                {spamResults.length}!
              </span>
            )}
            <div className="w-px h-4 bg-[#e1dfdd] mr-1" />
            {(['all','unread','flagged'] as const).map(f => (
              <button key={f} onClick={() => useMailStore.getState().setFilter(f)}
                className={`px-2 py-0.5 text-[11px] rounded transition-colors ${
                  filter === f ? 'bg-[#e1dfdd] text-[#323130] font-medium' : 'text-[#605e5c] hover:bg-[#e1dfdd]'
                }`}>{f === 'all' ? 'Todos' : f === 'unread' ? 'No leídos' : 'Marcados'}</button>
            ))}
          </div>
        </div>
        {/* Focused / Other tabs */}
        {currentFolder === 'INBOX' && (
          <div className="flex px-4 mt-1">
            {(['focused','other'] as const).map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)}
                className={`px-3 py-1.5 text-[13px] border-b-2 transition-colors ${
                  activeTab === tab ? 'border-[#0078d4] text-[#0078d4] font-medium' : 'border-transparent text-[#605e5c] hover:text-[#323130]'
                }`}>{tab === 'focused' ? 'Prioritarios' : 'Otros'}</button>
            ))}
          </div>
        )}
      </div>

      {/* Bulk actions bar */}
      {selectedUids.size > 0 && (
        <div className="flex items-center gap-1 px-3 py-1.5 bg-[#deecf9] border-b border-[#c7e0f4] shrink-0">
          <span className="text-[12px] text-[#0078d4] font-semibold mr-2">
            {selectedUids.size} seleccionado{selectedUids.size > 1 ? 's' : ''}
          </span>
          <button onClick={() => { const uids = Array.from(selectedUids); api.post(`/mail/bulk-action/${encodeURIComponent(currentFolder)}`, { uids, action: currentFolder === 'Trash' ? 'delete' : 'move', dest_folder: 'Trash' }).then(() => { showToast(`${uids.length} mensaje${uids.length > 1 ? 's' : ''} eliminado${uids.length > 1 ? 's' : ''}`); useMailStore.getState().clearSelection(); useMailStore.getState().setSelectedMessage(null); window.dispatchEvent(new CustomEvent('refresh-messages')); }); }}
            className="px-2 py-1 text-[12px] text-[#d13438] hover:bg-[#fde7e9] rounded flex items-center gap-1 font-medium" title="Eliminar seleccionados">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={deleteIcon} /></svg>
            Eliminar
          </button>
          <button onClick={() => { const uids = Array.from(selectedUids); api.post(`/mail/bulk-action/${encodeURIComponent(currentFolder)}`, { uids, action: 'archive', dest_folder: '' }).then(() => { showToast(`${uids.length} archivado${uids.length > 1 ? 's' : ''}`); useMailStore.getState().clearSelection(); useMailStore.getState().setSelectedMessage(null); window.dispatchEvent(new CustomEvent('refresh-messages')); }); }}
            className="px-2 py-1 text-[12px] text-[#323130] hover:bg-[#c7e0f4] rounded flex items-center gap-1 font-medium" title="Archivar seleccionados">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={archiveIcon} /></svg>
            Archivar
          </button>
          <button onClick={() => { const uids = Array.from(selectedUids); api.post(`/mail/bulk-action/${encodeURIComponent(currentFolder)}`, { uids, action: 'mark_read', dest_folder: '' }).then(() => { showToast('Marcados como leídos'); useMailStore.getState().clearSelection(); window.dispatchEvent(new CustomEvent('refresh-messages')); }); }}
            className="px-2 py-1 text-[12px] text-[#323130] hover:bg-[#c7e0f4] rounded flex items-center gap-1 font-medium" title="Marcar como leídos">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21.75 9v.906a2.25 2.25 0 01-1.183 1.981l-6.478 3.488M2.25 9v.906a2.25 2.25 0 001.183 1.981l6.478 3.488m8.839 0l.415.223a.75.75 0 00.882-.264l2.197-2.989M2.25 15.577l.415.223a.75.75 0 01.882-.264l2.197-2.989" /></svg>
            Leídos
          </button>
          <button onClick={() => { const uids = Array.from(selectedUids); api.post(`/mail/bulk-action/${encodeURIComponent(currentFolder)}`, { uids, action: 'move', dest_folder: 'Junk' }).then(() => { showToast('Movidos a Correo no deseado'); useMailStore.getState().clearSelection(); useMailStore.getState().setSelectedMessage(null); window.dispatchEvent(new CustomEvent('refresh-messages')); }); }}
            className="px-2 py-1 text-[12px] text-[#323130] hover:bg-[#c7e0f4] rounded flex items-center gap-1 font-medium" title="Marcar como spam">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" /></svg>
            Spam
          </button>
          <div className="flex-1" />
          <button onClick={() => useMailStore.getState().clearSelection()}
            className="px-2 py-1 text-[12px] text-[#605e5c] hover:bg-[#c7e0f4] rounded" title="Deseleccionar">
            x
          </button>
        </div>
      )}

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {loadingMessages ? (
          Array.from({length:12}).map((_,i) => (
            <div key={i} className="animate-pulse flex gap-2.5 px-4 py-[6px] border-b border-[#f3f2f1]">
              <div className="w-[32px] h-[32px] bg-[#e1dfdd] rounded-full shrink-0 mt-0.5" />
              <div className="flex-1 space-y-1 py-0.5">
                <div className="h-[10px] bg-[#e1dfdd] rounded w-2/3" />
                <div className="h-[10px] bg-[#e1dfdd] rounded w-4/5" />
                <div className="h-[8px] bg-[#f3f2f1] rounded w-full" />
              </div>
            </div>
          ))
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-40 text-[#a19f9d]">
            <svg className="w-10 h-10 mb-2 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
            </svg>
            <p className="text-[13px]">No hay mensajes</p>
          </div>
        ) : isConversationMode && threadGroups ? (
          threadGroups.map((group, gIdx) => renderThreadGroup(group, gIdx))
        ) : (
          filtered.map((msg, idx) => renderMessageRow(msg, idx))
        )}
      </div>

      {totalPages > 1 && (
        <div className="px-3 py-1.5 border-t border-[#edebe9] flex items-center justify-between text-[11px] text-[#605e5c]">
          <button disabled={currentPage<=1} onClick={() => useMailStore.getState().setPage(currentPage-1)}
            className="px-2 py-0.5 rounded hover:bg-[#e1dfdd] disabled:opacity-30">Anterior</button>
          <span>{currentPage} de {totalPages}</span>
          <button disabled={currentPage>=totalPages} onClick={() => useMailStore.getState().setPage(currentPage+1)}
            className="px-2 py-0.5 rounded hover:bg-[#e1dfdd] disabled:opacity-30">Siguiente</button>
        </div>
      )}

      {ctxMenu && <ContextMenu x={ctxMenu.x} y={ctxMenu.y} items={getCtxItems(ctxMenu.msg)} onClose={() => setCtxMenu(null)} />}
    </div>
  );
}

function QA({ icon, title, onClick, filled }: {
  icon: string; title: string; onClick: (e: React.MouseEvent) => void; filled?: boolean;
}) {
  return (
    <button onClick={onClick} title={title}
      className="w-[26px] h-[26px] rounded flex items-center justify-center text-[#605e5c] hover:bg-[#e1dfdd] hover:text-[#323130] transition-colors">
      <svg className="w-[14px] h-[14px]" fill={filled ? 'currentColor' : 'none'} stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={icon} />
      </svg>
    </button>
  );
}
