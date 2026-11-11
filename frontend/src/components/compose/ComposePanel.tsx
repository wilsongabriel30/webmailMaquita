// Los callbacks de la cinta viven hoy en la barra principal; se conservan aqui, marcados uno
// a uno mas abajo, hasta que se extraigan a su propio modulo (deuda anotada). Mientras esten
// declarados y sin conectar, la construccion (noUnusedLocals) los rechaza, de ahi la marca.
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-nocheck
import { addToOutbox, removeFromOutbox, updateOutboxStatus } from "../../lib/offlineStore";
import { syncOutbox } from "../../lib/syncQueue";
import { enviarCorreo } from "../../lib/envioSegundoPlano";   // envío inmediato (06/11/2026)
import { SelectorArchivosNube } from './SelectorArchivosNube';
import { SelectorRemitente } from './SelectorRemitente';
import { leerBloqueoSensibilidad, pedirMotivoSensibilidad } from './bloqueoSensibilidad';
import { cuentaDeCarpeta } from '../../lib/cuentas';
import { sanitizeSignatureHtml } from '../../lib/sanitize';
import { separarCitado } from '../../lib/borradorCitado';
import { cargarAdjuntosDelBorrador, cargarAdjuntosDelReenvio, filtrarPeligrosos, huellaAdjuntos, type ArchivoAdjunto } from '../../lib/adjuntosBorrador';
import { tomarArchivosParaRedaccion } from '../../lib/archivosParaRedaccion';
import { leerEstadoRedaccion } from '../../lib/estadoRedaccion';
import { CitaMarcable } from './CitaMarcable';
import { TIPO_ARRASTRE_CORREOS, EVENTO_ADJUNTAR_CORREO, correosArrastrados, descargarCorreosComoEml, type CorreoAAdjuntar } from '../../lib/correosComoAdjunto';
import { SelectorCorreoAdjunto } from './SelectorCorreoAdjunto';
import { useRedaccionPersistente } from './useRedaccionPersistente';
import { EVENTO_MOSTRAR_CAMPO } from './chipsArrastrables';
import { IMAGENES_SOLTADAS_EN_TEXTO, OPCIONES_RESIZE, insertarImagenesEnTexto, pegarImagenes, pegarImagenesFueraDelTexto, quitarImagenesLocales, soltarImagenes } from './imagenesPegadas';
import { BarraImagen } from './BarraImagen';
import { BotonAutocompletarIA, FranjaSugerenciaIA } from './SugerenciaIA';
import { VistaPreviaRedaccion } from './asistente-redaccion';
import { esReescritura, textoAParrafos } from '../../lib/autocompletar';
import { insertarContinuacion } from './insertarSugerencia';
import { IndicadorOrtografia } from './ortografia/IndicadorOrtografia';
import { useIdiomaOrtografia } from './ortografia/useIdiomaOrtografia';
import { aTexto } from './ortografia/idiomas';
import { useState, useEffect, useRef, useCallback } from 'react';
import { EVENTO_IMPORTANCIA, type Importancia } from '../mail/useImportanciaRedaccion';
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
import { FormatoParrafo } from './formatoParrafo';

import { useMailStore, type DraftWindow } from '../../store/mailStore';
import { api } from '../../api/client';
import type { AttachmentInfo } from '../../types';
import { showToast, updateToast, dismissToast } from '../common/Toast';
import { RecipientField } from './RecipientField';
import { Attachments } from './Attachments';
import { BotonDescartarRedaccion } from './BotonDescartarRedaccion';
import { ZonaSoltarArchivos, type ZonaSoltar } from './ZonaSoltarArchivos';
import { DirectoryPanel } from '../contacts/DirectoryPanel';
import { textoErrorEnvio } from '../../lib/mensajeErrorEnvio';

// Module-level pending send map (persists after compose unmounts)
interface PendingSend { timerId: ReturnType<typeof setTimeout>; toastId: string; intervalId: ReturnType<typeof setInterval>; }
const pendingSendMap: Map<string, PendingSend> = new Map();

interface Props { win: DraftWindow; }

type AttachmentFile = ArchivoAdjunto;
/** Un dato sensible detectado por Proteccion de datos, tal como lo devuelve el servidor. */
interface HallazgoDlp { label: string }
// Limite de adjuntos (fuente unica: MAX_ATTACHMENT_MB -> VITE en build)
const MAX_ATTACH_MB = Number(import.meta.env?.VITE_MAX_ATTACHMENT_MB) || 25;
const totalAttachBytes = (atts: AttachmentFile[]) => atts.reduce((sum, a) => sum + (a.size || 0), 0);


/** Una dirección utilizable: algo, una arroba, un dominio con punto. No aspira a validar todo
 *  lo que el RFC permite —eso solo lo sabe el servidor de destino—, sino a parar lo que es
 *  evidentemente inválido antes de dar el correo por enviado. Acepta la forma «Nombre <a@b.c>». */
function esDireccionUsable(valor: string): boolean {
  const limpio = valor.trim().replace(/^.*<([^>]+)>$/, '$1').trim();
  return /^[^\s@,;]+@[^\s@,;]+\.[^\s@,;]{2,}$/.test(limpio);
}

/** Las direcciones que no valen, para poder decir CUÁLES en el aviso. */
function direccionesInvalidas(lista: string[]): string[] {
  return lista.filter((d) => !esDireccionUsable(d));
}

