// @ts-nocheck
import React, { useState, useCallback } from 'react';
import { formatDistanceToNow, format } from 'date-fns';
import { es } from 'date-fns/locale';
import { api } from '../../api/client';
import { useMailStore } from '../../store/mailStore';

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

const AVATAR_COLORS = [
  '#0078d4', '#00b294', '#e74856', '#8764b8', '#ca5010',
  '#498205', '#005b70', '#8e562e', '#69797e', '#647c64',
];

function avatarColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

function avatarInitial(name: string): string {
  const clean = name.replace(/<.*>/, '').trim();
  return clean.charAt(0).toUpperCase() || '?';
}

function extractName(raw: string): string {
  const match = raw.match(/^"?([^"<]+)"?\s*</);
  if (match) return match[1].trim();
  return raw.replace(/<.*>/, '').trim() || raw;
}

function extractEmail(raw: string): string {
  const match = raw.match(/<([^>]+)>/);
  return match ? match[1] : raw.trim();
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/* ------------------------------------------------------------------ */
/*  Quote builder for Reply / Forward                                 */
/* ------------------------------------------------------------------ */

function buildQuoteHtml(
  from: string,
  date: string,
  to: string,
  cc: string,
  subject: string,
  htmlBody: string,
  isForward: boolean,
): string {
  const header = isForward
    ? '<p style="font-weight:bold;margin:0 0 8px">--- Mensaje reenviado ---</p>'
    : '';

  const ccLine = cc ? `<b>CC:</b> ${cc}<br>` : '';

  return `
<div style="border-top:1px solid #edebe9;padding-top:12px;margin-top:20px">
  ${header}
  <p style="font-size:12px;color:#605e5c;margin:0 0 8px">
    <b>De:</b> ${from}<br>
    <b>Enviado:</b> ${date}<br>
    <b>Para:</b> ${to}<br>
    ${ccLine}
    <b>Asunto:</b> ${subject}
  </p>
  ${htmlBody}
</div>`.trim();
}

/* ------------------------------------------------------------------ */
/*  Source modal                                                      */
/* ------------------------------------------------------------------ */

interface SourceModalProps {
  source: string;
  onClose: () => void;
}

const SourceModal: React.FC<SourceModalProps> = ({ source, onClose }) => {
  const preRef = React.useRef<HTMLPreElement>(null);
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
      e.preventDefault();
      e.stopPropagation();
      if (preRef.current) {
        const range = document.createRange();
        range.selectNodeContents(preRef.current);
        const sel = window.getSelection();
        sel?.removeAllRanges();
        sel?.addRange(range);
      }
    }
    e.stopPropagation();
  };
  return (
  <div
    style={{
      position: 'fixed',
      inset: 0,
      zIndex: 9999,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: 'rgba(0,0,0,0.5)',
      isolation: 'isolate',
    }}
    onClick={onClose}
    onKeyDown={handleKeyDown}
  >
    <div
      style={{
        background: '#fff',
        borderRadius: 8,
        width: '85vw',
        maxWidth: 960,
        height: '80vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 8px 32px rgba(0,0,0,0.25)',
      }}
      onClick={(e) => e.stopPropagation()}
      tabIndex={0}
      autoFocus
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 16px',
          borderBottom: '1px solid #edebe9',
        }}
      >
        <span style={{ fontWeight: 600, fontSize: 14 }}>Fuente del mensaje</span>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            fontSize: 18,
            cursor: 'pointer',
            color: '#605e5c',
            padding: '4px 8px',
            borderRadius: 4,
          }}
          title="Cerrar"
        >
          x
        </button>
      </div>
      <pre
        ref={preRef}
        style={{
          flex: 1,
          margin: 0,
          padding: 16,
          overflow: 'auto',
          fontSize: 12,
          fontFamily: 'Consolas, "Courier New", monospace',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-all',
          background: '#faf9f8',
          userSelect: 'text',
        }}
      >
        {source}
      </pre>
    </div>
  </div>
  );
};

/* ------------------------------------------------------------------ */
/*  ThreadMessageCard — a single message in the thread view           */
/* ------------------------------------------------------------------ */

