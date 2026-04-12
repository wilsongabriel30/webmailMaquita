import { useState, useEffect, useCallback, useRef } from 'react';

interface AttachmentInfo {
  filename: string;
  content_type: string;
  size: number;
  part_number: string;
}

interface AttachmentPreviewProps {
  open: boolean;
  onClose: () => void;
  folder: string;
  uid: number;
  attachment: AttachmentInfo;
  allAttachments?: AttachmentInfo[];
  currentIndex?: number;
  onNavigate?: (index: number) => void;
}

function getPreviewType(ct: string, filename: string = ''): 'image' | 'pdf' | 'text' | 'office' | 'unsupported' {
  if (ct.startsWith('image/')) return 'image';
  if (ct === 'application/pdf') return 'pdf';
  if (ct.startsWith('text/')) return 'text';
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  const officeExts = new Set(['docx','doc','odt','rtf','xlsx','xls','ods','csv','pptx','ppt','odp']);
  if (officeExts.has(ext)) return 'office';
  const officeMimes = new Set([
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'application/msword', 'application/vnd.ms-excel', 'application/vnd.ms-powerpoint',
  ]);
  if (officeMimes.has(ct)) return 'office';
  return 'unsupported';
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

function buildUrl(folder: string, uid: number, partNumber: string, filename: string): string {
  return '/api/mail/attachment/' + encodeURIComponent(folder) + '/' + uid + '/' + partNumber + '/' + encodeURIComponent(filename);
}

export function AttachmentPreview({
  open, onClose, folder, uid, attachment, allAttachments, currentIndex, onNavigate,
}: AttachmentPreviewProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [textContent, setTextContent] = useState('');
  const modalRef = useRef<HTMLDivElement>(null);

  // Compute derived values safely (handle null attachment)
  const type = attachment ? getPreviewType(attachment.content_type, attachment.filename) : 'unsupported';
  const url = attachment ? buildUrl(folder, uid, attachment.part_number, attachment.filename) : '';
  const hasNav = allAttachments && allAttachments.length > 1 && onNavigate != null;
  const total = allAttachments?.length || 1;
  const idx = currentIndex ?? 0;

  useEffect(() => {
    if (!open || !attachment || type !== 'text') return;
    setLoading(true);
    setError(false);
    fetch(url, { credentials: 'include' })
      .then((r) => { if (!r.ok) throw new Error(); return r.text(); })
      .then((t) => { setTextContent(t); setLoading(false); })
      .catch(() => { setError(true); setLoading(false); });
  }, [open, url, type, attachment]);

  useEffect(() => {
    if (!attachment) return;
    if (type !== 'text' && type !== 'office') { setLoading(true); setError(false); }
  }, [attachment?.part_number, type]);

  // Convert Office files to PDF via OnlyOffice for preview
  const [officePdfUrl, setOfficePdfUrl] = useState('');
  useEffect(() => {
    if (!open || !attachment || type !== 'office') return;
    setLoading(true);
    setError(false);
    setOfficePdfUrl('');
    fetch('/api/mail/office-preview', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        folder,
        uid,
        part_number: attachment.part_number,
        filename: attachment.filename,
      }),
    })
      .then(r => { if (!r.ok) throw new Error('Conversion failed'); return r.arrayBuffer(); })
      .then(buf => {
        const blob = new Blob([buf], { type: 'application/pdf' });
        const pdfUrl = URL.createObjectURL(blob);
        setOfficePdfUrl(pdfUrl);
        setLoading(false);
      })
      .catch(() => { setError(true); setLoading(false); });
    return () => { if (officePdfUrl) URL.revokeObjectURL(officePdfUrl); };
  }, [open, attachment?.part_number, type, folder, uid]);

  const onKeyDown = useCallback((e: KeyboardEvent) => {
    if (!open || !attachment) return;
    if (e.key === 'Escape') { e.preventDefault(); onClose(); }
    if (e.key === 'ArrowLeft' && hasNav) { e.preventDefault(); onNavigate!((idx - 1 + total) % total); }
    if (e.key === 'ArrowRight' && hasNav) { e.preventDefault(); onNavigate!((idx + 1) % total); }
    if (e.key === 'd' || e.key === 'D') {
      if (document.activeElement?.tagName === 'INPUT' || document.activeElement?.tagName === 'TEXTAREA') return;
      e.preventDefault();
      const a = document.createElement('a');
      a.href = url; a.download = attachment.filename; document.body.appendChild(a); a.click(); a.remove();
    }
  }, [open, onClose, hasNav, onNavigate, idx, total, url, attachment]);

  useEffect(() => {
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onKeyDown]);

  useEffect(() => {
    if (open) modalRef.current?.focus();
  }, [open]);

  // Early returns AFTER all hooks (React rules of hooks)
  if (!attachment) return null;
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 dark:bg-black/70"
      onClick={onClose}
    >
      <div
        ref={modalRef}
        tabIndex={-1}
        className="bg-white dark:bg-[#2d2d2d] rounded-lg shadow-2xl w-[90vw] max-w-[900px] max-h-[90vh] flex flex-col overflow-hidden outline-none"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#edebe9] dark:border-[#444]">
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <svg className="w-5 h-5 flex-shrink-0 text-[#605e5c] dark:text-[#aaa]" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
            </svg>
            <span className="text-[14px] font-medium text-[#323130] dark:text-[#e0e0e0] truncate">
              {attachment.filename}
            </span>
            <span className="text-[12px] text-[#605e5c] dark:text-[#999] ml-2 flex-shrink-0">
              {formatSize(attachment.size)}
            </span>
          </div>
          <div className="flex items-center gap-2 ml-3">
            <a
              href={url}
              download={attachment.filename}
              className="flex items-center gap-1 px-3 py-1.5 text-[13px] text-[#0078d4] hover:bg-[#f3f2f1] dark:hover:bg-[#383838] rounded"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
              </svg>
              Descargar
            </a>
            <button
              onClick={onClose}
              className="p-1.5 hover:bg-[#f3f2f1] dark:hover:bg-[#383838] rounded text-[#605e5c] dark:text-[#aaa]"
              aria-label="Cerrar"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Preview area */}
        <div className="flex-1 overflow-auto flex items-center justify-center p-4 bg-[#faf9f8] dark:bg-[#1e1e1e] min-h-[300px]">
          {type === 'image' && (
            <>
              {loading && <div className="animate-spin rounded-full h-8 w-8 border-2 border-[#0078d4] border-t-transparent" />}
              <img
                src={url}
                alt={attachment.filename}
                className={'max-w-full max-h-[70vh] object-contain' + (loading ? ' hidden' : '')}
                onLoad={() => setLoading(false)}
                onError={() => { setError(true); setLoading(false); }}
              />
            </>
          )}
          {type === 'pdf' && (
            <iframe
              src={'/api/mail/preview/' + encodeURIComponent(folder) + '/' + uid + '/' + attachment.part_number + '/' + encodeURIComponent(attachment.filename)}
              className="w-full h-[70vh] border-0"
              title={attachment.filename}
              onLoad={() => setLoading(false)}
            />
          )}
          {type === 'office' && loading && (
            <div className="flex flex-col items-center gap-3">
              <div className="animate-spin rounded-full h-8 w-8 border-2 border-[#0078d4] border-t-transparent" />
              <p className="text-[13px] text-[#605e5c] dark:text-[#999]">Convirtiendo documento...</p>
            </div>
          )}
          {type === 'office' && !loading && !error && officePdfUrl && (
            <iframe
              src={officePdfUrl}
              className="w-full h-[70vh] border-0"
              title={attachment.filename}
            />
          )}
          {type === 'text' && !loading && !error && (
            <pre className="w-full h-[70vh] overflow-auto p-4 bg-[#faf9f8] dark:bg-[#1e1e1e] text-[13px] font-mono text-[#323130] dark:text-[#e0e0e0] whitespace-pre-wrap">
              {textContent}
            </pre>
          )}
          {type === 'text' && loading && (
            <div className="animate-spin rounded-full h-8 w-8 border-2 border-[#0078d4] border-t-transparent" />
          )}
          {type === 'unsupported' && (
            <div className="flex flex-col items-center justify-center h-[300px] gap-4">
              <svg className="w-16 h-16 text-[#a19f9d] dark:text-[#666]" fill="none" stroke="currentColor" strokeWidth={1} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
              </svg>
              <p className="text-[14px] text-[#605e5c] dark:text-[#999]">Vista previa no disponible para este tipo de archivo</p>
              <p className="text-[12px] text-[#a19f9d] dark:text-[#777]">{attachment.content_type} · {formatSize(attachment.size)}</p>
              <a
                href={url}
                download={attachment.filename}
                className="px-4 py-2 bg-[#0078d4] text-white rounded hover:bg-[#106ebe] text-[14px] font-medium"
              >
                Descargar archivo
              </a>
            </div>
          )}
          {error && type !== 'unsupported' && (
            <div className="flex flex-col items-center gap-3">
              <p className="text-[14px] text-[#a4262c] dark:text-[#f1707b]">Error al cargar la vista previa</p>
              <a href={url} download={attachment.filename} className="text-[#0078d4] text-[13px] hover:underline">
                Descargar en su lugar
              </a>
            </div>
          )}
        </div>

        {/* Navigation footer */}
        {hasNav && (
          <div className="flex items-center justify-center gap-4 px-4 py-2 border-t border-[#edebe9] dark:border-[#444]">
            <button
              onClick={() => onNavigate!((idx - 1 + total) % total)}
              className="px-3 py-1 text-[13px] text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#383838] rounded flex items-center gap-1"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
              </svg>
              Anterior
            </button>
            <span className="text-[13px] text-[#605e5c] dark:text-[#999]">{idx + 1} de {total}</span>
            <button
              onClick={() => onNavigate!((idx + 1) % total)}
              className="px-3 py-1 text-[13px] text-[#323130] dark:text-[#e0e0e0] hover:bg-[#f3f2f1] dark:hover:bg-[#383838] rounded flex items-center gap-1"
            >
              Siguiente
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
              </svg>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