export function ComposePanel({ win }: Props) {
  const closeCompose = useMailStore(s => s.closeCompose);
  const minimizeCompose = useMailStore(s => s.minimizeCompose);
  const updateComposeData = useMailStore(s => s.updateComposeData);
  // Si la ventana vuelve de estar minimizada, se retoma lo que había en pantalla (estadoRedaccion.ts).
  const [estadoPrevio] = useState(() => leerEstadoRedaccion(win.id));
  const [to, setTo] = useState(estadoPrevio?.to ?? '');
  // Cuenta desde la que sale: la de la carpeta que se estaba viendo al abrir el redactor
  const [fromEmail, setFromEmail] = useState(() => estadoPrevio?.fromEmail ?? (cuentaDeCarpeta(useMailStore.getState().currentFolder) || ''));
  const [cc, setCc] = useState(estadoPrevio?.cc ?? '');
  const [bcc, setBcc] = useState(estadoPrevio?.bcc ?? '');
  const [subject, setSubject] = useState(estadoPrevio?.subject ?? '');
  const [sensitivity, setSensitivity] = useState('');
  const [showCc, setShowCc] = useState(estadoPrevio?.showCc ?? false);
  const [showBcc, setShowBcc] = useState(estadoPrevio?.showBcc ?? false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  // Importancia elegida en la cinta (barra principal): llega por EVENTO_IMPORTANCIA y se reinicia al abrir.
  const [importance, setImportance] = useState<Importancia>('normal');
  const [attachments, setAttachments] = useState<AttachmentFile[]>(estadoPrevio?.attachments ?? []);
  const [mostrarNube, setMostrarNube] = useState(false);
  // «Correo como adjunto» (menú Insertar): selector de correos del buzón (09/11/2026).
  const [mostrarSelectorCorreo, setMostrarSelectorCorreo] = useState(false);

  // Adjuntos provenientes de la sección Archivos (Almacén): se descargan con
  // la misma sesión y entran como adjuntos normales del mensaje.
  useEffect(() => {
    const pendientes = win.data?.adjuntos_almacen;
    if (!pendientes?.length || estadoPrevio) return;
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

  // Archivos que esperaban a esta ventana (p. ej. un PDF firmado desde el visor con «Responder con
  // el PDF firmado», 09/11/2026): entran como adjuntos normales al montarse el editor.
  useEffect(() => {
    if (estadoPrevio) return;
    const iniciales = tomarArchivosParaRedaccion();
    if (!iniciales.length) return;
    setAttachments(prev => [...prev, ...iniciales.map(f => ({ name: f.name, size: f.size, type: f.type, file: f }))]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // «Reenviar como adjunto»: los correos elegidos entran como .eml (lib/correosComoAdjunto.ts).
  useEffect(() => {
    const correos = win.data?.correos_adjuntos;
    if (!correos?.length || estadoPrevio) return;
    descargarCorreosComoEml(correos).then(({ cargados, fallidos }) => {
      if (cargados.length) setAttachments(prev => [...prev, ...cargados]);
      if (fallidos.length) showToast(`No se pudo adjuntar: ${fallidos.join(', ')}`);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Al reenviar, los adjuntos del correo original entran al redactor y salen con el mensaje.
  useEffect(() => {
    const origen = win.data?.reenvio_de;
    if (win.mode !== 'forward' || !origen || estadoPrevio) return;
    cargarAdjuntosDelReenvio(origen).then(cargados => {
      if (cargados.length) setAttachments(prev => [...prev, ...cargados]);
      else if (origen.adjuntos?.some(a => !a.is_inline)) showToast('No se pudieron traer los adjuntos del correo original');
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [isDragging, setIsDragging] = useState(false);
  const dragCounter = useRef(0);
  // Si lo arrastrado trae imágenes, dos zonas: arriba «Adjuntar», abajo «Insertar en el texto» (07/11/2026).
  const [arrastraImagenes, setArrastraImagenes] = useState(false);
  const [zonaSoltar, setZonaSoltar] = useState<ZonaSoltar>('adjuntar');
  // Límite entre «Adjuntar» e «Insertar»: el borde superior del editor, en px desde arriba del panel (08/11/2026).
  const [limiteZona, setLimiteZona] = useState<number | null>(null);
  // «read» arranca marcado si la persona eligió pedir siempre confirmación de lectura (Configuración → General).
  const [trackingState, setTrackingState] = useState(() => ({ delivery: false, read: useMailStore.getState().pedirLecturaSiempre, noReactions: false }));
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [showDirectoryPicker, setShowDirectoryPicker] = useState(false);
  const [directoryPickerTarget, setDirectoryPickerTarget] = useState<'to' | 'cc' | 'bcc'>('to');
  const [signatureHtml, setSignatureHtml] = useState(estadoPrevio?.signatureHtml ?? '');
  const [quotedHtml, setQuotedHtml] = useState(estadoPrevio?.quotedHtml ?? '');  // Contenido citado (reply/forward) — se renderiza DESPUES de la firma
  const [showSendDropdown, setShowSendDropdown] = useState(false);
  const [encrypt, setEncrypt] = useState(false);
  const [secureEnabled, setSecureEnabled] = useState(false);
  useEffect(() => {
    api.get('/mail/secure/config')
      .then((r) => setSecureEnabled(!!(r as { enabled?: boolean } | null)?.enabled))
      .catch(() => {
        /* sin cifrado configurado: la casilla simplemente no se ofrece */
      });
  }, []);
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
      Image.configure({ inline: true, allowBase64: true, resize: OPCIONES_RESIZE }),
      Table.configure({ resizable: true }),
      TableRow,
      TableCell,
      TableHeader,
      Subscript,
      Superscript,
      Placeholder.configure({ placeholder: '' }),
      TextAlign.configure({ types: ['heading', 'paragraph'] }),
      TextStyle, Color, FontFamily, FontSize, Highlight, FormatoParrafo,
    ],
    content: '',
    editorProps: {
      attributes: {
        class: 'outline-none px-6 py-2 text-[14px] leading-[22px] text-[#323130]',
        // Corrector del navegador; el idioma (atributo lang) lo pone useIdiomaOrtografia.
        spellcheck: 'true',
        style: 'font-family: Calibri, Segoe UI, sans-serif;',
      },
      handlePaste: (view, event) => pegarImagenes(view, event),
      transformPastedHTML: (html) => quitarImagenesLocales(html, showToast),
      handleDrop: (view, event, slice, moved) => soltarImagenes(view, event, slice, moved),
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
    // No duplicar: si el cuerpo ya trae la firma (p.ej. un borrador antiguo
    // guardado con la firma incrustada), no la reagregamos.
    const sigBlock = (signatureHtml && !body.includes('email-signature'))
      ? '<div class="email-signature" style="margin-top:12px;color:#605e5c">' + signatureHtml + '</div>'
      : '';
    // 2026-08-31: respetar la posicion de firma elegida (SignatureManager ->
    // localStorage). 'bottom' = al pie (tras el texto citado); 'before_quote'
    // (por defecto) = antes del texto citado, comportamiento historico.
    let posBottom = false;
    try { posBottom = JSON.parse(localStorage.getItem('maquita_sig_settings') || '{}').position === 'bottom'; } catch { /* sin config */ }
    let html = body;
    if (posBottom) {
      if (quotedHtml) html += quotedHtml;
      html += sigBlock;
    } else {
      html += sigBlock;
      if (quotedHtml) html += quotedHtml;
    }
    return html;
  }, [editor, signatureHtml, quotedHtml]);


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
    // La ventana vuelve de estar minimizada: los campos ya salieron del estado guardado;
    // solo falta devolver el texto al editor.
    if (estadoPrevio) {
      if (editor && !initializedRef.current) {
        initializedRef.current = true;
        editor.commands.setContent(estadoPrevio.cuerpoHtml || '<p></p>');
        cuerpoRef.current = editor.getHTML();
        setTimeout(() => { initializingRef.current = false; }, 500);
      }
      return;
    }
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
      } catch {
        /* ventana privada o almacenamiento lleno: la firma se vuelve a pedir al servidor */
      }

      let content = '';
      if (win.mode === 'new' && win.data.html_body) {
        // Editando un borrador: quitamos la firma incrustada (de borradores
        // guardados antes de este fix) para que NO se distorsione en el editor
        // ni se duplique; se re-aplica aparte, editable, mas abajo.
        const sinFirma = win.data.html_body.replace(/<div class="email-signature"[\s\S]*$/i, '');
        // 2026-09-16: si el borrador era una respuesta, la cita vuelve a su sitio
        // (fuera del editor y despues de la firma). Antes entraba entera al editor:
        // se deformaba y la firma quedaba al final de todo.
        const partes = separarCitado(sinFirma);
        content = partes.cuerpo || '<p></p>';
        if (partes.citado) setQuotedHtml(partes.citado);
        if (sig) setSignatureHtml(sig);
        // Los archivos guardados con el borrador vuelven al redactor.
        if (win.draftUid && win.data.adjuntos_borrador?.length) {
          // Hasta que termine la descarga, los guardados conservan los adjuntos del borrador
          // en el servidor (05/11/2026; antes el primer autoguardado los perdía).
          adjuntosEnCargaRef.current = true;
          cargarAdjuntosDelBorrador(win.draftUid, win.data.adjuntos_borrador).then(cargados => {
            if (!cargados.length) return;
            setAttachments(prev => [...prev, ...cargados]);
            huellaGuardadaRef.current = huellaAdjuntos(cargados);
          }).finally(() => { adjuntosEnCargaRef.current = false; });
        }
      } else if (win.mode === 'new') {
        // Parrafo vacio, no '<p><br></p>': ese <br> es un nodo de verdad y el texto se escribia
        // detras, de modo que el mensaje salia con un salto de linea sobrante al principio.
        content = '<p></p>';
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
        // 2026-08-31 (#2): respetar la preferencia de firma en respuestas/reenvios
        // que SignatureManager guarda en localStorage. Fallback seguro: incluir.
        let _incluirFirma = true;
        try {
          const _cfg = JSON.parse(localStorage.getItem('maquita_sig_settings') || '{}');
          _incluirFirma = win.mode === 'forward'
            ? _cfg.include_in_forward !== false
            : _cfg.include_in_reply !== false;
        } catch { /* sin config -> incluir como antes */ }
        if (sig && _incluirFirma) setSignatureHtml(sig);
        // Smart Reply: prefill_body contiene el texto IA pre-generado
        content = win.data.prefill_body || '<p></p>';

      }
      editor?.commands.setContent(content);
      cuerpoRef.current = editor?.getHTML() || '';
      // Allow smart-compose after init is done
      setTimeout(() => { initializingRef.current = false; }, 500);
    };
    if (editor && !initializedRef.current) { initializedRef.current = true; init(); }
  }, [editor]);

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

  // Guardado del borrador y conservación de lo escrito al minimizar (useRedaccionPersistente.ts).
  const { saveDraft, cuerpoRef, huellaGuardadaRef, adjuntosEnCargaRef, descartarBorrador } = useRedaccionPersistente(win, editor, estadoPrevio, {
    to, cc, bcc, subject, showCc, showBcc, fromEmail, quotedHtml, signatureHtml, attachments,
  });

  // Un destinatario movido a CC/CCO desde el menú del chip: mostrar ese campo.
  React.useEffect(() => {
    const h = (e: Event) => {
      const campo = (e as CustomEvent<string>).detail;
      if (campo === 'cc') setShowCc(true);
      if (campo === 'bcc') setShowBcc(true);
    };
    window.addEventListener(EVENTO_MOSTRAR_CAMPO, h);
    return () => window.removeEventListener(EVENTO_MOSTRAR_CAMPO, h);
  }, []);

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
    const attachMailHandler = () => setMostrarSelectorCorreo(true);
    const draftHandler = () => saveDraft();
    const ccHandler = () => setShowCc(true);
    const bccHandler = () => setShowBcc(true);
    // Firma elegida en el menu del Ribbon: la mostramos abajo (editable),
    // reemplazando la actual. No se inserta en el editor (evita duplicados).
    const sigHandler = (e: Event) => { setSignatureHtml((e as CustomEvent<string>).detail ?? ''); };
    window.addEventListener('compose-attach', attachHandler);
    window.addEventListener('compose-attach-cloud', attachCloudHandler);
    window.addEventListener(EVENTO_ADJUNTAR_CORREO, attachMailHandler);
    window.addEventListener('compose-save-draft', draftHandler);
    window.addEventListener('compose-show-cc', ccHandler);
    window.addEventListener('compose-show-bcc', bccHandler);
    window.addEventListener('compose-insert-signature', sigHandler);
    return () => {
      useMailStore.getState().setActiveEditor(null);
      window.removeEventListener('compose-attach', attachHandler);
      window.removeEventListener('compose-attach-cloud', attachCloudHandler);
      window.removeEventListener(EVENTO_ADJUNTAR_CORREO, attachMailHandler);
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
    // Un correo con solo adjuntos también se guarda (revisión 07/11/2026).
    const hasContent = !!(to || subject || (editor && editor.getText().trim()) || attachments.length);
    const cerrar = () => {
      // Destruir editor antes de cerrar para evitar HTML residual
      if (editor && !editor.isDestroyed) editor.commands.clearContent();
      closeCompose(win.id);
    };
    if (hasContent) {
      // Auto-guardar borrador al cerrar (sin diálogo intrusivo). Si el servidor no lo guardó
      // (sin red, error), la ventana NO se cierra: cerrarla borraría también la copia local
      // y la persona perdería lo escrito creyendo que quedó en Borradores.
      const guardado = await saveDraft();
      if (!guardado) {
        showToast('No se pudo guardar el borrador (revise la conexión). La ventana sigue abierta para que no pierda lo escrito.',
          { label: 'Cerrar sin guardar', onClick: cerrar }, { fijo: true });
        return;
      }
      showToast('Borrador guardado en «Borradores»');
    }
    cerrar();
  }, [to, subject, editor, attachments.length, saveDraft, win.id, closeCompose]);

  // «Cancelar y volver al correo» de la ventana emergente (/mensaje, 09/11/2026): la barra está
  // fuera de este componente y pide el cierre por evento; se cierra igual que la X (guarda si hay algo).
  useEffect(() => {
    const alCerrar = (e: Event) => {
      const id = (e as CustomEvent<{ id?: string }>).detail?.id;
      if (!id || id === win.id) void handleClose();
    };
    window.addEventListener('compose-cerrar', alCerrar);
    return () => window.removeEventListener('compose-cerrar', alCerrar);
  }, [handleClose, win.id]);

  // Papelera «Descartar» (07/11/2026): cierra SIN guardar y borra el borrador.
  // Revisión 07/11/2026: en vez de un cuadro de confirmación, aviso con «Deshacer» durante 5 s;
  // el borrador se conserva ese tiempo y, si no se deshace, se borra. Si el borrado falla, se avisa.
  const handleDescartar = useCallback(async () => {
    const hayAlgo = !!(to || subject || (editor && editor.getText().trim()) || attachments.length);
    if (autosaveTimer.current) clearInterval(autosaveTimer.current);
    const borrar = async () => {
      try {
        await descartarBorrador();
        window.dispatchEvent(new CustomEvent('refresh-messages'));
      } catch {
        showToast('No se pudo borrar el borrador del servidor: sigue en Borradores.');
      }
    };
    if (!hayAlgo) {
      closeCompose(win.id);
      await borrar();
      return;
    }
    const lista = (s: string) => s.split(/[,;]/).map(x => x.trim()).filter(Boolean);
    const foto = {
      to: lista(to), cc: lista(cc), bcc: lista(bcc), subject,
      html: (editor && !editor.isDestroyed ? editor.getHTML() : cuerpoRef.current) + (quotedHtml || ''),
    };
    const guardado = await saveDraft();
    const uid = useMailStore.getState().composeWindows.find(w => w.id === win.id)?.draftUid ?? win.draftUid;
    if (editor && !editor.isDestroyed) editor.commands.clearContent();
    closeCompose(win.id);
    let deshecho = false;
    const temporizador = setTimeout(() => { if (!deshecho) void borrar(); }, 5500);
    showToast('Mensaje descartado', {
      label: 'Deshacer',
      onClick: async () => {
        deshecho = true;
        clearTimeout(temporizador);
        let adjuntos: AttachmentInfo[] = [];
        if (guardado && uid) {
          try { adjuntos = ((await api.get<{ attachments?: AttachmentInfo[] }>(`/mail/message/Drafts/${uid}`)).attachments) || []; }
          catch { /* se reabre sin adjuntos */ }
        }
        useMailStore.getState().openCompose('new', {
          to: foto.to, cc: foto.cc, bcc: foto.bcc, subject: foto.subject, text_body: '', html_body: foto.html || '<p></p>',
          in_reply_to: win.data.in_reply_to, references: win.data.references,
          draft_uid: guardado && uid ? uid : null, adjuntos_borrador: adjuntos,
        });
      },
    });
  }, [to, cc, bcc, subject, quotedHtml, editor, attachments.length, closeCompose, win.id, win.draftUid, win.data.in_reply_to, win.data.references, descartarBorrador, saveDraft, cuerpoRef]);

  // Convertir File a base64 para enviar adjuntos al backend

  // handleSend with 5-second undo  MUST be defined before keyboard useEffect
  const enviarUnaVez = useCallback(async () => {
    if (encrypt) {
      const recipients = to.split(',').map(x => x.trim()).filter(Boolean);
      if (!recipients.length) { setError('Ingresa un destinatario'); return; }
      const malas = direccionesInvalidas(recipients);
      if (malas.length) {
        setError(malas.length === 1
          ? `«${malas[0]}» no es una dirección de correo válida`
          : `Estas direcciones no son válidas: ${malas.join(', ')}`);
        return;
      }
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
      } catch (err: unknown) {
        setSending(false);
        const m = err instanceof Error ? err.message : '';
        if (m.includes('413')) setError(`El correo supera el tamaño máximo (${MAX_ATTACH_MB} MB). Reduce los adjuntos.`);
        else setError('No se pudo enviar cifrado: ' + m);
      }
      return;
    }
    const recipients = to.split(',').map(s => s.trim()).filter(Boolean);
    if (!recipients.length) { setError('Ingresa un destinatario'); return; }
    // Sin esto, una direccion mal escrita arrancaba la cuenta atras igualmente y el correo se
    // daba por enviado hacia algo que no existe.
    const otras = [cc, bcc].join(',').split(',').map(s => s.trim()).filter(Boolean);
    const invalidas = direccionesInvalidas([...recipients, ...otras]);
    if (invalidas.length) {
      setError(invalidas.length === 1
        ? `«${invalidas[0]}» no es una dirección de correo válida`
        : `Estas direcciones no son válidas: ${invalidas.join(', ')}`);
      return;
    }
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
    let dlpReason = '';
    try {
      const dlpCc = cc ? cc.split(',').map(s => s.trim()).filter(Boolean) : [];
      const dlpBcc = bcc ? bcc.split(',').map(s => s.trim()).filter(Boolean) : [];
      const dlp = await api.post('/mail/dlp/check', { subject, html_body: getFullHtml(), text_body: '', to: recipients, cc: dlpCc, bcc: dlpBcc });
      if (dlp && Array.isArray(dlp.findings) && dlp.findings.length) {
        const tipos = dlp.findings.map((x: HallazgoDlp) => '\u2022 ' + x.label).join('\n');
        if (dlp.action === 'block') {
          const externos = Array.isArray(dlp.external) && dlp.external.length ? '\n\nDestinatarios externos:\n' + dlp.external.join(', ') : '';
          if (dlp.can_override) {
            const motivo = window.prompt('\uD83D\uDD12 Protecci\u00f3n de datos: este correo a destinatarios EXTERNOS contiene:\n' + tipos + externos + '\n\nComo administrador puedes forzar el env\u00edo. Escribe el motivo (queda registrado) o cancela:');
            if (!motivo || !motivo.trim()) return;
            dlpOverride = true;
            dlpReason = motivo.trim();
          } else {
            window.alert('\uD83D\uDD12 Env\u00edo bloqueado por Protecci\u00f3n de datos.\n\nEste correo a destinatarios EXTERNOS contiene:\n' + tipos + externos + '\n\nQuita esos datos para poder enviarlo o solicita autorizaci\u00f3n a Tecnolog\u00eda.');
            return;
          }
        }
        if (dlp.action === 'warn') {
          const ok = window.confirm('\u26A0\uFE0F Atenci\u00f3n: este correo contiene datos sensibles:\n\n' + tipos + '\n\n\u00bfEnviar de todas formas?');
          if (!ok) return;
          dlpOverride = true;
        }
      }
    } catch { /* si DLP no responde, no bloqueamos el env\u00edo */ }
    // UID del borrador VIGENTE (05/11/2026): `win.draftUid` es el de cuando se abrió la ventana;
    // los autoguardados lo van cambiando y con el viejo el envío no borraba el borrador.
    const draftUidVigente = useMailStore.getState().composeWindows.find(w => w.id === win.id)?.draftUid ?? win.draftUid;
    const sendPayload = {
      from_email: fromEmail || undefined,
      to: recipients,
      cc: cc ? cc.split(',').map(s => s.trim()).filter(Boolean) : undefined,
      bcc: bcc ? bcc.split(',').map(s => s.trim()).filter(Boolean) : undefined,
      subject, html_body: getFullHtml(), text_body: '',
      sensitivity: sensitivity || undefined,
      in_reply_to: win.data.in_reply_to || '', references: win.data.references || '',
      attachments: await Promise.all(
        attachments.filter(a => a.file).map(async (a) => ({
          filename: a.name,
          content_b64: await readFileAsBase64(a.file!),
          content_type: a.type || 'application/octet-stream',
        }))
      ),
      draft_uid: draftUidVigente,
      dlp_override: dlpOverride,
      dlp_reason: dlpReason || undefined,
      request_read_receipt: trackingState.read,
      request_delivery_receipt: trackingState.delivery,
      importance,
    };
    const savedData = { mode: win.mode, data: { ...win.data, to: recipients, subject, html_body: getFullHtml(), text_body: '' } };
    const winId = win.id;
    closeCompose(winId);
    const SEGUNDOS_PARA_ARREPENTIRSE = 5;
    let remaining = SEGUNDOS_PARA_ARREPENTIRSE;

    // El correo se guarda en la cola de salida ANTES de empezar la cuenta atrás, retenido hasta
    // que esta venza. Así deja de vivir solo en memoria: si la pestaña se cierra durante esos
    // segundos, el correo sigue ahí y sale al volver a abrir, en lugar de perderse sin aviso.
    const guardadoEnCola = addToOutbox({
      to: sendPayload.to, cc: sendPayload.cc, bcc: sendPayload.bcc,
      subject: sendPayload.subject, html_body: sendPayload.html_body, text_body: sendPayload.text_body,
      in_reply_to: sendPayload.in_reply_to, references: sendPayload.references,
      attachments: sendPayload.attachments,
      request_read_receipt: sendPayload.request_read_receipt,
      request_delivery_receipt: sendPayload.request_delivery_receipt,
      importance: sendPayload.importance,
    }, { retenidoHasta: Date.now() + SEGUNDOS_PARA_ARREPENTIRSE * 1000 })
      .catch(() => null); // Si no se pudo guardar, el envío sigue su curso como antes.

    /** Saca el correo de la cola: se va a enviar ahora, o la persona se ha arrepentido.
     *  Devuelve `false` solo si el correo sigue en la cola y hay que dejárselo a ella. */
    const soltarDeLaCola = async (): Promise<boolean> => {
      const id = await guardadoEnCola;
      if (!id) return true; // Nunca llegó a guardarse: el envío va por el camino de siempre.
      try {
        await removeFromOutbox(id);
        window.dispatchEvent(new CustomEvent('outbox-cambio'));
        return true;
      } catch {
        return false;
      }
    };

    const toastId = showToast(`Enviando en ${remaining}s...`, { label: 'Deshacer', onClick: () => {
      const p = pendingSendMap.get(winId); if (p) { clearTimeout(p.timerId); clearInterval(p.intervalId); pendingSendMap.delete(winId); }
      void soltarDeLaCola();
      dismissToast(toastId); useMailStore.getState().openCompose(savedData.mode, savedData.data); showToast('Envío cancelado');
    }});
    // Repintar el aviso en cada segundo: sin esto el contador se queda clavado en 5s y la
    // persona no sabe cuánto le queda para arrepentirse.
    const intervalId = setInterval(() => {
      remaining--;
      if (remaining <= 0) return;
      updateToast(toastId, `Enviando en ${remaining}s...`);
    }, 1000);
    const timerId = setTimeout(async () => {
      // Vencida la cuenta atrás, el correo deja de estar retenido: o se envía ahora, o se
      // vuelve a encolar como pendiente unas líneas más abajo (sin red o con el servidor caído).
      //
      // Si NO se ha podido sacar de la cola, no se envía por aquí: sigue guardado y lo entrega
      // la cola, una sola vez. Enviarlo igualmente lo mandaría dos veces.
      if (!(await soltarDeLaCola())) {
        clearInterval(intervalId); pendingSendMap.delete(winId); dismissToast(toastId);
        const id = await guardadoEnCola;
        if (id) await updateOutboxStatus(id, 'pending').catch(() => {});
        window.dispatchEvent(new CustomEvent('outbox-cambio'));
        void syncOutbox();
        showToast('El correo quedó en la cola de salida y se enviará en un momento.');
        return;
      }
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
            importance: sendPayload.importance,
          });
          window.dispatchEvent(new CustomEvent('outbox-cambio'));
          showToast('Sin internet: el correo quedó en cola y se enviará solo al volver la conexión (aunque cierres la app).');
        } catch { showToast('Error al guardar correo offline'); }
        return;
      }
      clearInterval(intervalId); pendingSendMap.delete(winId); dismissToast(toastId);
      try { await enviarCorreo(sendPayload); showToast('Mensaje enviado'); window.dispatchEvent(new CustomEvent('refresh-messages'));
      } catch (err: unknown) {
        const errMsg = err instanceof Error ? err.message : 'Error al enviar';
        const bloqueo = leerBloqueoSensibilidad(errMsg);
        if (bloqueo) {
          const motivo = pedirMotivoSensibilidad(bloqueo);
          if (motivo) {
            try {
              await enviarCorreo({ ...sendPayload, dlp_override: true, dlp_reason: motivo });
              showToast('Mensaje enviado'); window.dispatchEvent(new CustomEvent('refresh-messages'));
              return;
            } catch (err2: unknown) {
              showToast(textoErrorEnvio(err2 instanceof Error ? err2.message : ''), undefined, { fijo: true });
            }
          }
        } else if (errMsg.includes('dlp_blocked')) {
          let tipos = '';
          try {
            const d = JSON.parse(errMsg) as { findings?: HallazgoDlp[] };
            tipos = (d.findings || []).map((x) => '\u2022 ' + x.label).join('\n');
          } catch {
            /* el servidor no mando el detalle: se avisa igual, sin la lista */
          }
          window.alert('\uD83D\uDD12 Env\u00edo bloqueado por Protecci\u00f3n de datos (revisi\u00f3n de adjuntos).\n\n' + tipos + '\n\nQuita esos datos de los adjuntos o solicita autorizaci\u00f3n a Tecnolog\u00eda.');
        } else if (errMsg.includes('413')) {
          showToast(`No se envió: el correo supera el tamaño máximo (${MAX_ATTACH_MB} MB). Quite algún adjunto.`, undefined, { fijo: true });
        } else if (errMsg.includes('Session expired') || errMsg.includes('SMTP expirada') || errMsg.includes('401')) {
          showToast('No se envió: su sesión caducó. El correo se volvió a abrir; copie el texto, cierre sesión y vuelva a entrar.', undefined, { fijo: true });
        } else if (!navigator.onLine || /Failed to fetch|NetworkError|Sin conexion|offline|50[234]|timeout|abort/i.test(errMsg)) {
          // T-35: el servidor no responde o se fue la red a mitad del envío: a la cola persistente, nunca se pierde
          try {
            await addToOutbox({
              to: sendPayload.to, cc: sendPayload.cc, bcc: sendPayload.bcc, subject: sendPayload.subject, html_body: sendPayload.html_body,
              text_body: sendPayload.text_body, in_reply_to: sendPayload.in_reply_to, references: sendPayload.references,
              attachments: sendPayload.attachments, request_read_receipt: sendPayload.request_read_receipt, request_delivery_receipt: sendPayload.request_delivery_receipt,
              importance: sendPayload.importance,
            });
            window.dispatchEvent(new CustomEvent('outbox-cambio'));
            showToast(navigator.onLine ? 'El servidor no responde: el correo quedó en cola y se enviará solo al restablecerse.' : 'Sin internet: el correo quedó en cola y se enviará solo al volver la conexión.');
            return;
          } catch { /* si no se pudo encolar, se reabre el borrador abajo */ }
          showToast('No se pudo enviar ni guardar en la cola de salida. El correo se volvió a abrir; inténtelo de nuevo en unos minutos.', undefined, { fijo: true });
          console.warn('[correo] detalle del error al enviar:', errMsg);
        } else {
          showToast(textoErrorEnvio(errMsg), undefined, { fijo: true });
        }
        useMailStore.getState().openCompose(savedData.mode, savedData.data);
      }
    }, SEGUNDOS_PARA_ARREPENTIRSE * 1000);
    pendingSendMap.set(winId, { timerId, toastId, intervalId });
  }, [to, cc, bcc, subject, editor, win, trackingState, importance, closeCompose, attachments, encrypt]);

  // 2026-09-16: un doble clic en Enviar (o Ctrl+Enter repetido) disparaba dos
  // envios, porque el boton solo se bloqueaba despues de la comprobacion DLP.
  // El candado es sincrono (ref), asi que el segundo clic no llega a enviar.
  const enviandoRef = useRef(false);
  const handleSend = useCallback(async () => {
    if (enviandoRef.current) return;
    enviandoRef.current = true;
    try {
      await enviarUnaVez();
    } finally {
      enviandoRef.current = false;
    }
  }, [enviarUnaVez]);

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

  // Keyboard shortcuts: Ctrl+Enter envía; Esc solo cierra el desplegable de Enviar
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); handleSend(); }
      if (e.key === 'Escape') {
        // No cerrar compose si hay un dropdown/popup abierto (tabla, color, etc.)
        const hasOpenPopup = document.querySelector('.tippy-box, [data-tippy-root], [role="listbox"], .tiptap-menu, [data-radix-popper-content-wrapper], [role="dialog"], [role="menu"]');
        if (hasOpenPopup) { e.stopPropagation(); return; }
        // Si hay send dropdown abierto, cerrarlo en vez de cerrar compose
        if (showSendDropdown) { setShowSendDropdown(false); e.preventDefault(); return; }
        // Esc ya NO cierra la redacción: se pulsaba para cerrar las sugerencias de contactos
        // y se cerraba el correo entero (Zimbra no cierra con Esc). Se cierra con su botón.
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [handleSend, handleClose, showSendDropdown]);

  // Se conserva para la cinta de redaccion; hoy esta accion la sirve la barra principal.
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const handleAttach = () => { fileInputRef.current?.click(); };

  // Rechaza ejecutables, scripts, .dat y similares antes de que entren al redactor.
  const agregarArchivos = (archivos: File[]) => {
    const { permitidos, aviso } = filtrarPeligrosos(archivos);
    if (aviso) showToast(aviso);
    if (!permitidos.length) return;
    setAttachments(prev => [...prev, ...permitidos.map(f => ({ name: f.name, size: f.size, type: f.type, file: f }))]);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;
    agregarArchivos(Array.from(files));
    e.target.value = '';
  };

  const adjuntarDesdeNube = (archivos: File[]) => { agregarArchivos(archivos); };

  // Correos elegidos en el selector: entran como .eml con su origen, igual que al arrastrarlos.
  const adjuntarCorreos = (correos: CorreoAAdjuntar[]) => {
    descargarCorreosComoEml(correos).then(({ cargados, fallidos }) => {
      if (cargados.length) setAttachments(prev => [...prev, ...cargados]);
      if (fallidos.length) showToast(`No se pudo adjuntar: ${fallidos.join(', ')}`);
    });
  };

  const removeAttachment = (idx: number) => {
    setAttachments(prev => prev.filter((_, i) => i !== idx));
  };

  //  Drag & Drop
  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current++;
    if (e.dataTransfer.types.includes("Files") || e.dataTransfer.types.includes(TIPO_ARRASTRE_CORREOS)) {
      setIsDragging(true);
      setArrastraImagenes(Array.from(e.dataTransfer.items || []).some(i => i.kind === 'file' && i.type.startsWith('image/')));
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const r = e.currentTarget.getBoundingClientRect();
    const dom = editor && !editor.isDestroyed ? editor.view.dom : null;
    const borde = dom ? Math.min(Math.max(dom.getBoundingClientRect().top - r.top, 90), r.height - 90) : r.height / 2;
    setLimiteZona(borde);
    setZonaSoltar(e.clientY - r.top < borde ? 'adjuntar' : 'insertar');
  }, [editor]);

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
    // Correos arrastrados desde la lista: entran como adjuntos .eml.
    const correos = correosArrastrados(e.dataTransfer);
    if (correos.length) {
      descargarCorreosComoEml(correos).then(({ cargados, fallidos }) => {
        if (cargados.length) setAttachments(prev => [...prev, ...cargados]);
        if (fallidos.length) showToast(`No se pudo adjuntar: ${fallidos.join(', ')}`);
      });
      return;
    }
    let files = Array.from(e.dataTransfer.files || []);
    // Zona «Insertar en el texto»: las imágenes van dentro del cuerpo; el resto, como adjunto.
    const imagenes = files.filter(f => f.type.startsWith('image/'));
    if (imagenes.length && zonaSoltar === 'insertar' && editor && !editor.isDestroyed) {
      insertarImagenesEnTexto(editor.view, imagenes);
      files = files.filter(f => !f.type.startsWith('image/'));
    }
    // Imágenes soltadas sobre el texto: el editor ya las puso dentro; aquí se adjunta el resto.
    if ((e.nativeEvent as unknown as Record<string, boolean>)[IMAGENES_SOLTADAS_EN_TEXTO]) {
      files = files.filter(f => !f.type.startsWith('image/'));
    }
    if (files.length === 0) return;
    const { permitidos, aviso } = filtrarPeligrosos(files);
    if (aviso) showToast(aviso);
    if (!permitidos.length) return;
    setAttachments(prev => [...prev, ...permitidos.map(f => ({ name: f.name, size: f.size, type: f.type, file: f }))]);
  }, [zonaSoltar, editor]);

  // Se conserva para la cinta de redaccion; hoy esta accion la sirve la barra principal.
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
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

  // Se conserva para la cinta de redaccion; hoy esta accion la sirve la barra principal.
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
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

  //  «Mejorar redacción» y «Corregir ortografía»: asistente-redaccion/ (vista previa antes de aplicar,
  //  sobre la selección o todo el mensaje). Antes reemplazaba el texto sin mostrar la propuesta.

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

  // Corrector ortográfico: español de Ecuador por defecto; inglés si el correo o el texto lo están.
  const ortografia = useIdiomaOrtografia(editor, `ventana:${win.id}`, win.draftUid ? `borrador:${win.draftUid}` : null, quotedHtml);

  //  VM 170: Smart Compose — autocompletado IA
  const [composeSuggestion, setComposeSuggestion] = useState('');
  const [continuaPalabra, setContinuaPalabra] = useState(false);
  const [composingSuggestion, setComposingSuggestion] = useState(false);
  // Se conserva para la cinta de redaccion; hoy esta accion la sirve la barra principal.
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const composeDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Se conserva para la cinta de redaccion; hoy esta accion la sirve la barra principal.
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const smartComposeAbort = useRef<AbortController | null>(null);
  const initializingRef = useRef(true);

  // VM 170: Smart Compose — ON-DEMAND (boton), ya NO automatico (evita saturar el GPU)
  const requestSmartCompose = useCallback(async () => {
    if (!editor) return;
    const context = editor.getText();
    // Basta el comienzo de una palabra («Estimad», «Dear»). Solo se pide al pulsar el botón y
    // no mientras hay otra petición en curso, así que no satura la IA.
    if (context.trim().length < 4) { showToast('Escriba al menos unas letras para empezar'); return; }
    if (composingSuggestion) return;
    setComposingSuggestion(true);
    setComposeSuggestion('');
    try {
      const data = await api.post<{ suggestion: string; continua_palabra?: boolean }>('/ai/smart-compose',
        { context, subject, to, idioma: aTexto(ortografia.idioma) });
      if (data.suggestion) { setComposeSuggestion(data.suggestion); setContinuaPalabra(!!data.continua_palabra); }
      else showToast('La IA no devolvio una sugerencia');
    } catch { showToast('No se pudo generar (IA ocupada, reintenta)'); }
    finally { setComposingSuggestion(false); }
  }, [editor, subject, to, ortografia.idioma, composingSuggestion]);

  const acceptComposeSuggestion = useCallback(() => {
    if (composeSuggestion && editor) {
      if (esReescritura(editor.getText(), composeSuggestion)) {
        // La IA devolvió el correo entero: reemplaza el texto (la firma y el citado van aparte).
        editor.chain().focus().setContent(textoAParrafos(composeSuggestion)).run();
        showToast('Texto reemplazado por la versión de la IA');
      } else {
        // Al final del texto, no donde quedó el cursor; unida a la palabra a medias o con espacio.
        insertarContinuacion(editor, composeSuggestion, continuaPalabra);
        showToast('Sugerencia agregada al final');
      }
      setComposeSuggestion('');
    }
  }, [editor, composeSuggestion, continuaPalabra]);
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
  // Se conserva para la cinta de redaccion; hoy esta accion la sirve la barra principal.
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const handleFormatPaint = useCallback((marks: string[]) => {
    showToast(marks.length ? `Formato copiado: ${marks.join(', ')}` : 'Seleccione texto con formato');
  }, []);


  const handleTrackingChange = useCallback((t: { delivery: boolean; read: boolean; noReactions: boolean }) => {
    setTrackingState(t);
  }, []);

  // Importancia elegida en la cinta para ESTA redacción (con varias abiertas, cada una la suya).
  useEffect(() => {
    const alCambiar = (e: Event) => {
      const d = (e as CustomEvent<{ editor: unknown; valor: Importancia }>).detail;
      if (d && d.editor === editor) setImportance(d.valor);
    };
    window.addEventListener(EVENTO_IMPORTANCIA, alCambiar);
    return () => window.removeEventListener(EVENTO_IMPORTANCIA, alCambiar);
  }, [editor]);

  // Schedule send
  const handleScheduleSend = useCallback(() => {
    const now = new Date(); now.setHours(now.getHours() + 1);
    setScheduleDate(now.toISOString().slice(0, 16));
    setShowScheduleModal(true);
  }, []);

  const handleConfirmSchedule = useCallback(async () => {
    if (!scheduleDate) { showToast('Selecciona fecha y hora'); return; }
    // El envío programado del servidor todavía no admite adjuntos: los descartaba sin avisar
    // y el correo salía horas después sin ellos. Mientras tanto, se impide.
    if (attachments.length > 0) {
      showToast('Por ahora no se pueden programar correos con adjuntos. Envíelo directamente con «Enviar».', undefined, { fijo: true });
      return;
    }
    const recipients = to.split(',').map(s => s.trim()).filter(Boolean);
    if (!recipients.length) { setError('Ingresa un destinatario'); return; }
    // Programar un envio a una direccion invalida es peor: el fallo aparece horas despues.
    const malasProgramado = direccionesInvalidas(recipients);
    if (malasProgramado.length) {
      setError(malasProgramado.length === 1
        ? `«${malasProgramado[0]}» no es una dirección de correo válida`
        : `Estas direcciones no son válidas: ${malasProgramado.join(', ')}`);
      return;
    }
    try {
      await api.post('/mail/schedule', {
        to: recipients, cc: cc ? cc.split(',').map(s => s.trim()).filter(Boolean) : [],
        bcc: bcc ? bcc.split(',').map(s => s.trim()).filter(Boolean) : [],
        subject, html_body: getFullHtml(), text_body: '',
        in_reply_to: win.data.in_reply_to || '', references: win.data.references || '',
        scheduled_at: new Date(scheduleDate).toISOString(),
        request_read_receipt: trackingState.read, request_delivery_receipt: trackingState.delivery,
        importance,
      });
      closeCompose(win.id); setShowScheduleModal(false);
      showToast(`Envío programado para ${new Date(scheduleDate).toLocaleString('es-EC')}. Puede verlo o cambiarlo en «Programados».`);
      window.dispatchEvent(new CustomEvent('programados-cambio'));
    } catch { showToast('No se pudo programar el envío. Inténtelo de nuevo.', undefined, { fijo: true }); }
  }, [to, cc, bcc, subject, editor, win, scheduleDate, trackingState, importance, closeCompose, attachments]);

  useEffect(() => {
    const scheduleHandler = () => handleScheduleSend();
    const reviewHandler = () => handleReviewEditor();
    const accessibilityHandler = () => handleCheckAccessibility();
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
    window.addEventListener('compose-suggest-subject', suggestSubjectHandler);
    window.addEventListener('compose-accept-suggestion', acceptComposeHandler);
    window.addEventListener('compose-dictate', dictateHandler);
    window.addEventListener('compose-open-apps', openAppsHandler);
    window.addEventListener('compose-tracking-change', trackingHandler as EventListener);

    return () => {
      window.removeEventListener('compose-schedule-send', scheduleHandler);
      window.removeEventListener('compose-review-editor', reviewHandler);
      window.removeEventListener('compose-check-accessibility', accessibilityHandler);
      window.removeEventListener('compose-suggest-subject', suggestSubjectHandler);
      window.removeEventListener('compose-accept-suggestion', acceptComposeHandler);
      window.removeEventListener('compose-dictate', dictateHandler);
      window.removeEventListener('compose-open-apps', openAppsHandler);
      window.removeEventListener('compose-tracking-change', trackingHandler as EventListener);
    };
  }, [handleScheduleSend, handleReviewEditor, handleCheckAccessibility, handleDictate, handleOpenApps, handleTrackingChange, handleSuggestSubject, acceptComposeSuggestion]);

  if (!editor) return null;

  return (
    <div className="flex-1 flex flex-col bg-white overflow-hidden relative"
      onDragEnter={handleDragEnter}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}>
      {/* Zona para soltar archivos (07/11/2026, al estilo Outlook pero más ligera) */}
      {isDragging && <ZonaSoltarArchivos conImagenes={arrastraImagenes} zona={zonaSoltar} limite={limiteZona} />}
      {/* Ribbon (tabs + toolbar) */}
      {/* Ribbon rendered in main Toolbar */}

      {/* Hidden file input */}
      <input ref={fileInputRef} type="file" multiple className="hidden" onChange={handleFileSelect} />
      {mostrarNube && <SelectorArchivosNube onCerrar={() => setMostrarNube(false)} onElegir={adjuntarDesdeNube} />}
      {mostrarSelectorCorreo && <SelectorCorreoAdjunto onCerrar={() => setMostrarSelectorCorreo(false)} onElegir={adjuntarCorreos} />}

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
              aria-label="Opciones de envío" title="Opciones de envío"
              aria-haspopup="menu" aria-expanded={showSendDropdown}
              className="h-[32px] min-w-[28px] px-[8px] bg-[#0078d4] text-white rounded-r-[4px] border-l border-[#ffffff40] hover:bg-[#106ebe] transition-colors"
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
          {/* Este botón NO descarta: guarda en Borradores y cierra. Antes decía «Descartar» con
              icono de papelera y la persona creía haber borrado un correo que seguía en Borradores. */}
          <BotonDescartarRedaccion onDescartar={handleDescartar} />
          <button onClick={handleClose} title="Cerrar (se guarda en Borradores)" aria-label="Cerrar (se guarda en Borradores)"
            className="w-[32px] h-[32px] rounded-[3px] flex items-center justify-center text-[#605e5c] hover:bg-[#f3f2f1] hover:text-[#323130] transition-colors">
            <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
          <button onClick={() => minimizeCompose(win.id)} title="Minimizar" aria-label="Minimizar"
            className="w-[32px] h-[32px] rounded-[3px] flex items-center justify-center text-[#605e5c] hover:bg-[#f3f2f1] hover:text-[#323130] transition-colors">
            <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
            </svg>
          </button>
        </div>
      </div>

      {/* Remitente (solo si hay más de una cuenta) */}
      <SelectorRemitente valor={fromEmail} onChange={setFromEmail} />

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
        {/* En paneles estrechos (celular, zoom 150 %) los controles bajan a una segunda fila en
            vez de recortarse por la derecha (revisión 04/11/2026, n.º 6). */}
        <div className="flex flex-wrap items-center">
          <input value={subject} onChange={e => { setSubject(e.target.value); updateComposeData(win.id, { subject: e.target.value }); }}
            placeholder="Agregar un asunto" lang={ortografia.idioma} spellCheck
            className="flex-[1_1_14rem] min-w-0 text-[15px] px-4 py-2.5 outline-none text-[#323130] placeholder-[#605e5c]"
            style={{ fontFamily: 'Segoe UI, Calibri, sans-serif' }} />
          <div className="flex items-center flex-wrap gap-y-1 pl-2 pb-1 sm:pb-0 ml-auto">
          <select value={sensitivity} onChange={e => setSensitivity(e.target.value)}
            title="Etiqueta de sensibilidad" aria-label="Etiqueta de sensibilidad"
            className="mr-2 text-[11px] px-1.5 py-1 rounded border border-[#edebe9] text-[#605e5c] bg-white outline-none">
            <option value="">Sensibilidad…</option>
            <option value="Publica">Pública</option>
            <option value="Interna">Interna</option>
            <option value="Confidencial">Confidencial</option>
            <option value="Restringida">Restringida</option>
          </select>
          <BotonAutocompletarIA onClick={requestSmartCompose} ocupado={composingSuggestion} />
          <button onClick={handleSuggestSubject} disabled={suggestingSubject}
            title="Sugerir asunto con IA"
            className="mr-2 px-2 py-1 text-[11px] text-[#0078d4] hover:bg-[#f3f2f1] rounded flex items-center gap-1 disabled:opacity-50 whitespace-nowrap">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0078d4" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" /></svg>
            Asunto
          </button>
          </div>
        </div>
      </div>

      {/* Adjuntos debajo del asunto y antes del texto, como Outlook (07/11/2026; antes iban al pie) */}
      <Attachments files={attachments} onRemove={removeAttachment} />

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
        .compose-editor-area .ProseMirror { min-height: 180px !important; height: auto !important; }
        /* Solo imágenes heredadas (firmas antiguas dentro del texto). Las pegadas o insertadas van
           envueltas en el marco redimensionable y conservan el tamaño que la persona les da. */
        .compose-editor-area .tiptap img:not([data-resize-wrapper] > img) {
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
      {/* Asistente IA: la franja solo aparece mientras genera o con una sugerencia pendiente */}
      <FranjaSugerenciaIA generando={composingSuggestion} sugerencia={composeSuggestion}
        onInsertar={acceptComposeSuggestion} onDescartar={() => setComposeSuggestion('')} />
      <div className="flex-1 overflow-y-auto compose-editor-area"
        onMouseDown={(e) => {
          // Clic en el espacio en blanco del cuerpo: el cursor va al final del texto.
          if (e.target === e.currentTarget) { e.preventDefault(); editor?.commands.focus('end'); }
        }}
        onPaste={(e) => { if (editor && !editor.isDestroyed) pegarImagenesFueraDelTexto(editor.view, e.nativeEvent); }}>
        <BarraImagen editor={editor} />
        <VistaPreviaRedaccion editor={editor} asunto={subject} activo={!win.minimized} />
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
        {/* 07/11/2026: no se modifica (antifraude) pero se puede resaltar/subrayar (CitaMarcable.tsx) */}
        {quotedHtml && <CitaMarcable html={quotedHtml} onCambiar={setQuotedHtml} />}
      </div>

      <IndicadorOrtografia idioma={ortografia.idioma} manual={ortografia.manual} onCambiar={ortografia.elegir} />


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
