// @ts-nocheck  Ribbon callbacks temporarily unused (rendered in main Toolbar)
import { addToOutbox } from "../../lib/offlineStore";
import { SelectorArchivosNube } from './SelectorArchivosNube';
import { sanitizeHtml, sanitizeSignatureHtml } from '../../lib/sanitize';
import { useState, useEffect, useRef, useCallback } from 'react';
import React from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import Link from '@tiptap/extension-link';
import Image from '@tiptap/extension-image';
import { Table } from '@tiptap/extension-table';
import { TableRow } from '@tiptap/extension-table-row';
import { TableCell } from '@tiptap/extension-table-cell';
import { TableHeader } from '@tiptap/extension-table-header';
import { Subscript } from '@tiptap/extension-subscript';
import { Superscript } from '@tiptap/extension-superscript';
import Placeholder from '@tiptap/extension-placeholder';
import { VoiceDictation } from './VoiceDictation';
import TextAlign from '@tiptap/extension-text-align';
import { TextStyle } from '@tiptap/extension-text-style';
import { Color } from '@tiptap/extension-color';
import FontFamily from '@tiptap/extension-font-family';
import { FontSize } from './FontSize';
import { Highlight } from './Highlight';

import { useMailStore, type DraftWindow } from '../../store/mailStore';
import { api } from '../../api/client';
import { showToast, updateToast, dismissToast } from '../common/Toast';
import { RecipientField } from './RecipientField';
import { Attachments } from './Attachments';
import { DirectoryPanel } from '../contacts/DirectoryPanel';

// Module-level pending send map (persists after compose unmounts)
interface PendingSend { timerId: ReturnType<typeof setTimeout>; toastId: string; intervalId: ReturnType<typeof setInterval>; }
let pendingSendMap: Map<string, PendingSend> = new Map();

interface Props { win: DraftWindow; }

interface AttachmentFile { name: string; size: number; type: string; file?: File; }
// Limite de adjuntos (fuente unica: MAX_ATTACHMENT_MB -> VITE en build)
const MAX_ATTACH_MB = Number((import.meta as any).env?.VITE_MAX_ATTACHMENT_MB) || 25;
const totalAttachBytes = (atts: AttachmentFile[]) => atts.reduce((sum, a) => sum + (a.size || 0), 0);

