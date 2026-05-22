import { useEffect } from 'react';
import { useMailStore } from '../store/mailStore';
import {
  cacheMessageList,
  cacheFullMessage,
  cacheFolders,
  getCachedMessages,
  getCachedFolders,
  getCachedMessage,
  type OfflineMessage,
} from '../lib/offlineStore';
import type { MessageSummary, MessageFull, Folder } from '../types';

// Convert MessageSummary to OfflineMessage format
function toOfflineMessage(msg: MessageSummary | MessageFull, folder: string): OfflineMessage {
  const full = msg as MessageFull;
  return {
    id: `${folder}:${msg.uid}`,
    uid: msg.uid,
    folder,
    message_id: msg.message_id,
    thread_id: msg.thread_id,
    from: msg.from,
    to: msg.to,
    cc: full.cc,
    subject: msg.subject,
    date: msg.date,
    size: msg.size,
    flags: msg.flags,
    seen: msg.seen,
    flagged: msg.flagged,
    snippet: msg.snippet,
    has_attachments: msg.has_attachments,
    importance: msg.importance,
    html_body: full.html_body,
    text_body: full.text_body,
    attachments: full.attachments,
    references: full.references,
    in_reply_to: full.in_reply_to,
    has_remote_images: full.has_remote_images,
    blocked_image_count: full.blocked_image_count,
    cachedAt: Date.now(),
  };
}

// Convert OfflineMessage back to MessageSummary
function toMessageSummary(msg: OfflineMessage): MessageSummary {
  return {
    uid: msg.uid,
    folder: msg.folder,
    message_id: msg.message_id,
    thread_id: msg.thread_id,
    from: msg.from,
    to: msg.to,
    subject: msg.subject,
    date: msg.date,
    size: msg.size,
    flags: msg.flags,
    seen: msg.seen,
    flagged: msg.flagged,
    snippet: msg.snippet,
    has_attachments: msg.has_attachments,
    importance: msg.importance,
  };
}

// Convert OfflineMessage to MessageFull (if body is cached)
function toMessageFull(msg: OfflineMessage): MessageFull | null {
  if (!msg.html_body && !msg.text_body) return null;
  return {
    uid: msg.uid,
    folder: msg.folder,
    message_id: msg.message_id,
    thread_id: msg.thread_id,
    from: msg.from,
    to: msg.to,
    cc: msg.cc || '',
    subject: msg.subject,
    date: msg.date,
    size: msg.size,
    flags: msg.flags,
    seen: msg.seen,
    flagged: msg.flagged,
    snippet: msg.snippet,
    has_attachments: msg.has_attachments,
    importance: msg.importance,
    html_body: msg.html_body || '',
    text_body: msg.text_body || '',
    attachments: msg.attachments || [],
    references: msg.references || '',
    in_reply_to: msg.in_reply_to || '',
    has_remote_images: msg.has_remote_images || false,
    blocked_image_count: msg.blocked_image_count || 0,
  };
}

/**
 * Hook that automatically caches messages and folders to IndexedDB
 * and provides offline fallback when network is unavailable.
 */
export function useOfflineSync() {
  const messages = useMailStore((s) => s.messages);
  const folders = useMailStore((s) => s.folders);
  const currentFolder = useMailStore((s) => s.currentFolder);
  const selectedMessage = useMailStore((s) => s.selectedMessage);

  // Cache message list whenever it changes
  useEffect(() => {
    if (messages.length > 0 && navigator.onLine) {
      const offlineMsgs = messages.map(m => toOfflineMessage(m, currentFolder));
      cacheMessageList(currentFolder, offlineMsgs).catch(() => {});
    }
  }, [messages, currentFolder]);

  // Cache full message when user opens one
  useEffect(() => {
    if (selectedMessage && navigator.onLine) {
      const offlineMsg = toOfflineMessage(selectedMessage, selectedMessage.folder || currentFolder);
      cacheFullMessage(selectedMessage.folder || currentFolder, offlineMsg).catch(() => {});
    }
  }, [selectedMessage, currentFolder]);

  // Cache folders
  useEffect(() => {
    if (folders.length > 0 && navigator.onLine) {
      cacheFolders(folders.map(f => ({ name: f.name, unseen: f.unseen }))).catch(() => {});
    }
  }, [folders]);

  // Listen for sync-complete events
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail.sent > 0) {
        // Show a toast notification — dispatched via custom event since we can't use toast directly
        window.dispatchEvent(new CustomEvent('show-toast', {
          detail: { message: `${detail.sent} correo(s) enviado(s) desde la bandeja de salida` }
        }));
      }
    };
    window.addEventListener('offline-sync-complete', handler);
    return () => window.removeEventListener('offline-sync-complete', handler);
  }, []);
}

/**
 * Load cached messages for offline viewing.
 * Called from MessageList when offline.
 */
export async function loadOfflineMessages(folder: string): Promise<MessageSummary[]> {
  const cached = await getCachedMessages(folder);
  return cached.map(toMessageSummary);
}

/**
 * Load a cached full message for offline viewing.
 */
export async function loadOfflineMessage(folder: string, uid: number): Promise<MessageFull | null> {
  const cached = await getCachedMessage(folder, uid);
  if (!cached) return null;
  return toMessageFull(cached);
}

/**
 * Load cached folders for offline viewing.
 */
export async function loadOfflineFolders(): Promise<Folder[]> {
  const cached = await getCachedFolders();
  return cached.map(f => ({
    name: f.name,
    delimiter: '.',
    flags: [],
    type: f.name === 'INBOX' ? 'inbox' as const
      : f.name === 'Sent' ? 'sent' as const
      : f.name === 'Drafts' ? 'drafts' as const
      : f.name === 'Trash' ? 'trash' as const
      : f.name === 'Junk' ? 'junk' as const
      : 'folder' as const,
    unseen: f.unseen,
  }));
}
