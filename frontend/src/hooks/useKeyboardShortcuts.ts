import { useEffect } from 'react';
import { useMailStore } from '../store/mailStore';
import { api } from '../api/client';
import type { MessageFull } from '../types';

function buildQuoteHtml(msg: MessageFull, type: 'reply' | 'forward'): string {
  const header = type === 'forward'
    ? '<p style="font-weight:600;margin:0 0 8px">--- Mensaje reenviado ---</p>'
    : '';
  return `<div style="border-top:1px solid #edebe9;padding-top:12px;margin-top:20px">
    ${header}
    <p style="font-size:12px;color:#605e5c;margin:0 0 8px">
      <b>De:</b> ${msg.from}<br>
      <b>Para:</b> ${msg.to}<br>
      ${msg.cc ? `<b>CC:</b> ${msg.cc}<br>` : ''}
      <b>Asunto:</b> ${msg.subject}
    </p>
    ${msg.html_body || `<pre style="white-space:pre-wrap;font-family:inherit">${msg.text_body || ''}</pre>`}
  </div>`;
}

export function useKeyboardShortcuts() {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const isInput = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable;
      const state = useMailStore.getState();

      // Escape always works
      if (e.key === 'Escape') {
        if (state.composeWindows.length > 0) {
          const last = state.composeWindows[state.composeWindows.length - 1];
          state.closeCompose(last.id);
        } else if (state.selectedUids.size > 0) {
          state.clearSelection();
        } else if (state.selectedMessage) {
          state.setSelectedMessage(null);
        }
        e.preventDefault();
        return;
      }

      if (isInput) return;

      const msgs = state.messages;
      const idx = state.activeIndex;
      const folder = state.currentFolder;

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          if (idx < msgs.length - 1) {
            const newIdx = idx + 1;
            state.setActiveIndex(newIdx);
            selectMessage(msgs[newIdx].uid, folder);
          }
          break;

        case 'ArrowUp':
          e.preventDefault();
          if (idx > 0) {
            const newIdx = idx - 1;
            state.setActiveIndex(newIdx);
            selectMessage(msgs[newIdx].uid, folder);
          }
          break;

        case 'Enter':
          e.preventDefault();
          if (idx >= 0 && idx < msgs.length) {
            selectMessage(msgs[idx].uid, folder);
          }
          break;

        case 'Delete':
          e.preventDefault();
          if (state.selectedUids.size > 0) {
            bulkAction(Array.from(state.selectedUids), folder === 'Trash' ? 'delete' : 'move', 'Trash', folder);
          } else if (state.selectedMessage) {
            bulkAction([state.selectedMessage.uid], folder === 'Trash' ? 'delete' : 'move', 'Trash', folder);
          }
          break;

        case 'a':
          if (e.ctrlKey || e.metaKey) {
            // Only select all messages if no message is open for reading
            if (!state.selectedMessage) {
              e.preventDefault();
              state.selectAll();
            }
            // Otherwise let browser handle Ctrl+A (select text in message view)
          }
          break;

        case 'n':
        case 'N':
          e.preventDefault();
          state.openCompose('new');
          break;

        case 'r':
          e.preventDefault();
          if (state.selectedMessage) {
            const msg = state.selectedMessage;
            const quoteHtml = buildQuoteHtml(msg, 'reply');
            state.openCompose('reply', {
              to: [msg.from],
              subject: msg.subject.startsWith('Re:') ? msg.subject : `Re: ${msg.subject}`,
              text_body: '',
              html_body: quoteHtml,
              in_reply_to: msg.message_id || '',
              references: msg.references || '',
            });
          }
          break;

        case 'R':
          e.preventDefault();
          if (state.selectedMessage) {
            const msg = state.selectedMessage;
            const quoteHtml = buildQuoteHtml(msg, 'reply');
            state.openCompose('replyAll', {
              to: [msg.from],
              cc: msg.cc ? msg.cc.split(',').map(s => s.trim()) : [],
              subject: msg.subject.startsWith('Re:') ? msg.subject : `Re: ${msg.subject}`,
              text_body: '',
              html_body: quoteHtml,
              in_reply_to: msg.message_id || '',
              references: msg.references || '',
            });
          }
          break;

        case 'f':
        case 'F':
          e.preventDefault();
          if (state.selectedMessage) {
            const msg = state.selectedMessage;
            const quoteHtml = buildQuoteHtml(msg, 'forward');
            state.openCompose('forward', {
              to: [],
              subject: msg.subject.startsWith('RV:') ? msg.subject : `RV: ${msg.subject}`,
              text_body: '',
              html_body: quoteHtml,
            });
          }
          break;

        case 'e':
          if (!e.ctrlKey && !e.metaKey) {
            e.preventDefault();
            if (state.selectedMessage) {
              bulkAction([state.selectedMessage.uid], 'archive', '', folder);
            }
          }
          // Let Ctrl+E pass through for browser use
          break;

        case '/':
          e.preventDefault();
          document.getElementById('search-input')?.focus();
          break;
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);
}

async function selectMessage(uid: number, folder: string) {
  const state = useMailStore.getState();
  state.setLoadingMessage(true);
  try {
    const msg = await api.get<MessageFull>(`/mail/message/${encodeURIComponent(folder)}/${uid}`);
    state.setSelectedMessage(msg);
    const updated = state.messages.map(m => m.uid === uid ? { ...m, seen: true, flags: m.flags.includes('\\Seen') ? m.flags : [...m.flags, '\\Seen'] } : m);
    state.setMessages(updated, state.totalMessages, state.currentPage);
  } catch {}
}

async function bulkAction(uids: number[], action: string, dest: string, folder: string) {
  try {
    await api.post(`/mail/bulk-action/${encodeURIComponent(folder)}`, { uids, action, dest_folder: dest });
    useMailStore.getState().setSelectedMessage(null);
    useMailStore.getState().clearSelection();
    window.dispatchEvent(new CustomEvent('refresh-messages'));
  } catch {}
}