export function ComposePanel({ win }: Props) {
  const closeCompose = useMailStore(s => s.closeCompose);
  const minimizeCompose = useMailStore(s => s.minimizeCompose);
  const updateDraftUid = useMailStore(s => s.updateDraftUid);
  const updateComposeData = useMailStore(s => s.updateComposeData);
  const [to, setTo] = useState('');
  const [cc, setCc] = useState('');
  const [bcc, setBcc] = useState('');
  const [subject, setSubject] = useState('');
  const [showCc, setShowCc] = useState(false);
  const [showBcc, setShowBcc] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [importance, setImportance] = useState<'normal' | 'high' | 'low'>('normal');
  const [attachments, setAttachments] = useState<AttachmentFile[]>([]);
  const [mostrarNube, setMostrarNube] = useState(false);

  // Adjuntos provenientes de la sección Archivos (Almacén): se descargan con
  // la misma sesión y entran como adjuntos normales del mensaje.
  useEffect(() => {
    const pendientes = win.data?.adjuntos_almacen;
    if (!pendientes?.length) return;
    (async () => {
      for (const pendiente of pendientes) {
        try {
          const res = await fetch(`/api/almacen/archivos/descargar?ruta=${encodeURIComponent(pendiente.ruta)}`, { credentials: 'include' });
          if (!res.ok) throw new Error();
          const blob = await res.blob();
          if (blob.size > 25 * 1024 * 1024) {
            showToast(`"${pendiente.nombre}" supera 25 MB — compártelo comprimido`);
            continue;
          }
          const file = new File([blob], pendiente.nombre, { type: blob.type || 'application/octet-stream' });
          setAttachments(prev => [...prev, { name: file.name, size: file.size, type: file.type, file }]);
        } catch {
          showToast(`No se pudo adjuntar "${pendiente.nombre}"`);
        }
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [isDragging, setIsDragging] = useState(false);
  const dragCounter = useRef(0);
  const [trackingState, setTrackingState] = useState({ delivery: false, read: false, noReactions: false });
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [showDirectoryPicker, setShowDirectoryPicker] = useState(false);
  const [directoryPickerTarget, setDirectoryPickerTarget] = useState<'to' | 'cc' | 'bcc'>('to');
  const [signatureHtml, setSignatureHtml] = useState('');
  const [quotedHtml, setQuotedHtml] = useState('');  // Contenido citado (reply/forward) — se renderiza DESPUES de la firma
  const [showSendDropdown, setShowSendDropdown] = useState(false);
  const [encrypt, setEncrypt] = useState(false);
  const [secureEnabled, setSecureEnabled] = useState(false);
  useEffect(() => { api.get('/mail/secure/config').then((r: any) => setSecureEnabled(!!(r && r.enabled))).catch(() => {}); }, []);
  const sendDropdownRef = useRef<HTMLDivElement>(null);
  const [scheduleDate, setScheduleDate] = useState('');
  const autosaveTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const initializedRef = useRef(false);

  // FQA-006: Refs to capture latest values for auto-save (avoids stale closures with React batching)
  const subjectRef = useRef(subject);
  const toRef = useRef(to);
  useEffect(() => { subjectRef.current = subject; }, [subject]);
  useEffect(() => { toRef.current = to; }, [to]);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({ heading: { levels: [1, 2, 3] }, link: false, underline: false }),
      Underline, Link.configure({ openOnClick: false }),
      Image.configure({ inline: true, allowBase64: true }),
      Table.configure({ resizable: true }),
      TableRow,
      TableCell,
      TableHeader,
      Subscript,
      Superscript,
      Placeholder.configure({ placeholder: '' }),
      TextAlign.configure({ types: ['heading', 'paragraph'] }),
      TextStyle, Color, FontFamily, FontSize, Highlight,
    ],
    content: '',
    editorProps: {
      attributes: {
        class: 'outline-none px-6 py-2 text-[14px] leading-[22px] text-[#323130]',
        style: 'font-family: Calibri, Segoe UI, sans-serif;',
      },
    },
  });

  // Helper: full HTML = editor body + signature (for send/drafts)
  // Orden al enviar: texto del usuario + firma + contenido citado
  // Bug 2026-04-10: firma aparecia despues del quote, debe ir antes
  // Fix #5 (2026-06-19): TipTap serializa <table>/<td> sin estilos inline;
  // los bordes del editor vienen del CSS .tiptap, que NO existe en el correo
  // recibido -> la tabla se ve como texto. Inyectamos estilos inline al enviar.
  const styleTablesForEmail = (html: string): string => {
    if (!html || html.indexOf('<table') === -1) return html;
    try {
      const doc = new DOMParser().parseFromString(html, 'text/html');
      const add = (el: Element, css: string) => {
        const prev = el.getAttribute('style') || '';
        el.setAttribute('style', (prev ? prev.replace(/;?\s*$/, ';') : '') + css);
      };
      doc.querySelectorAll('table').forEach((t) => add(t, 'border-collapse:collapse;border:1px solid #d0d0d0;'));
      doc.querySelectorAll('td,th').forEach((c) => add(c, 'border:1px solid #d0d0d0;padding:6px 8px;'));
      doc.querySelectorAll('th').forEach((h) => add(h, 'background:#f3f2f1;font-weight:600;text-align:left;'));
      return doc.body.innerHTML;
    } catch {
      return html;
    }
  };

  const getFullHtml = useCallback(() => {
    const body = styleTablesForEmail(editor?.getHTML() || '');
    let html = body;
    // No duplicar: si el cuerpo ya trae la firma (p.ej. un borrador antiguo
    // guardado con la firma incrustada), no la reagregamos.
    if (signatureHtml && !body.includes('email-signature')) {
      html += '<div class="email-signature" style="margin-top:12px;color:#605e5c">' + signatureHtml + '</div>';
    }
    if (quotedHtml) {
      html += quotedHtml;
    }
    return html;
  }, [editor, signatureHtml, quotedHtml]);

  // Para GUARDAR borradores: cuerpo + cita, SIN la firma. La firma se conserva
  // como estado aparte y se re-aplica al reabrir, para que no quede incrustada
  // en el editor (donde se distorsiona) ni se duplique al enviar.
  const getDraftHtml = useCallback(() => {
    let html = editor?.getHTML() || '';
    if (quotedHtml) html += quotedHtml;
    return html;
  }, [editor, quotedHtml]);

  // Initialize content
  // ==========================================================================
  // INICIALIZACION DEL COMPOSE (destinatarios + cuerpo)
  // --------------------------------------------------------------------------
  // FLUJO: MessageView.handleReply() -> openCompose('reply', { to, subject,
  //        html_body: quoteHtml }) -> store crea DraftWindow -> ComposePanel
  //        monta -> este useEffect inicializa campos.
  //
  // BUGS CORREGIDOS (2026-04-10):
  //   1. Reply perdia contenido citado: el else usaba win.data.text_body pero
  //      handleReply pasa el quote en win.data.html_body (text_body='').
  //      FIX: priorizar html_body, fallback a text_body.
  //   2. Campo "Para" quedaba vacio: setTo() se ejecuta aqui pero
  //      RecipientField ya estaba montado con value="". Ver comentarios
  //      en RecipientField.tsx para la solucion completa.
  // ==========================================================================
  useEffect(() => {
    // Precargar destinatarios (RecipientField sincroniza via useEffect[value])
    setTo(win.data.to?.join(', ') || '');
    setCc(win.data.cc?.join(', ') || '');
    setBcc(win.data.bcc?.join(', ') || '');
    setSubject(win.data.subject || '');
    setShowCc(!!win.data.cc?.length);
    setShowBcc(!!win.data.bcc?.length);
    setImportance('normal');
    setError('');

    const init = async () => {
      let sig = '';
      try {
        // Cache signature in session to avoid re-fetching (and re-loading external images)
        const cached = sessionStorage.getItem('maquita_sig_cache');
        if (cached) {
          sig = cached;
        } else {
          const res = await api.get<{ signature_html: string }>('/settings/signature');
          sig = res.signature_html || '';
          if (sig) sessionStorage.setItem('maquita_sig_cache', sig);
        }
      } catch {}

      let content = '';
      if (win.mode === 'new' && win.data.html_body) {
        // Editando un borrador: quitamos la firma incrustada (de borradores
        // guardados antes de este fix) para que NO se distorsione en el editor
        // ni se duplique; se re-aplica aparte, editable, mas abajo.
        content = win.data.html_body.replace(/<div class="email-signature"[\s\S]*$/i, '');
        if (sig) setSignatureHtml(sig);
      } else if (win.mode === 'new') {
        content = '<p><br></p>';
        if (sig) setSignatureHtml(sig);
      } else {
        // Reply / ReplyAll / Forward
        // El quote se renderiza FUERA del editor, DESPUES de la firma.
        // Orden visual: [editor: texto usuario] → [firma] → [quote]
        // Bug 2026-04-10: antes el quote iba dentro del editor y la firma
        // quedaba al final de todo, lejos de donde el usuario escribe.
        if (win.data.html_body) {
          setQuotedHtml(win.data.html_body);
        } else if (win.data.text_body) {
          setQuotedHtml(`<div style="border-top:1px solid #edebe9;padding-top:10px;margin-top:20px;color:#605e5c"><p>${win.data.text_body.replace(/\n/g, "<br>")}</p></div>`);
        }
        if (sig) setSignatureHtml(sig);
        // Smart Reply: prefill_body contiene el texto IA pre-generado
        content = win.data.prefill_body || '<p><br></p>';

      }
      editor?.commands.setContent(content);
      // Allow smart-compose after init is done
      setTimeout(() => { initializingRef.current = false; }, 500);
    };
    if (editor && !initializedRef.current) { initializedRef.current = true; init(); }
  }, [editor]);

  const saveDraft = useCallback(async () => {
    if (!to && !subject && !editor?.getHTML()) return;
    try {
      const res = await api.post<{ draft_uid: number | null }>('/mail/drafts', {
        to: to.split(',').map(s => s.trim()).filter(Boolean),
        subject, html_body: getDraftHtml(), text_body: '',
        existing_draft_uid: win.draftUid,
      });
      if (res.draft_uid) updateDraftUid(win.id, res.draft_uid);
    } catch {}
  }, [to, subject, win.draftUid, win.id, editor]);

  // Share editor with main Toolbar ribbon
  React.useEffect(() => {
    // Keep this effect below `saveDraft`: moving it above reintroduces a TDZ crash
    // when `compose-save-draft` is wired before the callback is initialized.
    if (editor) {
      useMailStore.getState().setActiveEditor(editor);
      useMailStore.getState().setComposeRibbonTab('message');
    }
    const attachHandler = () => fileInputRef.current?.click();
    const attachCloudHandler = () => setMostrarNube(true);
    const draftHandler = () => saveDraft();
    const ccHandler = () => setShowCc(true);
    const bccHandler = () => setShowBcc(true);
    // Firma elegida en el menu del Ribbon: la mostramos abajo (editable),
    // reemplazando la actual. No se inserta en el editor (evita duplicados).
    const sigHandler = (e: Event) => { setSignatureHtml((e as CustomEvent<string>).detail ?? ''); };
    window.addEventListener('compose-attach', attachHandler);
    window.addEventListener('compose-attach-cloud', attachCloudHandler);
    window.addEventListener('compose-save-draft', draftHandler);
    window.addEventListener('compose-show-cc', ccHandler);
    window.addEventListener('compose-show-bcc', bccHandler);
    window.addEventListener('compose-insert-signature', sigHandler);
    return () => {
      useMailStore.getState().setActiveEditor(null);
      window.removeEventListener('compose-attach', attachHandler);
      window.removeEventListener('compose-attach-cloud', attachCloudHandler);
      window.removeEventListener('compose-save-draft', draftHandler);
      window.removeEventListener('compose-show-cc', ccHandler);
      window.removeEventListener('compose-show-bcc', bccHandler);
      window.removeEventListener('compose-insert-signature', sigHandler);
    };
  }, [editor, saveDraft]);

  // Autosave every 30s
  useEffect(() => {
    autosaveTimer.current = setInterval(() => { saveDraft(); }, 30000);
    return () => { if (autosaveTimer.current) clearInterval(autosaveTimer.current); };
  }, [saveDraft]);
  // Close with save confirmation
  const handleClose = useCallback(async () => {
    const hasContent = !!(to || subject || (editor && editor.getText().trim()));
    if (hasContent) {
      // Auto-guardar borrador silenciosamente al cerrar (sin diálogo intrusivo)
      try {
        await saveDraft();
        showToast('Borrador guardado');
      } catch {
        // Si falla el guardado, cerrar de todas formas
      }
    }
    // Destruir editor antes de cerrar para evitar HTML residual
    if (editor) {
      editor.commands.clearContent();
    }
    closeCompose(win.id);
  }, [to, subject, editor, saveDraft, win.id, closeCompose]);

  // Convertir File a base64 para enviar adjuntos al backend
  const readFileAsBase64 = (file: File): Promise<string> =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const result = reader.result as string;
        resolve(result.split(',')[1] ?? '');
      };
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(file);
    });

  // handleSend with 5-second undo  MUST be defined before keyboard useEffect
  const handleSend = useCallback(async () => {
    if (encrypt) {
      const recipients = to.split(',').map(x => x.trim()).filter(Boolean);
      if (!recipients.length) { setError('Ingresa un destinatario'); return; }
      if (totalAttachBytes(attachments) / (1024 * 1024) > MAX_ATTACH_MB) { setError(`El correo supera el tamaño máximo (${MAX_ATTACH_MB} MB). Reduce los adjuntos.`); return; }
      setSending(true); setError('');
      try {
        const att = await Promise.all(
          attachments.filter(a => a.file).map(async (a) => ({
            filename: a.name,
            content_b64: await readFileAsBase64(a.file!),
            content_type: a.type || 'application/octet-stream',
          }))
        );
        await api.post('/mail/secure/send', { to: recipients, subject, html_body: getFullHtml(), attachments: att });
        showToast('Mensaje seguro enviado \uD83D\uDD12');
        window.dispatchEvent(new CustomEvent('refresh-messages'));
        closeCompose(win.id);
      } catch (err: any) {
        setSending(false);
        const m = err?.message || '';
        if (m.includes('413')) setError(`El correo supera el tamaño máximo (${MAX_ATTACH_MB} MB). Reduce los adjuntos.`);
        else setError('No se pudo enviar cifrado: ' + m);
      }
      return;
    }
    const recipients = to.split(',').map(s => s.trim()).filter(Boolean);
    if (!recipients.length) { setError('Ingresa un destinatario'); return; }
    // Límite de tamaño de adjuntos (fuente: VITE_MAX_ATTACHMENT_MB)
    const totalAttachMB = totalAttachBytes(attachments) / (1024 * 1024);
    if (totalAttachMB > MAX_ATTACH_MB) {
      setError(`El correo supera el tamaño máximo (${MAX_ATTACH_MB} MB). Adjuntos: ${totalAttachMB.toFixed(1)} MB. Quita o reduce archivos.`);
      return;
    }
    // Advertencia si el asunto está vacío
    if (!subject.trim()) {
      if (!window.confirm("¿Enviar sin asunto?")) return;
    }
    // -- DLP: prevención de fuga de datos sensibles --
    let dlpOverride = false;
    try {
      const dlp: any = await api.post('/mail/dlp/check', { subject, html_body: getFullHtml(), text_body: '' });
      if (dlp && Array.isArray(dlp.findings) && dlp.findings.length) {
        const tipos = dlp.findings.map((x: any) => '\u2022 ' + x.label).join('\n');
        if (dlp.action === 'block') {
          window.alert('\uD83D\uDD12 Env\u00edo bloqueado por Protecci\u00f3n de datos.\n\nEste correo contiene:\n' + tipos + '\n\nQuita esos datos para poder enviarlo.');
          return;
        }
        if (dlp.action === 'warn') {
          const ok = window.confirm('\u26A0\uFE0F Atenci\u00f3n: este correo contiene datos sensibles:\n\n' + tipos + '\n\n\u00bfEnviar de todas formas?');
          if (!ok) return;
          dlpOverride = true;
        }
      }
    } catch { /* si DLP no responde, no bloqueamos el env\u00edo */ }
    const sendPayload = {
      to: recipients,
      cc: cc ? cc.split(',').map(s => s.trim()).filter(Boolean) : undefined,
      bcc: bcc ? bcc.split(',').map(s => s.trim()).filter(Boolean) : undefined,
      subject, html_body: getFullHtml(), text_body: '',
      in_reply_to: win.data.in_reply_to || '', references: win.data.references || '',
      attachments: await Promise.all(
        attachments.filter(a => a.file).map(async (a) => ({
          filename: a.name,
          content_b64: await readFileAsBase64(a.file!),
          content_type: a.type || 'application/octet-stream',
        }))
      ),
      draft_uid: win.draftUid,
      dlp_override: dlpOverride,
      request_read_receipt: trackingState.read,
      request_delivery_receipt: trackingState.delivery,
    };
    const savedData = { mode: win.mode, data: { ...win.data, to: recipients, subject, html_body: getFullHtml(), text_body: '' } };
    const winId = win.id;
    closeCompose(winId);
    let remaining = 5;
    const toastId = showToast(`Enviando en ${remaining}s...`, { label: 'Deshacer', onClick: () => {
      const p = pendingSendMap.get(winId); if (p) { clearTimeout(p.timerId); clearInterval(p.intervalId); pendingSendMap.delete(winId); }
      dismissToast(toastId); useMailStore.getState().openCompose(savedData.mode, savedData.data); showToast('Envío cancelado');
    }});
    const intervalId = setInterval(() => { remaining--; if (remaining <= 0) return; }, 1000);
    const timerId = setTimeout(async () => {
      // OFFLINE: queue in outbox instead of sending
      if (!navigator.onLine) {
        clearInterval(intervalId); pendingSendMap.delete(winId); dismissToast(toastId);
        try {
          await addToOutbox({
            to: sendPayload.to, cc: sendPayload.cc, bcc: sendPayload.bcc,
            subject: sendPayload.subject, html_body: sendPayload.html_body,
            text_body: sendPayload.text_body, in_reply_to: sendPayload.in_reply_to,
            references: sendPayload.references, attachments: sendPayload.attachments,
            request_read_receipt: sendPayload.request_read_receipt,
            request_delivery_receipt: sendPayload.request_delivery_receipt,
          });
          showToast('Sin conexion: correo guardado en bandeja de salida. Se enviara al reconectar.');
        } catch { showToast('Error al guardar correo offline'); }
        return;
      }
      clearInterval(intervalId); pendingSendMap.delete(winId); dismissToast(toastId);
      try { await api.post('/mail/send', sendPayload); showToast('Mensaje enviado'); window.dispatchEvent(new CustomEvent('refresh-messages'));
      } catch (err: unknown) {
        const errMsg = err instanceof Error ? err.message : 'Error al enviar';
        if (errMsg.includes('413')) {
          showToast(`El correo supera el tamaño máximo (${MAX_ATTACH_MB} MB). Reduce los adjuntos.`);
        } else if (errMsg.includes('Session expired') || errMsg.includes('SMTP expirada') || errMsg.includes('401')) {
          showToast('Sesión expirada. Cierra sesión y vuelve a iniciar.');
        } else {
          showToast('Error al enviar: ' + errMsg);
        }
        useMailStore.getState().openCompose(savedData.mode, savedData.data);
      }
    }, 5000);
    pendingSendMap.set(winId, { timerId, toastId, intervalId });
  }, [to, cc, bcc, subject, editor, win, trackingState, closeCompose, attachments, encrypt]);

  // Close send dropdown on click outside
  useEffect(() => {
    if (!showSendDropdown) return;
    function handleClick(e: MouseEvent) {
      if (sendDropdownRef.current && !sendDropdownRef.current.contains(e.target as Node)) {
        setShowSendDropdown(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [showSendDropdown]);

  // Keyboard shortcuts: Ctrl+Enter  send, Esc  close
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); handleSend(); }
      if (e.key === 'Escape') {
        // No cerrar compose si hay un dropdown/popup abierto (tabla, color, etc.)
        const hasOpenPopup = document.querySelector('.tippy-box, [data-tippy-root], [role="listbox"], .tiptap-menu, [data-radix-popper-content-wrapper], [role="dialog"], [role="menu"]');
        if (hasOpenPopup) { e.stopPropagation(); return; }
        // Si hay send dropdown abierto, cerrarlo en vez de cerrar compose
        if (showSendDropdown) { setShowSendDropdown(false); e.preventDefault(); return; }
        e.preventDefault();
        handleClose();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [handleSend, handleClose, showSendDropdown]);

  const handleAttach = () => { fileInputRef.current?.click(); };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;
    const newFiles: AttachmentFile[] = Array.from(files).map(f => ({
      name: f.name, size: f.size, type: f.type, file: f,
    }));
    setAttachments(prev => [...prev, ...newFiles]);
    e.target.value = '';
  };

  const adjuntarDesdeNube = (archivos: File[]) => {
    setAttachments(prev => [...prev, ...archivos.map(f => ({ name: f.name, size: f.size, type: f.type, file: f }))]);
  };

  const removeAttachment = (idx: number) => {
    setAttachments(prev => prev.filter((_, i) => i !== idx));
  };

  //  Drag & Drop
  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current++;
    if (e.dataTransfer.types.includes("Files")) {
      setIsDragging(true);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current--;
    if (dragCounter.current === 0) {
      setIsDragging(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    dragCounter.current = 0;
    const files = e.dataTransfer.files;
    if (!files || files.length === 0) return;
    const newFiles: AttachmentFile[] = Array.from(files).map(f => ({
      name: f.name, size: f.size, type: f.type, file: f,
    }));
    setAttachments(prev => [...prev, ...newFiles]);
  }, []);

  const insertSignature = useCallback(async (html?: string) => {
    // Seleccion desde el menu de firmas: aplica ESA firma (reemplaza, no duplica).
    if (html !== undefined) {
      setSignatureHtml(html);
      showToast(html ? 'Firma aplicada' : 'Firma quitada');
      return;
    }
    // Si la firma ya esta puesta, llevamos el foco a ella para EDITARLA
    // (no se agrega una segunda firma).
    if (signatureHtml) {
      const el = document.getElementById('compose-signature-edit');
      if (el) { el.focus(); el.scrollIntoView({ block: 'center' }); }
      showToast('Edita tu firma abajo');
      return;
    }
    try {
      const cached = sessionStorage.getItem('maquita_sig_cache');
      const sig = cached || (await api.get<{ signature_html: string }>('/settings/signature')).signature_html;
      if (sig) {
        if (!cached) sessionStorage.setItem('maquita_sig_cache', sig);
        setSignatureHtml(sig);
        showToast('Firma insertada');
      } else {
        showToast('No hay firma configurada');
      }
    } catch { showToast('Error al cargar la firma'); }
  }, [signatureHtml]);

  const downloadDraft = useCallback(() => {
    const html = getFullHtml();
    const fullHtml = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${subject || 'Borrador'}</title></head><body style="font-family:Calibri,sans-serif;font-size:14px">${html}</body></html>`;
    const blob = new Blob([fullHtml], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${subject || 'borrador'}.html`;
    a.click();
    URL.revokeObjectURL(url);
  }, [editor, subject]);

  // ====== Callbacks conectados a backends ======

  // Helper para llamar a la API IA (proxy nginx /api/ia/  VM 170)
  const iaFetch = useCallback(async <T,>(endpoint: string, body: object): Promise<T> => {
    const res = await fetch(`/api/ia/${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`IA error: ${res.status}`);
    return res.json();
  }, []);

  //  VM 170: Mejorar redacción con IA - PROGRESIVO 4 NIVELES
  const [improveLevel, setImproveLevel] = useState(0);
  const MAX_LEVEL = 4;
  const LEVEL_LABELS = ['', 'Nivel 1/4 · Corrigiendo ortografía...', 'Nivel 2/4 · Mejorando sintaxis...', 'Nivel 3/4 · Alineando a Maquita...', 'Nivel 4/4 · Pulido ejecutivo...'];
  const LEVEL_TOASTS = ['', 'Ortografía corregida', 'Sintaxis mejorada', 'Alineado a Maquita', 'Pulido ejecutivo aplicado'];
  const LEVEL_NEXT = ['', 'mejorar sintaxis', 'alinear a Maquita', 'pulido ejecutivo', ''];

  const [improving, setImproving] = useState(false);

  const handleImproveWriting = useCallback(async () => {
    const text = editor?.getText() || '';
    if (!text.trim() || text.trim().length < 10) {
      showToast('Escribe al menos una oración para mejorar');
      return;
    }
    if (improving) return;
    // BLINDAJE: guardamos el contenido original; NUNCA se reemplaza salvo mejora valida.
    const originalHtml = editor?.getHTML() || '';
    const nextLevel = improveLevel >= MAX_LEVEL ? 1 : improveLevel + 1;
    setImproving(true);
    const progressId = showToast(LEVEL_LABELS[nextLevel]);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 30000);

    try {
      const res = await fetch('/api/ia/improve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: originalHtml || text, tone: 'professional', level: nextLevel }),
        signal: controller.signal,
      });
      if (!res.ok) throw new Error(`IA ${res.status}`);
      const data = await res.json();
      const improved = ((data && data.improved_text) || '').trim();
      const plainLen = improved.replace(/<[^>]+>/g, '').trim().length;
      // Solo reemplazamos si la IA devolvio una mejora con contenido REAL. Si no, mantenemos el texto del usuario.
      if (improved && plainLen >= 5) {
        editor?.commands.setContent(improved);
        if (data.subject_suggestion && !subject) setSubject(data.subject_suggestion);
        setImproveLevel(nextLevel);
        dismissToast(progressId);
        const next = LEVEL_NEXT[nextLevel];
        showToast(next
          ? `${LEVEL_TOASTS[nextLevel]} (${data.changes_summary || ''}). Click para ${next}.`
          : `${LEVEL_TOASTS[nextLevel]}: ${data.changes_summary || ''}`
        );
      } else {
        dismissToast(progressId);
        showToast('La IA no devolvió una mejora válida. Tu texto se mantiene intacto.');
      }
    } catch {
      dismissToast(progressId);
      showToast('No se pudo mejorar (IA ocupada). Tu texto se mantiene intacto.');
    } finally {
      clearTimeout(timer);
      setImproving(false);
    }
  }, [editor, subject, improveLevel, improving]);

  //  VM 170: Revisión IA del texto - FUNCIONAL
  const handleReviewEditor = useCallback(async () => {
    const text = editor?.getText() || '';
    if (!text.trim()) { showToast('No hay texto para revisar'); return; }
    showToast('Revisando con IA...');
    try {
      const data = await iaFetch<{ score: number; feedback: string; suggestions: string[]; corrected_text: string | null }>('review', {
        text: editor?.getHTML() || text,
        subject,
      });
      const msg = `Puntuación: ${data.score}/10\n\n${data.feedback}\n\nSugerencias:\n${data.suggestions.map(s => ' ' + s).join('\n')}`;
      if (data.corrected_text && confirm(`${msg}\n\n¿Aplicar la versión corregida?`)) {
        editor?.commands.setContent(data.corrected_text.replace(/\n/g, '<br>'));
        showToast('Correcciones aplicadas');
      } else {
        alert(msg);
      }
    } catch { showToast('Error al conectar con IA'); }
  }, [editor, subject, iaFetch]);

  //  VM 170: Análisis de accesibilidad - FUNCIONAL
  const handleCheckAccessibility = useCallback(async () => {
    const html = editor?.getHTML() || '';
    const issues: string[] = [];
    if (html.includes('<img') && !html.includes('alt=')) issues.push('Imágenes sin texto alternativo (alt)');
    if (html.length > 50000) issues.push('Email muy largo (>50KB)');
    if (!html.includes('</p>') && html.length > 500) issues.push('Texto largo sin párrafos separados');
    showToast(issues.length ? `Accesibilidad: ${issues.length} problema(s)` : 'Sin problemas de accesibilidad');
    if (issues.length) alert(`Problemas de accesibilidad:\n\n${issues.map(i => ' ' + i).join('\n')}`);
  }, [editor]);


  //  VM 170: Sugerir asunto con IA
  const [suggestingSubject, setSuggestingSubject] = useState(false);
  const handleSuggestSubject = useCallback(async () => {
    const text = editor?.getText() || '';
    if (!text.trim() || text.trim().length < 10) {
      showToast('Escribe algo en el cuerpo para sugerir asunto');
      return;
    }
    if (suggestingSubject) return;
    setSuggestingSubject(true);
    showToast('Generando sugerencias de asunto...');
    try {
      const data = await api.post<{ suggestions: string[] }>('/ai/suggest-subject', { body: text });
      if (data.suggestions?.length) {
        const choice = data.suggestions.length === 1
          ? data.suggestions[0]
          : await new Promise<string | null>((resolve) => {
              const msg = data.suggestions.map((s, i) => `${i + 1}. ${s}`).join('\n');
              const pick = prompt(`Sugerencias de asunto:\n\n${msg}\n\nEscribe el numero (1-${data.suggestions.length}):`);
              if (pick) {
                const idx = parseInt(pick) - 1;
                resolve(idx >= 0 && idx < data.suggestions.length ? data.suggestions[idx] : null);
              } else resolve(null);
            });
        if (choice) {
          setSubject(choice);
          showToast('Asunto aplicado');
        }
      } else {
        showToast('No se pudieron generar sugerencias');
      }
    } catch { showToast('Error al conectar con IA'); }
    setSuggestingSubject(false);
  }, [editor, api, suggestingSubject]);

  //  VM 170: Smart Compose — autocompletado IA
  const [composeSuggestion, setComposeSuggestion] = useState('');
  const [composingSuggestion, setComposingSuggestion] = useState(false);
  const composeDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);
  const smartComposeAbort = useRef<AbortController | null>(null);
  const initializingRef = useRef(true);

  // VM 170: Smart Compose — ON-DEMAND (boton), ya NO automatico (evita saturar el GPU)
  const requestSmartCompose = useCallback(async () => {
    if (!editor) return;
    const context = editor.getText();
    if (context.trim().length < 10) { showToast('Escribe algo de texto primero'); return; }
    setComposingSuggestion(true);
    setComposeSuggestion('');
    try {
      const data = await api.post<{ suggestion: string }>('/ai/smart-compose', { context, subject, to });
      if (data.suggestion) setComposeSuggestion(data.suggestion);
      else showToast('La IA no devolvio una sugerencia');
    } catch { showToast('No se pudo generar (IA ocupada, reintenta)'); }
    finally { setComposingSuggestion(false); }
  }, [editor, subject, to]);

  const acceptComposeSuggestion = useCallback(() => {
    if (composeSuggestion && editor) {
      editor.chain().focus().insertContent(composeSuggestion).run();
      setComposeSuggestion('');
      showToast('Sugerencia aceptada');
    }
  }, [editor, composeSuggestion]);
  //  VM 170: Whisper STT
  const [dictating, setDictating] = useState(false);
  const handleDictate = useCallback(() => {
    setDictating(prev => !prev);
  }, []);
  const handleTranscript = useCallback((text: string) => {
    if (editor) {
      editor.chain().focus().insertContent(text + ' ').run();
      showToast('Texto dictado insertado');
    }
    setDictating(false);
  }, [editor]);

  // handleScheduleSend defined above

  //  Futuro: Nextcloud/LibreOffice Online
  const handleOpenApps = useCallback(() => {
    const appList = [
      'Traductor de idiomas',
      'Corrector ortográfico avanzado',
      'Plantillas de correo',
      'Generador de firmas',
    ].join(' · ');
    showToast('Complementos disponibles: ' + appList);
  }, []);

  // Copiar formato
  const handleFormatPaint = useCallback((marks: string[]) => {
    showToast(marks.length ? `Formato copiado: ${marks.join(', ')}` : 'Seleccione texto con formato');
  }, []);


  const handleTrackingChange = useCallback((t: { delivery: boolean; read: boolean; noReactions: boolean }) => {
    setTrackingState(t);
  }, []);

  // Schedule send
  const handleScheduleSend = useCallback(() => {
    const now = new Date(); now.setHours(now.getHours() + 1);
    setScheduleDate(now.toISOString().slice(0, 16));
    setShowScheduleModal(true);
  }, []);

  const handleConfirmSchedule = useCallback(async () => {
    if (!scheduleDate) { showToast('Selecciona fecha y hora'); return; }
    const recipients = to.split(',').map(s => s.trim()).filter(Boolean);
    if (!recipients.length) { setError('Ingresa un destinatario'); return; }
    try {
      await api.post('/mail/schedule', {
        to: recipients, cc: cc ? cc.split(',').map(s => s.trim()).filter(Boolean) : [],
        bcc: bcc ? bcc.split(',').map(s => s.trim()).filter(Boolean) : [],
        subject, html_body: getFullHtml(), text_body: '',
        in_reply_to: win.data.in_reply_to || '', references: win.data.references || '',
        scheduled_at: new Date(scheduleDate).toISOString(),
        request_read_receipt: trackingState.read, request_delivery_receipt: trackingState.delivery,
      });
      closeCompose(win.id); setShowScheduleModal(false);
      showToast(`Envío programado para ${new Date(scheduleDate).toLocaleString('es-EC')}`);
    } catch { showToast('Error al programar envío'); }
  }, [to, cc, bcc, subject, editor, win, scheduleDate, trackingState, closeCompose]);

  useEffect(() => {
    const scheduleHandler = () => handleScheduleSend();
    const reviewHandler = () => handleReviewEditor();
    const accessibilityHandler = () => handleCheckAccessibility();
    const improveHandler = () => handleImproveWriting();
    const dictateHandler = () => handleDictate();
    const openAppsHandler = () => handleOpenApps();
    const trackingHandler = (event: Event) => {
      const customEvent = event as CustomEvent<{ delivery: boolean; read: boolean; noReactions: boolean }>;
      if (customEvent.detail) handleTrackingChange(customEvent.detail);
    };

    window.addEventListener('compose-schedule-send', scheduleHandler);
    window.addEventListener('compose-review-editor', reviewHandler);
    window.addEventListener('compose-check-accessibility', accessibilityHandler);
    const suggestSubjectHandler = () => handleSuggestSubject();
    const acceptComposeHandler = () => acceptComposeSuggestion();
    window.addEventListener('compose-improve-writing', improveHandler);
    window.addEventListener('compose-suggest-subject', suggestSubjectHandler);
    window.addEventListener('compose-accept-suggestion', acceptComposeHandler);
    window.addEventListener('compose-dictate', dictateHandler);
    window.addEventListener('compose-open-apps', openAppsHandler);
    window.addEventListener('compose-tracking-change', trackingHandler as EventListener);

    return () => {
      window.removeEventListener('compose-schedule-send', scheduleHandler);
      window.removeEventListener('compose-review-editor', reviewHandler);
      window.removeEventListener('compose-check-accessibility', accessibilityHandler);
      window.removeEventListener('compose-improve-writing', improveHandler);
      window.removeEventListener('compose-suggest-subject', suggestSubjectHandler);
      window.removeEventListener('compose-accept-suggestion', acceptComposeHandler);
      window.removeEventListener('compose-dictate', dictateHandler);
      window.removeEventListener('compose-open-apps', openAppsHandler);
      window.removeEventListener('compose-tracking-change', trackingHandler as EventListener);
    };
  }, [handleScheduleSend, handleReviewEditor, handleCheckAccessibility, handleImproveWriting, handleDictate, handleOpenApps, handleTrackingChange, handleSuggestSubject, acceptComposeSuggestion]);

  if (!editor) return null;

  return (
    <div className="flex-1 flex flex-col bg-white overflow-hidden relative"
      onDragEnter={handleDragEnter}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}>
      {/* Drop overlay */}
      {isDragging && (
        <div className="absolute inset-0 z-50 bg-white/90 flex items-center justify-center pointer-events-none"
          style={{ border: "3px dashed #0078d4", borderRadius: 8, margin: 4 }}>
          <div className="text-center">
            <svg className="w-16 h-16 mx-auto mb-3 text-[#0078d4]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <p className="text-[16px] font-semibold text-[#0078d4]">Soltar archivos aquí</p>
            <p className="text-[13px] text-[#605e5c] mt-1">Se agregarán como adjuntos</p>
          </div>
        </div>
      )}
      {/* Ribbon (tabs + toolbar) */}
      {/* Ribbon rendered in main Toolbar */}

      {/* Hidden file input */}
      <input ref={fileInputRef} type="file" multiple className="hidden" onChange={handleFileSelect} />
      {mostrarNube && <SelectorArchivosNube onCerrar={() => setMostrarNube(false)} onElegir={adjuntarDesdeNube} />}

      {/* Send row (below ribbon, above recipients) - matches OWA layout exactly */}
      <div className="h-[44px] flex items-center px-4 bg-white border-b border-[#edebe9] shrink-0">
        {/* Send button with dropdown caret */}
        <div className="flex items-center relative" ref={sendDropdownRef}>
          <button onClick={handleSend} disabled={sending}
            className="h-[32px] pl-3 pr-2.5 bg-[#0078d4] text-white text-[13px] font-semibold rounded-l-[4px] hover:bg-[#106ebe] disabled:opacity-50 transition-colors flex items-center gap-[6px]">
            <svg className="w-[16px] h-[16px]" viewBox="0 0 24 24" fill="currentColor">
              <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
            </svg>
            {sending ? 'Enviando...' : 'Enviar'}
          </button>
            <button
              onClick={() => setShowSendDropdown(!showSendDropdown)}
              className="h-[32px] px-[6px] bg-[#0078d4] text-white rounded-r-[4px] border-l border-[#ffffff40] hover:bg-[#106ebe] transition-colors"
            >
              <svg className="w-[10px] h-[10px]" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
            {showSendDropdown && (
              <div className="absolute left-0 top-full mt-1 bg-white border border-[#e0e0e0] rounded shadow-lg z-[9999] py-1 min-w-[220px]">
                <button
                  className="w-full text-left px-3 py-[7px] text-[13px] text-[#323130] hover:bg-[#f3f2f1] flex items-center gap-2"
                  onClick={() => { setShowSendDropdown(false); handleSend(); }}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="#0078d4">
                    <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
                  </svg>
                  Enviar
                </button>
                <button
                  className="w-full text-left px-3 py-[7px] text-[13px] text-[#323130] hover:bg-[#f3f2f1] flex items-center gap-2"
                  onClick={() => { setShowSendDropdown(false); handleScheduleSend(); }}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#605e5c" strokeWidth="1.5">
                    <circle cx="12" cy="12" r="9" />
                    <path d="M12 6v6l4 4" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  Programar envío
                </button>
              </div>
            )}
        </div>

        {secureEnabled && (
          <button onClick={() => setEncrypt(v => !v)} title="Cifrar este mensaje (solo el destinatario podrá abrirlo)"
            className={`ml-3 h-[32px] px-3 rounded-[4px] text-[13px] font-medium flex items-center gap-1.5 border transition-colors ${encrypt ? 'bg-[#0078d4] text-white border-[#0078d4]' : 'bg-white text-[#605e5c] border-[#c8c6c4] hover:bg-[#f3f2f1]'}`}>
            <svg className="w-[15px] h-[15px]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 11V7a4 4 0 018 0v4M5 11h14v10H5z" /></svg>
            {encrypt ? 'Cifrado' : 'Cifrar'}
          </button>
        )}

        <div className="flex-1" />

        {/* Right icons: delete draft + minimize/save */}
        <div className="flex items-center gap-[2px]">
          <button onClick={handleClose} title="Descartar"
            className="w-[32px] h-[32px] rounded-[3px] flex items-center justify-center text-[#605e5c] hover:bg-[#f3f2f1] hover:text-[#323130] transition-colors">
            <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
          <button onClick={() => minimizeCompose(win.id)} title="Minimizar"
            className="w-[32px] h-[32px] rounded-[3px] flex items-center justify-center text-[#605e5c] hover:bg-[#f3f2f1] hover:text-[#323130] transition-colors">
            <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
            </svg>
          </button>
        </div>
      </div>

      {/* Recipients */}
      <RecipientField label="Para" value={to} onChange={setTo} autoFocus primary
        onToggleExtra={() => { setShowCc(true); setShowBcc(true); }}
        showExtra={showCc || showBcc}
        onOpenDirectory={(target) => { setDirectoryPickerTarget(target); setShowDirectoryPicker(true); }} />
      {showCc && <RecipientField label="CC" value={cc} onChange={setCc}
        onOpenDirectory={(target) => { setDirectoryPickerTarget(target); setShowDirectoryPicker(true); }} />}
      {showBcc && <RecipientField label="CCO" value={bcc} onChange={setBcc}
        onOpenDirectory={(target) => { setDirectoryPickerTarget(target); setShowDirectoryPicker(true); }} />}

      {/* Subject */}
      <div className="border-b border-[#edebe9] shrink-0">
        <div className="flex items-center">
          <input value={subject} onChange={e => { setSubject(e.target.value); updateComposeData(win.id, { subject: e.target.value }); }}
            placeholder="Agregar un asunto"
            className="flex-1 text-[15px] px-4 py-2.5 outline-none text-[#323130] placeholder-[#a19f9d]"
            style={{ fontFamily: 'Segoe UI, Calibri, sans-serif' }} />
          <button onClick={handleSuggestSubject} disabled={suggestingSubject}
            title="Sugerir asunto con IA"
            className="mr-2 px-2 py-1 text-[11px] text-[#0078d4] hover:bg-[#f3f2f1] rounded flex items-center gap-1 disabled:opacity-50 whitespace-nowrap">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0078d4" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" /></svg>
            IA
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="px-4 py-1.5 bg-[#fde7e9] text-[#a4262c] text-[12px] shrink-0">{error}</div>
      )}

      {/* Voice dictation bar */}
      {dictating && (
        <div className="flex items-center gap-2 px-4 py-2 bg-[#fef6f6] border-b border-[#f3d6d8]">
          <VoiceDictation onTranscript={handleTranscript} />
          <span className="text-[12px] text-[#605e5c]">Habla y el texto se insertará en el editor</span>
          <button onClick={() => setDictating(false)} className="ml-auto text-[12px] text-[#605e5c] hover:text-[#323130]">Cerrar</button>
        </div>
      )}

      {/* Editor area */}
      {/* ================================================================
          CSS para escalar imagenes de firmas en contenido citado (reply).
          Bug 2026-04-10: las firmas HTML tienen imagenes de 600px+ que
          desbordaban el compose. TipTap elimina class/style de <div>,
          por eso usamos <style> global apuntando al editor .tiptap.
          max-width:280px limita logos de firma a tamaño razonable.
          ================================================================ */}
      <style>{`
        .compose-editor-area > div { height: auto !important; }
        .compose-editor-area .ProseMirror { min-height: 60px !important; height: auto !important; }
        .compose-editor-area .tiptap img {
          max-width: 160px !important;
          max-height: 70px !important;
          width: auto !important;
          height: auto !important;
        }
        .compose-editor-area .tiptap table {
          max-width: 100% !important;
          font-size: 12px;
          border-collapse: collapse;
          width: 100%;
          margin: 8px 0;
        }
        .compose-editor-area .tiptap td,
        .compose-editor-area .tiptap th {
          border: 1px solid #323130;
          padding: 6px 10px;
          min-width: 60px;
          vertical-align: top;
          position: relative;
        }
        .compose-editor-area .tiptap th {
          font-weight: 600;
          background: #f3f2f1;
        }
        .compose-editor-area .tiptap .selectedCell {
          background: #e1f0ff;
        }
        .compose-editor-area .tiptap .column-resize-handle {
          position: absolute;
          right: -2px;
          top: 0;
          bottom: 0;
          width: 4px;
          background: #0078d4;
          cursor: col-resize;
          z-index: 20;
        }
        .compose-editor-area .tiptap .tableWrapper {
          overflow-x: auto;
          margin: 8px 0;
        }
      `}</style>
      {/* Smart Compose — barra ON-DEMAND */}
      <div className="flex items-center gap-2 px-4 py-1.5 bg-[#f0f6ff] border-b border-[#c7e0f4] shrink-0">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0078d4" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" /></svg>
        {composingSuggestion ? (
          <span className="text-[12px] text-[#605e5c] flex-1">Generando sugerencia con IA...</span>
        ) : composeSuggestion ? (
          <>
            <span className="text-[12px] text-[#605e5c] truncate flex-1" title={composeSuggestion}>
              {composeSuggestion.length > 80 ? composeSuggestion.slice(0, 80) + '...' : composeSuggestion}
            </span>
            <button onClick={acceptComposeSuggestion} className="text-[11px] font-semibold text-[#0078d4] hover:bg-[#deecf9] px-2 py-0.5 rounded">Insertar</button>
            <button onClick={() => setComposeSuggestion('')} className="text-[11px] text-[#a19f9d] hover:text-[#605e5c] px-1">{'\u2715'}</button>
          </>
        ) : (
          <>
            <span className="text-[12px] text-[#605e5c] flex-1">Asistente de redaccion IA</span>
            <button onClick={requestSmartCompose} className="text-[11px] font-semibold text-[#0078d4] hover:bg-[#deecf9] px-2 py-0.5 rounded">Autocompletar con IA</button>
          </>
        )}
      </div>
      <div className="flex-1 overflow-y-auto compose-editor-area">
        <EditorContent editor={editor}
          className="[&_.tiptap_h1]:text-[24px] [&_.tiptap_h1]:font-bold [&_.tiptap_h1]:mb-3 [&_.tiptap_h2]:text-[20px] [&_.tiptap_h2]:font-bold [&_.tiptap_h2]:mb-2 [&_.tiptap_h3]:text-[16px] [&_.tiptap_h3]:font-bold [&_.tiptap_h3]:mb-1 [&_.tiptap_ul]:list-disc [&_.tiptap_ul]:pl-6 [&_.tiptap_ol]:list-decimal [&_.tiptap_ol]:pl-6 [&_.tiptap_blockquote]:border-l-4 [&_.tiptap_blockquote]:border-[#e1dfdd] [&_.tiptap_blockquote]:pl-4 [&_.tiptap_blockquote]:italic [&_.tiptap_blockquote]:text-[#605e5c] [&_.tiptap_a]:text-[#0078d4] [&_.tiptap_a]:underline [&_.tiptap_pre]:bg-[#f3f2f1] [&_.tiptap_pre]:p-3 [&_.tiptap_pre]:rounded [&_.tiptap_pre]:font-mono [&_.tiptap_pre]:text-[13px] [&_.tiptap_hr]:border-[#edebe9] [&_.tiptap_hr]:my-3 [&_.tiptap_p]:mb-1 [&_.tiptap_img]:max-w-full [&_.tiptap_img]:h-auto [&_.tiptap_img]:rounded" />

        {/* Firma — renderizada fuera del editor para preservar HTML complejo */}
        {signatureHtml && (
          <div className="compose-signature" style={{ position: 'relative', padding: '0 24px', marginTop: 8, color: '#605e5c' }}>
            <button
              onClick={() => setSignatureHtml('')}
              title="Quitar firma"
              style={{ position: 'absolute', top: 0, right: 24, background: 'none', border: 'none', cursor: 'pointer', color: '#a19f9d', fontSize: 14, padding: '2px 6px', borderRadius: 3 }}
              onMouseEnter={(e) => { e.currentTarget.style.color = '#323130'; e.currentTarget.style.background = '#f3f2f1'; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = '#a19f9d'; e.currentTarget.style.background = 'none'; }}
            >×</button>
            <div
              id="compose-signature-edit"
              contentEditable
              suppressContentEditableWarning
              onBlur={(e) => setSignatureHtml(e.currentTarget.innerHTML)}
              style={{ outline: 'none' }}
              title="Puedes editar tu firma aqui"
              dangerouslySetInnerHTML={{ __html: sanitizeSignatureHtml(signatureHtml) }}
            />
          </div>
        )}
        {/* Contenido citado (reply/forward) — se muestra DESPUES de la firma */}
        {quotedHtml && (
          <div
            contentEditable={false}
            className="compose-quoted-content"
            style={{ padding: '0 24px 16px', color: '#605e5c', userSelect: 'text', cursor: 'default', fontSize: 13 }}
            dangerouslySetInnerHTML={{ __html: sanitizeHtml(quotedHtml) }}
          />
        )}
      </div>

      {/* Attachments */}
      <Attachments files={attachments} onRemove={removeAttachment} />

      {/* Schedule send modal */}
      {showScheduleModal && (
        <div className="absolute inset-0 z-50 bg-black/30 flex items-center justify-center" onClick={() => setShowScheduleModal(false)}>
          <div className="bg-white rounded-lg shadow-xl p-5 w-80" onClick={e => e.stopPropagation()}>
            <h3 className="text-[14px] font-semibold text-[#323130] mb-3">Programar envío</h3>
            <input type="datetime-local" value={scheduleDate} onChange={e => setScheduleDate(e.target.value)}
              className="w-full border border-[#8a8886] rounded px-3 py-2 text-[13px] mb-3" />
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowScheduleModal(false)} className="px-3 py-1.5 text-[13px] text-[#605e5c] hover:bg-[#f3f2f1] rounded">Cancelar</button>
              <button onClick={handleConfirmSchedule} className="px-3 py-1.5 text-[13px] bg-[#0078d4] text-white rounded hover:bg-[#106ebe]">Programar</button>
            </div>
          </div>
        </div>
      )}

      {/* Directory picker for recipients */}
      {showDirectoryPicker && (
        <DirectoryPanel
          isOpen={showDirectoryPicker}
          onClose={() => setShowDirectoryPicker(false)}
          pickerMode
          pickerTarget={directoryPickerTarget}
          onPickContact={(contact, target) => {
            const emailAddr = contact.display_name
              ? `${contact.display_name} <${contact.email}>`
              : contact.email;
            if (target === 'to') {
              setTo(prev => prev ? `${prev}, ${emailAddr}` : emailAddr);
            } else if (target === 'cc') {
              setShowCc(true);
              setCc(prev => prev ? `${prev}, ${emailAddr}` : emailAddr);
            } else {
              setShowBcc(true);
              setBcc(prev => prev ? `${prev}, ${emailAddr}` : emailAddr);
            }
          }}
        />
      )}
    </div>
  );
}