interface ThreadMessageCardProps {
  msg: any;
  isExpanded: boolean;
  onToggle: () => void;
  isLast: boolean;
  currentFolder: string;
  openCompose: any;
}

const ThreadMessageCard: React.FC<ThreadMessageCardProps> = ({
  msg, isExpanded, onToggle, isLast, currentFolder, openCompose,
}) => {
  const senderName = extractName(msg.from);
  const senderEmail = extractEmail(msg.from);
  const bgColor = avatarColor(senderName);
  const initial = avatarInitial(senderName);
  const relDate = msg.date ? formatDistanceToNow(new Date(msg.date), { addSuffix: true, locale: es }) : '';
  const fullDate = msg.date ? format(new Date(msg.date), "EEEE, d 'de' MMMM 'de' yyyy, HH:mm", { locale: es }) : '';

  // First line of text for collapsed view
  const snippet = msg.text_body
    ? msg.text_body.substring(0, 120).replace(/\n/g, ' ').trim()
    : msg.snippet || '';

  if (!isExpanded) {
    return (
      <div
        onClick={onToggle}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '8px 16px',
          cursor: 'pointer',
          borderBottom: '1px solid #f3f2f1',
          background: '#faf9f8',
          transition: 'background 0.15s',
        }}
        onMouseOver={(e) => { (e.currentTarget as HTMLDivElement).style.background = '#f3f2f1'; }}
        onMouseOut={(e) => { (e.currentTarget as HTMLDivElement).style.background = '#faf9f8'; }}
      >
        {/* Mini avatar */}
        <div style={{
          width: 28, height: 28, borderRadius: '50%', background: bgColor,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#fff', fontWeight: 600, fontSize: 12, flexShrink: 0,
        }}>
          {initial}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontWeight: 600, fontSize: 13, color: '#323130' }}>{senderName}</span>
            <span style={{ fontSize: 11, color: '#a19f9d', marginLeft: 'auto', whiteSpace: 'nowrap' }} title={fullDate}>
              {relDate}
            </span>
          </div>
          <p style={{
            fontSize: 12, color: '#605e5c', margin: 0, overflow: 'hidden',
            textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {snippet || '\u00A0'}
          </p>
        </div>
        <svg style={{ width: 16, height: 16, color: '#a19f9d', flexShrink: 0 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </div>
    );
  }

  // Expanded view - full message
  return (
    <div style={{
      borderBottom: '1px solid #edebe9',
      background: '#fff',
    }}>
      {/* Header */}
      <div
        onClick={onToggle}
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 12,
          padding: '14px 16px 8px',
          cursor: 'pointer',
        }}
      >
        <div style={{
          width: 36, height: 36, borderRadius: '50%', background: bgColor,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#fff', fontWeight: 600, fontSize: 14, flexShrink: 0,
        }}>
          {initial}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 600, fontSize: 14, color: '#323130' }}>{senderName}</span>
            <span style={{ fontSize: 12, color: '#605e5c' }}>&lt;{senderEmail}&gt;</span>
            <span style={{ fontSize: 12, color: '#a19f9d', marginLeft: 'auto', whiteSpace: 'nowrap' }} title={fullDate}>
              {relDate}
            </span>
          </div>
          <div style={{ fontSize: 12, color: '#605e5c', marginTop: 2 }}>
            Para: {msg.to}
            {msg.cc && <span> | CC: {msg.cc}</span>}
          </div>
        </div>
        <svg style={{ width: 16, height: 16, color: '#a19f9d', flexShrink: 0, marginTop: 4 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
        </svg>
      </div>

      {/* Attachments */}
      {msg.has_attachments && msg.attachments && msg.attachments.length > 0 && (
        <div style={{ padding: '4px 16px 8px', display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {msg.attachments.map((att: any, i: number) => (
            <a
              key={i}
              href={`/api/mail/attachment/${encodeURIComponent(msg.folder || currentFolder)}/${msg.uid}/${encodeURIComponent(att.filename)}`}
              download={att.filename}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 4,
                padding: '4px 8px', border: '1px solid #d2d0ce', borderRadius: 4,
                textDecoration: 'none', color: '#323130', fontSize: 11,
                background: '#faf9f8',
              }}
              title={`${att.filename} (${formatSize(att.size)})`}
            >
              <svg width="12" height="12" viewBox="0 0 16 16" fill="#605e5c">
                <path d="M14 4.5V14a2 2 0 01-2 2H4a2 2 0 01-2-2V2a2 2 0 012-2h5.5L14 4.5zM9.5 1H4a1 1 0 00-1 1v12a1 1 0 001 1h8a1 1 0 001-1V5h-3.5V1z"/>
              </svg>
              <span style={{ maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {att.filename}
              </span>
            </a>
          ))}
        </div>
      )}

      {/* Body */}
      <div style={{ padding: '0 16px 14px' }}>
        {msg.html_body ? (
          <div
            className="message-html-body"
            style={{ fontSize: 14, lineHeight: 1.6, color: '#323130', wordBreak: 'break-word' }}
            dangerouslySetInnerHTML={{ __html: '<style>.message-html-body a { color: #0078d4 !important; text-decoration: underline !important; cursor: pointer !important; }</style>' + msg.html_body }}
          />
        ) : (
          <pre style={{
            margin: 0, fontSize: 14, lineHeight: 1.6, color: '#323130',
            whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'inherit',
          }}>
            {msg.text_body}
          </pre>
        )}
      </div>
    </div>
  );
};

/* ------------------------------------------------------------------ */
/*  MessageView                                                       */
/* ------------------------------------------------------------------ */

const MessageView: React.FC = () => {
  const {
    selectedMessage: msg, loadingMessage, currentFolder, openCompose,
    threadMessages, threadExpanded, toggleThreadExpand, loadingThread, viewMode,
  } = useMailStore();

  const [showDetails, setShowDetails] = useState(false);
  const [loadingImages, setLoadingImages] = useState(false);
  const [imageMsg, setImageMsg] = useState<typeof msg>(null);
  const [sourceText, setSourceText] = useState<string | null>(null);
  const [loadingSource, setLoadingSource] = useState(false);
  const [recallStatus, setRecallStatus] = React.useState<'idle'|'checking'|'recalling'|'done'|'error'>('idle');
  const [recallInfo, setRecallInfo] = React.useState<{can_recall:boolean,was_read:boolean|null,recipient:string}[]>([]);

  const displayMsg = imageMsg?.uid === msg?.uid ? imageMsg : msg;

  const isThreadView = viewMode === 'conversations' && threadMessages.length > 1;

  /* ---- Actions ---- */

  const handleLoadImages = useCallback(async () => {
    if (!msg) return;
    setLoadingImages(true);
    try {
      const data = await api.get<typeof msg>(
        `/mail/message/${encodeURIComponent(currentFolder)}/${msg.uid}?load_images=true`,
      );
      setImageMsg(data);
    } catch (err) {
      console.error('Error loading images:', err);
    } finally {
      setLoadingImages(false);
    }
  }, [msg, currentFolder]);

  const handleDownloadEml = useCallback(async () => {
    if (!msg) return;
    try {
      const res = await fetch(`/api/mail/message/${encodeURIComponent(currentFolder)}/${msg.uid}/eml`, {
        credentials: 'include',
      });
      if (!res.ok) throw new Error('Download failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${msg.subject || 'message'}.eml`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Error downloading .eml:', err);
    }
  }, [msg]);

  const handleViewSource = useCallback(async () => {
    if (!msg) return;
    setLoadingSource(true);
    try {
      const data = await api.get<{ source: string }>(
        `/mail/message/${encodeURIComponent(currentFolder)}/${msg.uid}/source`,
      );
      setSourceText(data.source || '');
    } catch (err) {
      console.error('Error loading source:', err);
    } finally {
      setLoadingSource(false);
    }
  }, [msg]);

  const handlePrint = useCallback(() => {
    if (!displayMsg) return;
    const printWindow = window.open('', '_blank');
    if (!printWindow) return;
    const formattedDate = displayMsg.date ? format(new Date(displayMsg.date), "d 'de' MMMM 'de' yyyy, HH:mm", { locale: es }) : '';
    const body = displayMsg.html_body || `<pre style="white-space:pre-wrap;font-family:inherit">${displayMsg.text_body}</pre>`;
    printWindow.document.write(`<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>${displayMsg.subject}</title>
<style>body{font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;max-width:800px;margin:24px auto;color:#323130;font-size:14px}.header{border-bottom:1px solid #edebe9;padding-bottom:16px;margin-bottom:16px}.subject{font-size:20px;font-weight:600;margin:0 0 12px}.meta{font-size:12px;color:#605e5c;line-height:1.6}.body-content img{max-width:100%}@media print{body{margin:0}}</style>
</head><body><div class="header"><h1 class="subject">${displayMsg.subject}</h1><div class="meta"><b>De:</b> ${displayMsg.from}<br><b>Para:</b> ${displayMsg.to}<br>${displayMsg.cc ? `<b>CC:</b> ${displayMsg.cc}<br>` : ''}<b>Fecha:</b> ${formattedDate}<br></div></div><div class="body-content">${body}</div><script>window.onload=function(){window.print();}</script></body></html>`);
    printWindow.document.close();
  }, [displayMsg]);

  const handleReply = useCallback(() => {
    if (!msg || !openCompose) return;
    const formattedDate = msg.date ? format(new Date(msg.date), "d 'de' MMMM 'de' yyyy, HH:mm", { locale: es }) : '';
    const quoteHtml = buildQuoteHtml(
      msg.from, formattedDate, msg.to, msg.cc, msg.subject,
      msg.html_body || `<pre style="white-space:pre-wrap">${msg.text_body}</pre>`,
      false,
    );
    openCompose('reply', {
      to: [extractEmail(msg.from)],
      subject: msg.subject.startsWith('Re:') ? msg.subject : `Re: ${msg.subject}`,
      text_body: '',
      in_reply_to: msg.message_id || '',
      references: msg.references ? `${msg.references} ${msg.message_id}` : (msg.message_id || ''),
      html_body: quoteHtml,
    });
  }, [msg, openCompose]);

  const handleReplyAll = useCallback(() => {
    if (!msg || !openCompose) return;
    const formattedDate = msg.date ? format(new Date(msg.date), "d 'de' MMMM 'de' yyyy, HH:mm", { locale: es }) : '';
    const quoteHtml = buildQuoteHtml(
      msg.from, formattedDate, msg.to, msg.cc, msg.subject,
      msg.html_body || `<pre style="white-space:pre-wrap">${msg.text_body}</pre>`,
      false,
    );
    openCompose('replyAll', {
      to: [extractEmail(msg.from)],
      cc: [msg.to, msg.cc].filter(Boolean).join(', ').split(',').map(s => s.trim()).filter(Boolean),
      subject: msg.subject.startsWith('Re:') ? msg.subject : `Re: ${msg.subject}`,
      text_body: '',
      in_reply_to: msg.message_id || '',
      references: msg.references ? `${msg.references} ${msg.message_id}` : (msg.message_id || ''),
      html_body: quoteHtml,
    });
  }, [msg, openCompose]);

  const handleForward = useCallback(() => {
    if (!msg || !openCompose) return;
    const formattedDate = msg.date ? format(new Date(msg.date), "d 'de' MMMM 'de' yyyy, HH:mm", { locale: es }) : '';
    const quoteHtml = buildQuoteHtml(
      msg.from, formattedDate, msg.to, msg.cc, msg.subject,
      msg.html_body || `<pre style="white-space:pre-wrap">${msg.text_body}</pre>`,
      true,
    );
    openCompose('forward', {
      to: [],
      subject: msg.subject.startsWith('Fwd:') ? msg.subject : `Fwd: ${msg.subject}`,
      text_body: '',
      in_reply_to: msg.message_id || '',
      references: msg.references ? `${msg.references} ${msg.message_id}` : (msg.message_id || ''),
      html_body: quoteHtml,
    });
  }, [msg, openCompose]);

  const handleRecallCheck = React.useCallback(async () => {
    if (!msg || !msg.to) return;
    setRecallStatus('checking');
    try {
      const recipients = msg.to.split(',').map((s: string) => s.trim()).filter(Boolean);
      if (msg.cc) recipients.push(...msg.cc.split(',').map((s: string) => s.trim()).filter(Boolean));
      const res = await api.post<{checks: any[]}>('/mail/recall/check', {
        message_id: msg.message_id, recipients, action: 'delete',
      });
      setRecallInfo(res.checks || []);
      setRecallStatus('idle');
    } catch { setRecallStatus('error'); }
  }, [msg]);

  const handleRecall = React.useCallback(async () => {
    if (!msg) return;
    setRecallStatus('recalling');
    try {
      const recipients = msg.to.split(',').map((s: string) => s.trim()).filter(Boolean);
      if (msg.cc) recipients.push(...msg.cc.split(',').map((s: string) => s.trim()).filter(Boolean));
      const res = await api.post<{results: any[], message: string}>('/mail/recall', {
        message_id: msg.message_id, recipients, action: 'delete',
      });
      setRecallStatus('done');
      setRecallInfo(res.results?.map((r: any) => ({can_recall: r.status === 'recalled', was_read: null, recipient: r.recipient, detail: r.detail, status: r.status})) || []);
    } catch { setRecallStatus('error'); }
  }, [msg]);

  /* ---- Loading state ---- */

  if (loadingMessage) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#605e5c' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{
            width: 32, height: 32, border: '3px solid #edebe9', borderTop: '3px solid #0078d4',
            borderRadius: '50%', animation: 'spin 0.8s linear infinite', margin: '0 auto 12px',
          }} />
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          <span style={{ fontSize: 13 }}>Cargando mensaje...</span>
        </div>
      </div>
    );
  }

  if (!msg) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#a19f9d' }}>
        <div style={{ textAlign: 'center' }}>
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none" style={{ marginBottom: 12, opacity: 0.5 }}>
            <path d="M6 12l18 12 18-12" stroke="#a19f9d" strokeWidth="2" fill="none"/>
            <rect x="4" y="10" width="40" height="28" rx="3" stroke="#a19f9d" strokeWidth="2" fill="none"/>
          </svg>
          <p style={{ fontSize: 14, margin: 0 }}>Selecciona un mensaje para leerlo</p>
        </div>
      </div>
    );
  }

  /* ---- Thread View ---- */
  if (isThreadView) {
    const subject = msg.subject.replace(/^(Re|Fwd|Fw):\s*/i, '');
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#fff' }}>
        {sourceText !== null && (
          <SourceModal source={sourceText} onClose={() => setSourceText(null)} />
        )}

        {/* Thread header */}
        <div style={{ padding: '16px 20px 12px', borderBottom: '1px solid #edebe9', flexShrink: 0 }}>
          <h2 style={{ fontSize: 20, fontWeight: 600, margin: '0 0 6px', color: '#323130', lineHeight: 1.3 }}>
            {subject}
          </h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <svg style={{ width: 16, height: 16, color: '#0078d4' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
            </svg>
            <span style={{ fontSize: 13, color: '#605e5c' }}>
              {threadMessages.length} mensajes en esta conversacion
            </span>
          </div>
        </div>

        {/* Thread loading */}
        {loadingThread && (
          <div style={{ padding: '12px 20px', textAlign: 'center', color: '#605e5c', fontSize: 13 }}>
            Cargando conversacion...
          </div>
        )}

        {/* Thread messages */}
        <div style={{ flex: 1, overflow: 'auto' }}>
          {/* Visual connector line */}
          <div style={{ position: 'relative' }}>
            {/* Vertical thread line */}
            <div style={{
              position: 'absolute',
              left: 33,
              top: 20,
              bottom: 20,
              width: 2,
              background: '#e1dfdd',
              zIndex: 0,
            }} />

            {threadMessages.map((threadMsg, idx) => {
              const isLast = idx === threadMessages.length - 1;
              const isExp = threadExpanded.has(threadMsg.uid);
              return (
                <div key={threadMsg.uid} style={{ position: 'relative', zIndex: 1 }}>
                  <ThreadMessageCard
                    msg={threadMsg}
                    isExpanded={isExp}
                    onToggle={() => toggleThreadExpand(threadMsg.uid)}
                    isLast={isLast}
                    currentFolder={currentFolder}
                    openCompose={openCompose}
                  />
                </div>
              );
            })}
          </div>
        </div>

        {/* Bottom reply bar */}
        <div style={{
          padding: '12px 24px', borderTop: '1px solid #edebe9', flexShrink: 0,
          display: 'flex', gap: 4, background: '#faf9f8',
        }}>
          <button style={actionBtnStyle} onClick={handleReply}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" style={{ marginRight: 2 }}>
              <path d="M6.5 3L1 8l5.5 5V10c4.5 0 7 1.5 8.5 5-1-4.5-3.5-8-8.5-8.5V3z"/>
            </svg>
            Responder
          </button>
          <button style={actionBtnStyle} onClick={handleReplyAll}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" style={{ marginRight: 2 }}>
              <path d="M9.5 3L4 8l5.5 5V10c4.5 0 6 1.5 7.5 5-1-4.5-3-8-7.5-8.5V3zM3 8L0 5.5v5L3 8z"/>
            </svg>
            Responder a todos
          </button>
          <button style={actionBtnStyle} onClick={handleForward}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" style={{ marginRight: 2 }}>
              <path d="M9.5 3L15 8l-5.5 5V10C5 10 2.5 11.5 1 15c1-4.5 3.5-8 8.5-8.5V3z"/>
            </svg>
            Reenviar
          </button>
        </div>
      </div>
    );
  }

  /* ---- Single Message View (original) ---- */

  const senderName = extractName(msg.from);
  const senderEmail = extractEmail(msg.from);
  const bgColor = avatarColor(senderName);
  const initial = avatarInitial(senderName);

  const relDate = msg.date ? formatDistanceToNow(new Date(msg.date), { addSuffix: true, locale: es }) : '';
  const fullDate = msg.date ? format(new Date(msg.date), "EEEE, d 'de' MMMM 'de' yyyy, HH:mm", { locale: es }) : '';

  const showBlockedBanner =
    displayMsg!.has_remote_images && displayMsg!.blocked_image_count > 0 && (!imageMsg || imageMsg.uid !== msg.uid);

  const btnStyle: React.CSSProperties = {
    background: 'none',
    border: '1px solid #d2d0ce',
    borderRadius: 4,
    padding: '5px 12px',
    fontSize: 12,
    color: '#323130',
    cursor: 'pointer',
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#fff' }}>
      {sourceText !== null && (
        <SourceModal source={sourceText} onClose={() => setSourceText(null)} />
      )}

      {/* Header */}
      <div style={{ padding: '20px 24px 0', flexShrink: 0 }}>
        <h2 style={{ fontSize: 20, fontWeight: 600, margin: '0 0 16px', color: '#323130', lineHeight: 1.3 }}>
          {msg.subject}
          {msg.importance && msg.importance.toLowerCase() === 'high' && (
            <span style={{
              display: 'inline-block', marginLeft: 8, fontSize: 11, fontWeight: 600,
              background: '#fde7e9', color: '#a80000', padding: '2px 8px', borderRadius: 3,
              verticalAlign: 'middle',
            }}>
              Importancia alta
            </span>
          )}
        </h2>

        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
          <div style={{
            width: 40, height: 40, borderRadius: '50%', background: bgColor,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#fff', fontWeight: 600, fontSize: 16, flexShrink: 0,
          }}>
            {initial}
          </div>

          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
              <span style={{ fontWeight: 600, fontSize: 14, color: '#323130' }}>{senderName}</span>
              <span style={{ fontSize: 12, color: '#605e5c' }}>&lt;{senderEmail}&gt;</span>
              <span style={{ fontSize: 12, color: '#a19f9d', marginLeft: 'auto', whiteSpace: 'nowrap' }} title={fullDate}>
                {relDate}
              </span>
            </div>
            <div style={{ fontSize: 12, color: '#605e5c', marginTop: 2 }}>
              Para: {msg.to}
            </div>

            <button
              onClick={() => setShowDetails((v) => !v)}
              style={{
                background: 'none', border: 'none', padding: 0, marginTop: 4,
                fontSize: 12, color: '#0078d4', cursor: 'pointer',
              }}
            >
              {showDetails ? 'Menos' : 'Mas'}
            </button>

            {showDetails && (
              <div style={{
                marginTop: 8, padding: 12, background: '#faf9f8', borderRadius: 4,
                fontSize: 12, lineHeight: 1.8, color: '#323130',
              }}>
                <div><b>De:</b> {msg.from}</div>
                <div><b>Para:</b> {msg.to}</div>
                {msg.cc && <div><b>CC:</b> {msg.cc}</div>}
                <div><b>Fecha:</b> {fullDate}</div>
                {msg.message_id && <div><b>ID:</b> <span style={{ wordBreak: 'break-all' }}>{msg.message_id}</span></div>}
                {msg.importance && msg.importance.toLowerCase() !== 'normal' && (
                  <div><b>Prioridad:</b> {msg.importance}</div>
                )}
                {msg.size > 0 && <div><b>Tamano:</b> {formatSize(msg.size)}</div>}
              </div>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
          <button style={btnStyle} onClick={handleDownloadEml} title="Descargar como .eml">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
              <path d="M8 1v9.5M8 10.5l-3-3M8 10.5l3-3M2 12v2h12v-2"/>
            </svg>
            Descargar .eml
          </button>
          <button style={btnStyle} onClick={handleViewSource} disabled={loadingSource} title="Ver fuente del mensaje">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
              <path d="M5.5 4L1.5 8l4 4M10.5 4l4 4-4 4"/>
            </svg>
            {loadingSource ? 'Cargando...' : 'Ver fuente'}
          </button>
          <button style={btnStyle} onClick={handlePrint} title="Imprimir">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
              <path d="M4 1h8v3H4zM2 5h12v7H4v3h8v-3h2V5zM4 10h8"/>
            </svg>
            Imprimir
          </button>
        </div>

        {showBlockedBanner && (
          <div style={{
            marginTop: 12, padding: '8px 12px', background: '#fff4ce', borderRadius: 4,
            display: 'flex', alignItems: 'center', gap: 10, fontSize: 13, color: '#323130',
          }}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="#797775">
              <path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 10.5a.75.75 0 110-1.5.75.75 0 010 1.5zM8.75 4v5h-1.5V4h1.5z"/>
            </svg>
            <span>
              Se bloquearon {displayMsg!.blocked_image_count} imagen{displayMsg!.blocked_image_count > 1 ? 'es' : ''} remota{displayMsg!.blocked_image_count > 1 ? 's' : ''} por seguridad.
            </span>
            <button
              onClick={handleLoadImages}
              disabled={loadingImages}
              style={{
                background: '#0078d4', color: '#fff', border: 'none', borderRadius: 4,
                padding: '4px 12px', fontSize: 12, cursor: loadingImages ? 'default' : 'pointer',
                fontWeight: 600, marginLeft: 'auto', opacity: loadingImages ? 0.6 : 1,
              }}
            >
              {loadingImages ? 'Cargando...' : 'Cargar imagenes'}
            </button>
          </div>
        )}

        <div style={{ borderBottom: '1px solid #edebe9', marginTop: 16 }} />
      </div>

      {/* Attachments */}
      {msg.has_attachments && msg.attachments && msg.attachments.length > 0 && (
        <div style={{ padding: '10px 24px', borderBottom: '1px solid #edebe9', flexShrink: 0 }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {msg.attachments.map((att, i) => (
              <a
                key={i}
                href={`/api/mail/attachment/${encodeURIComponent(msg.folder)}/${msg.uid}/${encodeURIComponent(att.filename)}`}
                download={att.filename}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 6,
                  padding: '6px 10px', border: '1px solid #d2d0ce', borderRadius: 4,
                  textDecoration: 'none', color: '#323130', fontSize: 12,
                  background: '#faf9f8',
                }}
                title={`${att.filename} (${formatSize(att.size)})`}
              >
                <svg width="14" height="14" viewBox="0 0 16 16" fill="#605e5c">
                  <path d="M14 4.5V14a2 2 0 01-2 2H4a2 2 0 01-2-2V2a2 2 0 012-2h5.5L14 4.5zM9.5 1H4a1 1 0 00-1 1v12a1 1 0 001 1h8a1 1 0 001-1V5h-3.5V1z"/>
                </svg>
                <span style={{ maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {att.filename}
                </span>
                <span style={{ color: '#a19f9d' }}>({formatSize(att.size)})</span>
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Body */}
      <div style={{ flex: 1, overflow: 'auto', padding: '16px 24px' }}>
        {displayMsg!.html_body ? (
          <div
            className="message-html-body"
            style={{ fontSize: 14, lineHeight: 1.6, color: '#323130', wordBreak: 'break-word' }}
            dangerouslySetInnerHTML={{ __html: '<style>.message-html-body a { color: #0078d4 !important; text-decoration: underline !important; cursor: pointer !important; } .message-html-body a:hover { color: #106ebe !important; text-decoration: underline !important; }</style>' + displayMsg!.html_body }}
          />
        ) : (
          <pre style={{
            margin: 0, fontSize: 14, lineHeight: 1.6, color: '#323130',
            whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'inherit',
          }}>
            {displayMsg!.text_body}
          </pre>
        )}
      </div>

      {/* Bottom reply bar */}
      <div style={{
        padding: '12px 24px', borderTop: '1px solid #edebe9', flexShrink: 0,
        display: 'flex', gap: 4, background: '#faf9f8',
      }}>
        <button style={actionBtnStyle} onClick={handleReply}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" style={{ marginRight: 2 }}>
            <path d="M6.5 3L1 8l5.5 5V10c4.5 0 7 1.5 8.5 5-1-4.5-3.5-8-8.5-8.5V3z"/>
          </svg>
          Responder
        </button>
        <button style={actionBtnStyle} onClick={handleReplyAll}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" style={{ marginRight: 2 }}>
            <path d="M9.5 3L4 8l5.5 5V10c4.5 0 6 1.5 7.5 5-1-4.5-3-8-7.5-8.5V3zM3 8L0 5.5v5L3 8z"/>
          </svg>
          Responder a todos
        </button>
        <button style={actionBtnStyle} onClick={handleForward}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" style={{ marginRight: 2 }}>
            <path d="M9.5 3L15 8l-5.5 5V10C5 10 2.5 11.5 1 15c1-4.5 3.5-8 8.5-8.5V3z"/>
          </svg>
          Reenviar
        </button>
        {currentFolder === 'Sent' && (
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
            {recallStatus === 'done' ? (
              <span style={{ fontSize: 12, color: '#107c10', fontWeight: 600 }}>Mensaje recuperado exitosamente</span>
            ) : recallStatus === 'error' ? (
              <span style={{ fontSize: 12, color: '#d13438' }}>Error al recuperar</span>
            ) : recallInfo.length > 0 ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ fontSize: 11, color: '#605e5c' }}>
                  {recallInfo.map((r: any, i: number) => (
                    <div key={i}>
                      {r.recipient}: {r.can_recall ? (r.was_read ? 'Ya leido' : 'Recuperable') : (r.reason || 'No disponible')}
                    </div>
                  ))}
                </div>
                {recallInfo.some((r: any) => r.can_recall) && (
                  <button onClick={handleRecall} disabled={recallStatus === 'recalling'}
                    style={{ padding: '5px 14px', background: '#d13438', color: 'white', border: 'none', borderRadius: 4, fontSize: 12, cursor: 'pointer', fontWeight: 600 }}>
                    {recallStatus === 'recalling' ? 'Recuperando...' : 'Confirmar recuperacion'}
                  </button>
                )}
              </div>
            ) : (
              <button onClick={handleRecallCheck} disabled={recallStatus === 'checking'}
                style={{ padding: '5px 14px', background: '#ca5010', color: 'white', border: 'none', borderRadius: 4, fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4, fontWeight: 600 }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
                </svg>
                {recallStatus === 'checking' ? 'Verificando...' : 'Recuperar mensaje'}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

/* ---- Shared button style ---- */
const actionBtnStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  color: '#0078d4',
  fontWeight: 600,
  padding: '8px 16px',
  fontSize: 13,
  cursor: 'pointer',
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  borderRadius: 4,
};

export { MessageView };
