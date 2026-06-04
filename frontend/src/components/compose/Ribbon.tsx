import { useMailStore } from "../../store/mailStore";
import React, { useState, useRef, useEffect, useLayoutEffect, type ReactNode } from 'react';
import { api } from '../../api/client';
import type { Editor } from '@tiptap/react';
import { showToast } from '../common/Toast';
import { createPortal } from 'react-dom';

type Tab = 'message' | 'insert' | 'format' | 'options';

type FormatPaintSnapshot = {
  marks: string[];
  color?: string;
  backgroundColor?: string;
  fontFamily?: string;
  fontSize?: string;
};

let formatPaintBuffer: FormatPaintSnapshot | null = null;

interface Props {
  editor: Editor;
  onAttach?: () => void;
  onShowCc?: () => void;
  onShowBcc?: () => void;
  showCc?: boolean;
  showBcc?: boolean;
  onImportanceChange?: (v: 'normal' | 'high' | 'low') => void;
  importance?: 'normal' | 'high' | 'low';
  onSaveDraft?: () => void;
  onInsertSignature?: (html?: string) => void;
  onDownloadDraft?: () => void;
  // Callbacks preparados para backends externos
  onDictate?: () => void;             // → VM 170 (ia-maquita) Whisper STT
  onScheduleSend?: () => void;        // → Backend webmail: programar envío
  onOpenApps?: () => void;            // → Futuro: Nextcloud/LibreOffice Online para ver archivos
  onReviewEditor?: () => void;        // → VM 170 (ia-maquita) revisión IA del texto
  onCheckAccessibility?: () => void;  // → VM 170 (ia-maquita) análisis accesibilidad IA
  onFormatPaint?: (marks: string[]) => void; // → Copiar formato entre selecciones
  onTrackingChange?: (tracking: { delivery: boolean; read: boolean; noReactions: boolean }) => void;
  onImproveWriting?: () => void;      // → VM 170 (ia-maquita) mejorar redacción con IA
}

export function Ribbon({ editor, onAttach, onShowCc, onShowBcc, showCc, showBcc, onImportanceChange, importance, onSaveDraft, onInsertSignature, onDownloadDraft, onDictate, onScheduleSend, onOpenApps, onReviewEditor, onCheckAccessibility, onFormatPaint, onTrackingChange, onImproveWriting }: Props) {
  const storeTab = useMailStore(s => s.composeRibbonTab);
  const [localTab, setLocalTab] = useState<Tab>('message');
  const tab = storeTab || localTab;
  const setTab = (t: Tab) => { setLocalTab(t); useMailStore.getState().setComposeRibbonTab(t); };
  const [collapsed, setCollapsed] = useState(false);

  const tabs: { id: Tab; label: string }[] = [
    { id: 'message', label: 'Mensaje' },
    { id: 'insert', label: 'Insertar' },
    { id: 'format', label: 'Aplicar formato al texto' },
    { id: 'options', label: 'Opciones' },
  ];

  return (
    <div className="shrink-0 bg-white select-none relative">
      {/* Tab bar hidden - managed by main Toolbar */}
      <div className="hidden">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-3 h-[28px] text-[12px] transition-colors relative top-[1px] ${
              tab === t.id
                ? 'bg-white text-[#323130] font-semibold border-t-[2px] border-x border-t-[#0078d4] border-x-[#edebe9] rounded-t-[3px]'
                : 'text-[#605e5c] hover:text-[#323130] hover:bg-[#e1dfdd] rounded-t-[3px]'
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {collapsed ? (
        <div className="flex items-center h-[36px] px-2 border-b border-[#edebe9] bg-white gap-[2px] ">
          <CollapsedRibbon editor={editor} onAttach={onAttach} onImportanceChange={onImportanceChange} importance={importance} />
        </div>
      ) : (
        <div className="flex items-stretch border-b border-[#edebe9] bg-[#f8f8f8] " style={{ height: '84px', overflow: 'visible' }}>
          {tab === 'message' && <MessageTab editor={editor} onAttach={onAttach} onImportanceChange={onImportanceChange} importance={importance} onSaveDraft={onSaveDraft} onInsertSignature={onInsertSignature} onDownloadDraft={onDownloadDraft} onDictate={onDictate} onOpenApps={onOpenApps} onReviewEditor={onReviewEditor} onCheckAccessibility={onCheckAccessibility} onImproveWriting={onImproveWriting} />}
          {tab === 'insert' && <InsertTab editor={editor} onAttach={onAttach} onInsertSignature={onInsertSignature} onOpenApps={onOpenApps} />}
          {tab === 'format' && <FormatTab editor={editor} onFormatPaint={onFormatPaint} />}
          {tab === 'options' && <OptionsTab editor={editor} onShowCc={onShowCc} onShowBcc={onShowBcc} showCc={showCc} showBcc={showBcc} onImportanceChange={onImportanceChange} importance={importance} onSaveDraft={onSaveDraft} onDownloadDraft={onDownloadDraft} onScheduleSend={onScheduleSend} onReviewEditor={onReviewEditor} onCheckAccessibility={onCheckAccessibility} onTrackingChange={onTrackingChange} />}
        </div>
      )}

      <button onClick={() => setCollapsed(!collapsed)} title={collapsed ? 'Expandir la cinta de opciones' : 'Contraer la cinta de opciones'}
        className="absolute right-[2px] top-[4px] w-[24px] h-[24px] rounded-[3px] flex items-center justify-center text-[#605e5c] hover:bg-[#e1dfdd] hover:text-[#323130] transition-colors z-20">
        <svg className="w-[12px] h-[12px]" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2.5}>
          {collapsed
            ? <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            : <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
          }
        </svg>
      </button>
    </div>
  );
}

/* ===== Helper: increase/decrease font size ===== */
const SIZES = [8,9,10,11,12,14,16,18,20,24,28,36,48,72];
function stepFontSize(editor: Editor, direction: 'up' | 'down') {
  const attrs = editor.getAttributes('textStyle');
  const current = parseInt(attrs.fontSize || '12');
  const idx = SIZES.indexOf(current);
  let next: number;
  if (idx === -1) {
    next = direction === 'up' ? SIZES.find(s => s > current) || 72 : [...SIZES].reverse().find(s => s < current) || 8;
  } else {
    next = direction === 'up' ? (SIZES[idx + 1] || 72) : (SIZES[idx - 1] || 8);
  }
  (editor.chain().focus() as any).setFontSize(next + 'px').run();
}

/* ===== Helper: clipboard operations ===== */
function getSelectedText(editor: Editor) {
  const { from, to } = editor.state.selection;
  return editor.state.doc.textBetween(from, to, '\n');
}

async function doCopy(editor: Editor) {
  const text = getSelectedText(editor);
  if (!text) {
    showToast('Selecciona texto para copiar');
    return false;
  }

  // Algunos navegadores bloquean portapapeles si la página no tiene permiso explícito.
  // Si falla aquí, no intentamos una alternativa insegura ni silenciosa.
  if (!navigator.clipboard?.writeText) {
    showToast('Este navegador no permite copiar desde la cinta');
    return false;
  }

  try {
    await navigator.clipboard.writeText(text);
    showToast('Texto copiado');
    return true;
  } catch {
    showToast('El navegador no permitió copiar el texto');
    return false;
  }
}

async function doCut(editor: Editor) {
  const copied = await doCopy(editor);
  if (!copied) return false;
  editor.chain().focus().deleteSelection().run();
  showToast('Texto cortado');
  return true;
}

async function doPaste(editor: Editor) {
  if (!navigator.clipboard?.readText) {
    showToast('Este navegador no permite pegar desde la cinta');
    return false;
  }

  try {
    const text = await navigator.clipboard.readText();
    if (!text) {
      showToast('El portapapeles está vacío');
      return false;
    }
    editor.chain().focus().insertContent(text).run();
    showToast('Texto pegado');
    return true;
  } catch {
    showToast('El navegador no permitió pegar el texto');
    return false;
  }
}

function captureFormatSnapshot(editor: Editor): FormatPaintSnapshot | null {
  const marks: string[] = [];
  if (editor.isActive('bold')) marks.push('bold');
  if (editor.isActive('italic')) marks.push('italic');
  if (editor.isActive('underline')) marks.push('underline');
  if (editor.isActive('strike')) marks.push('strike');
  if (editor.isActive('subscript')) marks.push('subscript');
  if (editor.isActive('superscript')) marks.push('superscript');

  const textStyle = editor.getAttributes('textStyle') || {};
  const snapshot: FormatPaintSnapshot = {
    marks,
    color: textStyle.color,
    backgroundColor: textStyle.backgroundColor,
    fontFamily: textStyle.fontFamily,
    fontSize: textStyle.fontSize,
  };

  if (!snapshot.marks.length && !snapshot.color && !snapshot.backgroundColor && !snapshot.fontFamily && !snapshot.fontSize) {
    return null;
  }

  return snapshot;
}

function applyFormatSnapshot(editor: Editor, snapshot: FormatPaintSnapshot) {
  const { from, to } = editor.state.selection;
  if (from === to) {
    showToast('Selecciona texto para aplicar el formato');
    return false;
  }

  let chain = editor.chain().focus();
  chain = chain.unsetAllMarks();

  if (snapshot.fontFamily) chain = (chain as any).setFontFamily(snapshot.fontFamily);
  if (snapshot.fontSize) chain = (chain as any).setFontSize(snapshot.fontSize);
  if (snapshot.color) chain = (chain as any).setColor(snapshot.color);
  if (snapshot.backgroundColor) chain = (chain as any).setHighlight(snapshot.backgroundColor);
  else chain = (chain as any).unsetHighlight();

  if (snapshot.marks.includes('bold')) chain = chain.toggleBold();
  if (snapshot.marks.includes('italic')) chain = chain.toggleItalic();
  if (snapshot.marks.includes('underline')) chain = (chain as any).toggleUnderline();
  if (snapshot.marks.includes('strike')) chain = chain.toggleStrike();
  if (snapshot.marks.includes('subscript')) chain = (chain as any).toggleSubscript();
  if (snapshot.marks.includes('superscript')) chain = (chain as any).toggleSuperscript();

  chain.run();
  return true;
}

function hasHighlight(editor: Editor) {
  return Boolean(editor.getAttributes('textStyle')?.backgroundColor);
}

/* ===== Helper: insert table with interactive grid ===== */
function insertTable(editor: Editor, rows: number = 2, cols: number = 2) {
  // Use TipTap Table extension if available
  if ((editor.commands as any).insertTable) {
    (editor.commands as any).insertTable({ rows, cols, withHeaderRow: true });
  } else {
    // Fallback: HTML insertion
    let html = '<table style="border-collapse:collapse;width:100%">';
    for (let r = 0; r < rows; r++) {
      html += '<tr>';
      for (let c = 0; c < cols; c++) {
        html += '<td style="border:1px solid #edebe9;padding:8px;min-width:60px">&nbsp;</td>';
      }
      html += '</tr>';
    }
    html += '</table><p></p>';
    editor.chain().focus().insertContent(html).run();
  }
}

/* ===== Table grid selector component ===== */
function TableGridSelector({ onSelect, onClose }: { onSelect: (rows: number, cols: number) => void; onClose: () => void }) {
  const [hoverRow, setHoverRow] = React.useState(0);
  const [hoverCol, setHoverCol] = React.useState(0);
  const maxRows = 6, maxCols = 6;
  return (
    <div style={{ position: 'absolute', left: 0, top: '100%', marginTop: 4, background: 'white', border: '1px solid #edebe9', borderRadius: 4, padding: 8, zIndex: 200, boxShadow: '0 4px 12px rgba(0,0,0,0.15)' }}
      onClick={e => e.stopPropagation()}>
      <div style={{ marginBottom: 6, fontSize: 11, color: '#605e5c', textAlign: 'center' }}>
        {hoverRow > 0 ? `${hoverRow} x ${hoverCol} tabla` : 'Selecciona tamano'}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${maxCols}, 20px)`, gap: 2 }}>
        {Array.from({ length: maxRows * maxCols }).map((_, i) => {
          const r = Math.floor(i / maxCols) + 1;
          const c = (i % maxCols) + 1;
          const active = r <= hoverRow && c <= hoverCol;
          return (
            <div key={i}
              onMouseEnter={() => { setHoverRow(r); setHoverCol(c); }}
              onClick={() => { onSelect(r, c); onClose(); }}
              style={{
                width: 18, height: 18,
                border: `1px solid ${active ? '#0078d4' : '#d2d0ce'}`,
                background: active ? '#deecf9' : 'white',
                borderRadius: 2, cursor: 'pointer',
              }} />
          );
        })}
      </div>
    </div>
  );
}

/* ===== Helper: subscript/superscript via inline HTML ===== */
function toggleSubscript(editor: Editor) {
  if ((editor.commands as any).toggleSubscript) {
    (editor.commands as any).toggleSubscript();
  } else {
    const { from, to } = editor.state.selection;
    const text = editor.state.doc.textBetween(from, to);
    if (text) editor.chain().focus().deleteSelection().insertContent('<sub>' + text + '</sub>').run();
  }
}
function toggleSuperscript(editor: Editor) {
  if ((editor.commands as any).toggleSuperscript) {
    (editor.commands as any).toggleSuperscript();
  } else {
    const { from, to } = editor.state.selection;
    const text = editor.state.doc.textBetween(from, to);
    if (text) editor.chain().focus().deleteSelection().insertContent('<sup>' + text + '</sup>').run();
  }
}

/* ===== COLLAPSED RIBBON ===== */
function CollapsedRibbon({ editor, onAttach, onImportanceChange, importance }: {
  editor: Editor; onAttach?: () => void;
  onImportanceChange?: (v: 'normal' | 'high' | 'low') => void; importance?: string;
}) {
  const [showColor, setShowColor] = useState(false);
  const imgRef = useRef<HTMLInputElement>(null);
  const handleImage = mkImageHandler(editor, imgRef);

  return (
    <>
      <select className="h-[24px] px-1 text-[11px] border border-[#c8c6c4] rounded-[2px] bg-white text-[#323130] outline-none focus:border-[#0078d4] w-[90px]"
        defaultValue="Calibri" onChange={e => editor.chain().focus().setFontFamily(e.target.value).run()}>
        {FONTS.map(f => <option key={f} value={f}>{f}</option>)}
      </select>
      <select className="h-[24px] px-1 text-[11px] border border-[#c8c6c4] rounded-[2px] bg-white text-[#323130] outline-none focus:border-[#0078d4] w-[38px]"
        defaultValue="12" onChange={e => (editor.chain().focus() as any).setFontSize(e.target.value + 'px').run()}>
        {SIZES.map(s => <option key={s} value={s}>{s}</option>)}
      </select>
      <CSep />
      <SmBtn a={editor.isActive('bold')} o={() => editor.chain().focus().toggleBold().run()} t="Negrita" icon={<span className="font-bold text-[12px]">B</span>} />
      <SmBtn a={editor.isActive('italic')} o={() => editor.chain().focus().toggleItalic().run()} t="Cursiva" icon={<span className="italic text-[12px]">I</span>} />
      <SmBtn a={editor.isActive('underline')} o={() => editor.chain().focus().toggleUnderline().run()} t="Subrayado" icon={<span className="underline text-[12px]">U</span>} />
      <SmBtn a={editor.isActive('strike')} o={() => editor.chain().focus().toggleStrike().run()} t="Tachado" icon={<span className="line-through text-[11px]">S</span>} />
      <div className="relative">
        <button onClick={() => setShowColor(!showColor)} title="Color de fuente"
          className="w-[22px] h-[22px] rounded-[2px] flex flex-col items-center justify-center hover:bg-[#e1dfdd]">
          <span className="text-[10px] font-bold leading-none">A</span>
          <div className="w-[14px] h-[3px] bg-[#d13438] rounded-sm -mt-[1px]" />
        </button>
        {showColor && <ColorPicker editor={editor} onClose={() => setShowColor(false)} />}
      </div>
      <CSep />
      <SmBtn a={editor.isActive('bulletList')} o={() => editor.chain().focus().toggleBulletList().run()} t="Viñetas" icon={<SvgI d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" s={13} />} />
      <SmBtn a={editor.isActive('orderedList')} o={() => editor.chain().focus().toggleOrderedList().run()} t="Numerada" icon={<SvgI d="M10 6h11M10 12h11M10 18h11M4 6h1v4M4 10h2M6 18H4c0-1 2-2 2-3s-1-1.5-2-1" s={13} />} />
      <SmBtn a={editor.isActive({textAlign:'left'})} o={() => editor.chain().focus().setTextAlign('left').run()} t="Izquierda" icon={<SvgI d="M4 6h16M4 12h10M4 18h14" s={13} />} />
      <SmBtn a={editor.isActive({textAlign:'center'})} o={() => editor.chain().focus().setTextAlign('center').run()} t="Centro" icon={<SvgI d="M4 6h16M7 12h10M5 18h14" s={13} />} />
      <CSep />
      <CBtn icon={<SvgI d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" s={14} />} label="Adjuntar" onClick={() => onAttach?.()} />
      <CBtn icon={<SvgI d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" s={14} />} label="Vincular" onClick={() => doLink(editor)} />
      <CBtn icon={<SvgI d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" s={14} />} label="Imagen" onClick={() => imgRef.current?.click()} />
      <input ref={imgRef} type="file" accept="image/*" className="hidden" onChange={handleImage} />
      <CSep />
      <CBtn icon={<ImportHighIcon />} label="Importancia alta" onClick={() => onImportanceChange?.(importance === 'high' ? 'normal' : 'high')} active={importance === 'high'} />
      <CBtn icon={<ImportLowIcon />} label="Importancia baja" onClick={() => onImportanceChange?.(importance === 'low' ? 'normal' : 'low')} active={importance === 'low'} />
      <CSep />
      <SmBtn o={() => editor.chain().focus().undo().run()} t="Deshacer" icon={<SvgI d="M3 10h10a5 5 0 015 5v2M3 10l4-4m-4 4l4 4" s={13} />} />
      <SmBtn o={() => editor.chain().focus().redo().run()} t="Rehacer" icon={<SvgI d="M21 10h-10a5 5 0 00-5 5v2M21 10l-4-4m4 4l-4 4" s={13} />} />
    </>
  );
}

const FONTS = ['Calibri','Arial','Segoe UI','Times New Roman','Courier New','Georgia','Verdana','Tahoma'];

function doLink(editor: Editor) {
  if (editor.isActive('link')) { editor.chain().focus().unsetLink().run(); return; }
  const url = window.prompt('URL:');
  if (url) editor.chain().focus().setLink({ href: url }).run();
}

function mkImageHandler(editor: Editor, _imgRef: React.RefObject<HTMLInputElement | null>) {
  return (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') editor.chain().focus().setImage({ src: reader.result }).run();
    };
    reader.readAsDataURL(file);
    e.target.value = '';
  };
}

/* ========== MESSAGE TAB ========== */
interface SigItem { id: number; name: string; html_content: string; is_default: boolean; }

// Menu desplegable del boton Firma: lista las firmas creadas por el usuario
// (Configuracion -> Firmas) y permite SELECCIONAR cual aplicar. Reemplaza la
// firma actual, no agrega una nueva.
function SignatureMenu({ onSelect, size }: { onSelect?: (html?: string) => void; size: 'med' | 'large' }) {
  const [open, setOpen] = useState(false);
  const [sigs, setSigs] = useState<SigItem[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number }>({ top: 0, left: 0 });
  const anchorRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (open && !loaded) {
      api.get<SigItem[]>('/settings/signatures')
        .then((r) => setSigs(r || []))
        .catch(() => {})
        .finally(() => setLoaded(true));
    }
  }, [open, loaded]);
  const toggle = () => {
    if (!open && anchorRef.current) {
      const r = anchorRef.current.getBoundingClientRect();
      setPos({ top: r.bottom + 4, left: r.left });
    }
    setOpen((o) => !o);
  };
  const icon = <SvgI d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" s={size === 'large' ? 22 : 16} />;
  return (
    <div className="relative" ref={anchorRef}>
      {size === 'large'
        ? <LargeBtn icon={icon} label="Firma" onClick={toggle} hasDropdown />
        : <MedBtn icon={icon} label="Firma" onClick={toggle} hasDropdown />}
      {open && createPortal(
        <>
          <div className="fixed inset-0 z-[9998]" onClick={() => setOpen(false)} />
          <div className="fixed w-[240px] bg-white rounded shadow-lg border border-[#edebe9] z-[9999] py-1 max-h-[320px] overflow-auto" style={{ top: pos.top, left: pos.left }}>
            <div className="px-3 py-1 text-[11px] font-semibold text-[#605e5c] uppercase tracking-wide">Mis firmas</div>
            {loaded && sigs.length === 0 && (
              <div className="px-3 py-2 text-[12px] text-[#605e5c]">No tienes firmas. Crea una en Configuracion &rarr; Firmas.</div>
            )}
            {sigs.map((sg) => (
              <button key={sg.id} onClick={() => { onSelect?.(sg.html_content); setOpen(false); }}
                className="w-full text-left px-3 py-[6px] text-[13px] hover:bg-[#f3f2f1] flex items-center justify-between gap-2">
                <span className="truncate">{sg.name}</span>
                {sg.is_default && <span className="text-[10px] text-[#0078d4] flex-shrink-0">predet.</span>}
              </button>
            ))}
            <div className="border-t border-[#edebe9] mt-1 pt-1">
              <button onClick={() => { onSelect?.(''); setOpen(false); }}
                className="w-full text-left px-3 py-[6px] text-[12px] text-[#a4262c] hover:bg-[#f3f2f1]">Quitar firma</button>
            </div>
          </div>
        </>,
        document.body
      )}
    </div>
  );
}

function MessageTab({ editor, onAttach, onImportanceChange, importance, onSaveDraft, onInsertSignature, onDownloadDraft, onDictate, onOpenApps, ...rest }: {
  editor: Editor; onAttach?: () => void;
  onImportanceChange?: (v: 'normal' | 'high' | 'low') => void; importance?: string;
  onSaveDraft?: () => void; onInsertSignature?: (html?: string) => void; onDownloadDraft?: () => void;
  onDictate?: () => void; onOpenApps?: () => void; onReviewEditor?: () => void; onCheckAccessibility?: () => void; onImproveWriting?: () => void;
}) {

  const [showTblGrid, setShowTblGrid] = useState(false);
  const { onReviewEditor, onCheckAccessibility, onImproveWriting } = rest;
  const [showColor, setShowColor] = useState(false);
  const [showEmoji, setShowEmoji] = useState(false);
  const emojiAnchorRef = useRef<HTMLDivElement>(null);
  const [showStyles, setShowStyles] = useState(false);
  const imgRef = useRef<HTMLInputElement>(null);
  const handleImage = mkImageHandler(editor, imgRef);

  return (
    <>
      {/* Portapapeles */}
      <RGroup label="Portapapeles">
        <LargeBtn icon={<ClipboardIcon />} label="Pegar" onClick={() => { void doPaste(editor); }} />
      </RGroup>
      <GSep />

      {/* Texto básico - TWO ROWS */}
      <RGroup label="Texto básico">
        <div className="flex flex-col gap-[2px] py-[3px]">
          <div className="flex items-center gap-[2px]">
            <select className="h-[22px] px-1 text-[11px] border border-[#c8c6c4] rounded-[2px] bg-white text-[#323130] outline-none focus:border-[#0078d4] w-[100px]"
              defaultValue="Calibri" onChange={e => editor.chain().focus().setFontFamily(e.target.value).run()}>
              {FONTS.map(f => <option key={f} value={f}>{f}</option>)}
            </select>
            <select className="h-[22px] px-1 text-[11px] border border-[#c8c6c4] rounded-[2px] bg-white text-[#323130] outline-none focus:border-[#0078d4] w-[40px]"
              defaultValue="12" onChange={e => (editor.chain().focus() as any).setFontSize(e.target.value + 'px').run()}>
              {SIZES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <SmBtn t="Aumentar tamaño de fuente" o={() => stepFontSize(editor, 'up')} icon={<span className="text-[10px] font-bold">aA</span>} />
            <SmBtn t="Reducir tamaño de fuente" o={() => stepFontSize(editor, 'down')} icon={<span className="text-[9px] font-bold">Ab</span>} />
          </div>
          <div className="flex items-center gap-[1px]">
            <SmBtn a={editor.isActive('bold')} o={() => editor.chain().focus().toggleBold().run()} t="Negrita (Ctrl+B)" icon={<span className="font-bold text-[12px]">B</span>} />
            <SmBtn a={editor.isActive('italic')} o={() => editor.chain().focus().toggleItalic().run()} t="Cursiva (Ctrl+I)" icon={<span className="italic text-[12px]">I</span>} />
            <SmBtn a={editor.isActive('underline')} o={() => editor.chain().focus().toggleUnderline().run()} t="Subrayado (Ctrl+U)" icon={<span className="underline text-[12px]">U</span>} />
            <SmBtn a={editor.isActive('strike')} o={() => editor.chain().focus().toggleStrike().run()} t="Tachado" icon={<span className="line-through text-[11px]">S</span>} />
            <SmBtn o={() => toggleSubscript(editor)} t="Subíndice" icon={<span className="text-[9px]">x<sub>2</sub></span>} />
            <SmBtn o={() => toggleSuperscript(editor)} t="Superíndice" icon={<span className="text-[9px]">x<sup>2</sup></span>} />
            <div className="relative">
              <button onClick={() => setShowColor(!showColor)} title="Color de fuente"
                className="w-[22px] h-[22px] rounded-[2px] flex flex-col items-center justify-center hover:bg-[#e1dfdd] transition-colors">
                <span className="text-[10px] font-bold leading-none">A</span>
                <div className="w-[14px] h-[3px] bg-[#d13438] rounded-sm -mt-[1px]" />
              </button>
              {showColor && <ColorPicker editor={editor} onClose={() => setShowColor(false)} />}
            </div>
            <SmBtn a={hasHighlight(editor)} o={() => (editor.chain().focus() as any).toggleHighlight().run()} t="Resaltado" icon={<span className="text-[9px] bg-[#fff100] px-[2px] rounded-sm font-medium">ab</span>} />
            <SmBtn o={() => editor.chain().focus().clearNodes().unsetAllMarks().run()} t="Borrar formato" icon={<SvgI d="M4 7V4h16v3M9 20h6M12 4v16" s={12} />} />
          </div>
        </div>
      </RGroup>
      <GSep />

      {/* Estilos */}
      <RGroup label="Estilos">
        <div className="relative">
          <LargeBtn icon={<SvgI d="M4 6h16M4 10h16M4 14h10M4 18h12" s={20} />} label="Estilos" onClick={() => setShowStyles(!showStyles)} hasDropdown />
          {showStyles && (
            <>
              <div className="fixed inset-0 z-[190]" onClick={() => setShowStyles(false)} />
              <div className="absolute left-0 top-full mt-1 w-[180px] bg-white rounded shadow-lg border border-[#edebe9] z-50 py-1">
                <button onClick={() => { editor.chain().focus().setParagraph().run(); setShowStyles(false); }} className="w-full text-left px-3 py-[5px] text-[13px] hover:bg-[#f3f2f1]">Normal</button>
                <button onClick={() => { editor.chain().focus().toggleHeading({level:1}).run(); setShowStyles(false); }} className="w-full text-left px-3 py-[5px] text-[20px] font-bold hover:bg-[#f3f2f1]">Título 1</button>
                <button onClick={() => { editor.chain().focus().toggleHeading({level:2}).run(); setShowStyles(false); }} className="w-full text-left px-3 py-[5px] text-[16px] font-bold hover:bg-[#f3f2f1]">Título 2</button>
                <button onClick={() => { editor.chain().focus().toggleHeading({level:3}).run(); setShowStyles(false); }} className="w-full text-left px-3 py-[5px] text-[14px] font-bold hover:bg-[#f3f2f1]">Título 3</button>
                <div className="h-px bg-[#edebe9] my-1" />
                <button onClick={() => { editor.chain().focus().toggleBlockquote().run(); setShowStyles(false); }} className="w-full text-left px-3 py-[5px] text-[13px] italic text-[#605e5c] hover:bg-[#f3f2f1]">Cita</button>
                <button onClick={() => { editor.chain().focus().toggleCodeBlock().run(); setShowStyles(false); }} className="w-full text-left px-3 py-[5px] text-[12px] font-mono hover:bg-[#f3f2f1]">Código</button>
              </div>
            </>
          )}
        </div>
      </RGroup>
      <GSep />

      {/* Insertar group */}
      <RGroup label="Insertar">
        <div className="flex flex-col gap-[1px] py-[2px]">
          <div className="flex items-center gap-[2px]">
            <MedBtn icon={<SvgI d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" s={16} />} label="Adjuntar" onClick={() => onAttach?.()} hasDropdown />
            <MedBtn icon={<SvgI d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" s={16} />} label="Vincular" onClick={() => doLink(editor)} />
            <SignatureMenu onSelect={onInsertSignature} size="med" />
          </div>
          <div className="flex items-center gap-[2px]">
            <MedBtn icon={<SvgI d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" s={16} />} label="Imágenes" onClick={() => imgRef.current?.click()} />
            <div className="relative" ref={emojiAnchorRef}>
              <MedBtn icon={<span className="text-[14px]">&#128578;</span>} label="Emoji" onClick={() => setShowEmoji(!showEmoji)} />
              {showEmoji && <EmojiPicker editor={editor} onClose={() => setShowEmoji(false)} anchorRef={emojiAnchorRef} />}
            </div>
            <div className="relative">
                <MedBtn icon={<SvgI d="M3 10h18M3 14h18M10 3v18M14 3v18" s={16} />} label="Tabla" onClick={() => setShowTblGrid(!showTblGrid)} hasDropdown />
                {showTblGrid && <TableGridSelector onSelect={(r,c) => insertTable(editor, r, c)} onClose={() => setShowTblGrid(false)} />}
              </div>
          </div>
        </div>
        <input ref={imgRef} type="file" accept="image/*" className="hidden" onChange={handleImage} />
      </RGroup>
      <GSep />

      {/* Complementos → Futuro: marketplace de complementos */}
      <RGroup label="Complementos">
        <LargeBtn icon={<GridIcon />} label="Aplicaciones" onClick={() => onOpenApps?.()} />
      </RGroup>
      <GSep />

      {/* Voz → VM 170 (ia-maquita) Whisper STT */}
      <RGroup label="Voz">
        <LargeBtn icon={<MicIcon />} label="Dictar" onClick={() => onDictate?.()} />
      </RGroup>
      <GSep />

      {/* Etiquetas */}
      <RGroup label="Etiquetas">
        <div className="flex items-center gap-[2px]">
          <LargeBtn icon={<ImportHighIcon />} label={"Importancia\nalta"} onClick={() => onImportanceChange?.(importance === 'high' ? 'normal' : 'high')} active={importance === 'high'} />
          <LargeBtn icon={<ImportLowIcon />} label={"Importancia\nbaja"} onClick={() => onImportanceChange?.(importance === 'low' ? 'normal' : 'low')} active={importance === 'low'} />
        </div>
      </RGroup>
      <GSep />

      {/* Formato */}
      <RGroup label="Formato">
        <LargeBtn icon={<span className="text-[18px] font-light text-[#323130]">T</span>} label={"Cambiar a texto\nsin formato"} onClick={() => {
          const text = editor.getText();
          editor.commands.setContent(`<p>${text.replace(/\n/g, '<br>')}</p>`);
        }} />
      </RGroup>
      <GSep />

      {/* Imprimir */}
      <RGroup label="Imprimir">
        <LargeBtn icon={<PrintIcon />} label="Imprimir" onClick={() => window.print()} />
      </RGroup>
      <GSep />

      {/* Guardar */}
      <RGroup label="Guardar">
        <div className="flex items-center gap-[2px]">
          <LargeBtn icon={<SaveIcon />} label={"Guardar\nborrador"} onClick={() => onSaveDraft?.()} />
          <LargeBtn icon={<DownloadIcon />} label="Descargar" onClick={() => onDownloadDraft?.()} hasDropdown />
        </div>
      </RGroup>
      <GSep />

      {/* Opciones → VM 170 revisión IA */}
      <RGroup label="Opciones">
        <div className="flex items-center gap-[2px]">
          <LargeBtn icon={<EditorIcon />} label="Editor" onClick={() => onReviewEditor?.()} />
          <LargeBtn icon={<AccessIcon />} label={"Comprobar\naccesibilidad"} onClick={() => onCheckAccessibility?.()} />
        </div>
      </RGroup>
      <GSep />

      {/* IA Maquita → VM 170 mejorar redacción con IA */}
      <RGroup label="IA Maquita">
        <LargeBtn icon={<SparkleIcon />} label={"Mejorar\nredacción"} onClick={() => onImproveWriting?.()} />
      </RGroup>
    </>
  );
}

/* ========== INSERT TAB ========== */
function InsertTab({ editor, onAttach, onInsertSignature, onOpenApps }: { editor: Editor; onAttach?: () => void; onInsertSignature?: (html?: string) => void; onOpenApps?: () => void }) {

  const [showTblGrid, setShowTblGrid] = useState(false);
  const imgRef = useRef<HTMLInputElement>(null);
  const [showEmoji, setShowEmoji] = useState(false);
  const emojiAnchorRef = useRef<HTMLDivElement>(null);
  const handleImage = mkImageHandler(editor, imgRef);

  return (
    <>
      <RGroup label="Incluir">
        <div className="flex items-center gap-[3px]">
          <LargeBtn icon={<SvgI d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" s={22} />} label={"Adjuntar\narchivo"} onClick={() => onAttach?.()} hasDropdown />
          <LargeBtn icon={<SvgI d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" s={22} />} label="Vincular" onClick={() => doLink(editor)} />
          <SignatureMenu onSelect={onInsertSignature} size="large" />
          <LargeBtn icon={<SvgI d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" s={22} />} label="Imágenes" onClick={() => imgRef.current?.click()} />
          <div className="relative" ref={emojiAnchorRef}>
            <LargeBtn icon={<span className="text-[20px]">&#128578;</span>} label="Emoji" onClick={() => setShowEmoji(!showEmoji)} />
            {showEmoji && <EmojiPicker editor={editor} onClose={() => setShowEmoji(false)} anchorRef={emojiAnchorRef} />}
          </div>
          <LargeBtn icon={<SvgI d="M3 10h18M3 14h18M10 3v18M14 3v18" s={22} />} label="Tabla" onClick={() => setShowTblGrid(!showTblGrid)} hasDropdown />
                {showTblGrid && <TableGridSelector onSelect={(r,c) => insertTable(editor, r, c)} onClose={() => setShowTblGrid(false)} />}
        </div>
        <input ref={imgRef} type="file" accept="image/*" className="hidden" onChange={handleImage} />
      </RGroup>
      <GSep />
      <RGroup label="Complementos">
        <LargeBtn icon={<GridIcon />} label="Aplicaciones" onClick={() => onOpenApps?.()} />
      </RGroup>
    </>
  );
}

/* ========== FORMAT TAB ========== */
function FormatTab({ editor, onFormatPaint }: { editor: Editor; onFormatPaint?: (marks: string[]) => void }) {
  const [showColor, setShowColor] = useState(false);
  const [formatPaintArmed, setFormatPaintArmed] = useState(Boolean(formatPaintBuffer));

  return (
    <>
      <RGroup label="Portapapeles">
        <div className="flex items-center gap-[3px]">
          <LargeBtn icon={<SvgI d="M3 10h10a5 5 0 015 5v2M3 10l4-4m-4 4l4 4" s={20} />} label="Deshacer" onClick={() => editor.chain().focus().undo().run()} />
          <LargeBtn icon={<ClipboardIcon />} label="Pegar" onClick={() => { void doPaste(editor); }} />
          <div className="flex flex-col gap-[1px] py-[6px]">
            <SmBtn o={() => { void doCut(editor); }} t="Cortar (Ctrl+X)" icon={<span className="text-[10px]">✂</span>}>Cortar</SmBtn>
            <SmBtn o={() => { void doCopy(editor); }} t="Copiar (Ctrl+C)" icon={<SvgI d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" s={12} />}>Copiar</SmBtn>
            <SmBtn a={formatPaintArmed} o={() => {
              if (!formatPaintBuffer) {
                const snapshot = captureFormatSnapshot(editor);
                if (!snapshot) {
                  showToast('Coloca el cursor en texto con formato para copiarlo');
                  return;
                }
                formatPaintBuffer = snapshot;
                setFormatPaintArmed(true);
                onFormatPaint?.(snapshot.marks);
                showToast('Formato copiado. Selecciona texto y pulsa de nuevo para aplicarlo');
                return;
              }

              const applied = applyFormatSnapshot(editor, formatPaintBuffer);
              if (!applied) return;
              onFormatPaint?.(formatPaintBuffer.marks);
              formatPaintBuffer = null;
              setFormatPaintArmed(false);
              showToast('Formato aplicado');
            }} t={formatPaintArmed ? 'Aplicar formato copiado' : 'Copiar formato'} icon={<SvgI d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2" s={12} />}>Copiar formato</SmBtn>
          </div>
        </div>
      </RGroup>
      <GSep />

      <RGroup label="Texto básico">
        <div className="flex flex-col gap-[2px] py-[3px]">
          <div className="flex items-center gap-[2px]">
            <select className="h-[22px] px-1 text-[11px] border border-[#c8c6c4] rounded-[2px] bg-white text-[#323130] outline-none focus:border-[#0078d4] w-[100px]"
              defaultValue="Calibri" onChange={e => editor.chain().focus().setFontFamily(e.target.value).run()}>
              {FONTS.map(f => <option key={f} value={f}>{f}</option>)}
            </select>
            <select className="h-[22px] px-1 text-[11px] border border-[#c8c6c4] rounded-[2px] bg-white text-[#323130] outline-none focus:border-[#0078d4] w-[40px]"
              defaultValue="12" onChange={e => (editor.chain().focus() as any).setFontSize(e.target.value + 'px').run()}>
              {SIZES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <SmBtn t="Aumentar tamaño" o={() => stepFontSize(editor, 'up')} icon={<span className="text-[10px] font-bold">aA</span>} />
            <SmBtn t="Borrar formato" o={() => editor.chain().focus().clearNodes().unsetAllMarks().run()} icon={<span className="text-[10px]">Ab</span>} />
          </div>
          <div className="flex items-center gap-[1px]">
            <SmBtn a={editor.isActive('bold')} o={() => editor.chain().focus().toggleBold().run()} t="Negrita" icon={<span className="font-bold text-[12px]">B</span>} />
            <SmBtn a={editor.isActive('italic')} o={() => editor.chain().focus().toggleItalic().run()} t="Cursiva" icon={<span className="italic text-[12px]">I</span>} />
            <SmBtn a={editor.isActive('underline')} o={() => editor.chain().focus().toggleUnderline().run()} t="Subrayado" icon={<span className="underline text-[12px]">U</span>} />
            <SmBtn a={editor.isActive('strike')} o={() => editor.chain().focus().toggleStrike().run()} t="Tachado" icon={<span className="line-through text-[11px]">S</span>} />
            <SmBtn o={() => toggleSubscript(editor)} t="Subíndice" icon={<span className="text-[9px]">x<sub>2</sub></span>} />
            <SmBtn o={() => toggleSuperscript(editor)} t="Superíndice" icon={<span className="text-[9px]">x<sup>2</sup></span>} />
            <SmBtn a={hasHighlight(editor)} o={() => (editor.chain().focus() as any).toggleHighlight().run()} t="Resaltado" icon={<span className="text-[9px] bg-[#fff100] px-[2px] rounded-sm">ab</span>} />
            <div className="relative">
              <button onClick={() => setShowColor(!showColor)} title="Color de fuente"
                className="w-[22px] h-[22px] rounded-[2px] flex flex-col items-center justify-center hover:bg-[#e1dfdd]">
                <span className="text-[10px] font-bold leading-none">A</span>
                <div className="w-[14px] h-[3px] bg-[#d13438] rounded-sm -mt-[1px]" />
              </button>
              {showColor && <ColorPicker editor={editor} onClose={() => setShowColor(false)} />}
            </div>
            <SmBtn o={() => editor.chain().focus().clearNodes().unsetAllMarks().run()} t="Borrar formato" icon={<SvgI d="M4 7V4h16v3M9 20h6M12 4v16" s={12} />} />
          </div>
        </div>
      </RGroup>
      <GSep />

      <RGroup label="Párrafo">
        <div className="flex flex-col gap-[2px] py-[3px]">
          <div className="flex items-center gap-[1px]">
            <SmBtn a={editor.isActive('bulletList')} o={() => editor.chain().focus().toggleBulletList().run()} t="Viñetas" icon={<SvgI d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" s={13} />} />
            <SmBtn a={editor.isActive('orderedList')} o={() => editor.chain().focus().toggleOrderedList().run()} t="Numerada" icon={<SvgI d="M10 6h11M10 12h11M10 18h11M4 6h1v4M4 10h2M6 18H4c0-1 2-2 2-3s-1-1.5-2-1" s={13} />} />
            <div className="w-px h-[16px] bg-[#e1dfdd] mx-[2px]" />
            <SmBtn a={editor.isActive({textAlign:'left'})} o={() => editor.chain().focus().setTextAlign('left').run()} t="Alinear izquierda" icon={<SvgI d="M4 6h16M4 12h10M4 18h14" s={13} />} />
            <SmBtn a={editor.isActive({textAlign:'center'})} o={() => editor.chain().focus().setTextAlign('center').run()} t="Centrar" icon={<SvgI d="M4 6h16M7 12h10M5 18h14" s={13} />} />
            <SmBtn a={editor.isActive({textAlign:'right'})} o={() => editor.chain().focus().setTextAlign('right').run()} t="Alinear derecha" icon={<SvgI d="M4 6h16M10 12h10M6 18h14" s={13} />} />
            <SmBtn o={() => editor.chain().focus().setTextAlign('justify').run()} t="Justificar" icon={<SvgI d="M4 6h16M4 12h16M4 18h16" s={13} />} />
          </div>
          <div className="flex items-center gap-[1px]">
            <SmBtn o={() => editor.chain().focus().liftListItem('listItem').run()} t="Reducir sangría" icon={<SvgI d="M10 12H3l3-3m-3 3l3 3M13 6h8M13 12h8M13 18h8" s={13} />} />
            <SmBtn o={() => editor.chain().focus().sinkListItem('listItem').run()} t="Aumentar sangría" icon={<SvgI d="M3 12h7l-3-3m3 3l-3 3M13 6h8M13 12h8M13 18h8" s={13} />} />
            <div className="w-px h-[16px] bg-[#e1dfdd] mx-[2px]" />
            <SmBtn o={() => editor.chain().focus().setHorizontalRule().run()} t="Línea horizontal" icon={<SvgI d="M4 12h16" s={13} />} />
            <SmBtn a={editor.isActive('blockquote')} o={() => editor.chain().focus().toggleBlockquote().run()} t="Cita" icon={<span className="text-[14px] font-serif leading-none">&ldquo;</span>} />
          </div>
        </div>
      </RGroup>
    </>
  );
}

/* ========== OPTIONS TAB ========== */
function OptionsTab({ editor, onShowCc, onShowBcc, showCc, showBcc, onImportanceChange, importance, onSaveDraft, onDownloadDraft, onScheduleSend, onReviewEditor, onCheckAccessibility, onTrackingChange }: {
  editor: Editor; onShowCc?: () => void; onShowBcc?: () => void; showCc?: boolean; showBcc?: boolean;
  onImportanceChange?: (v: 'normal' | 'high' | 'low') => void; importance?: string;
  onSaveDraft?: () => void; onDownloadDraft?: () => void;
  onScheduleSend?: () => void; onReviewEditor?: () => void; onCheckAccessibility?: () => void;
  onTrackingChange?: (tracking: { delivery: boolean; read: boolean; noReactions: boolean }) => void;
}) {
  const [reqDelivery, setReqDelivery] = useState(false);
  const [reqRead, setReqRead] = useState(false);
  const [noReactions, setNoReactions] = useState(false);

  const updateTracking = (d: boolean, r: boolean, n: boolean) => {
    onTrackingChange?.({ delivery: d, read: r, noReactions: n });
  };

  return (
    <>
      {/* Revisión → VM 170 (ia-maquita) revisión IA */}
      <RGroup label="Revisión">
        <div className="flex items-center gap-[2px]">
          <LargeBtn icon={<EditorIcon />} label="Editor" onClick={() => onReviewEditor?.()} />
          <LargeBtn icon={<AccessIcon />} label={"Comprobar\naccesibilidad"} onClick={() => onCheckAccessibility?.()} />
        </div>
      </RGroup>
      <GSep />

      {/* Programar envío → Backend webmail: cron/queue */}
      <RGroup label="Enviar">
        <LargeBtn icon={<SvgI d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" s={20} />} label={"Programar\nenvío"} onClick={() => onScheduleSend?.()} />
      </RGroup>
      <GSep />

      <RGroup label="Mostrar campos">
        <div className="flex flex-col gap-[4px] py-[6px]">
          <label className="flex items-center gap-[4px] text-[11px] text-[#323130] cursor-pointer hover:text-[#0078d4]">
            <input type="checkbox" checked={showBcc || false} onChange={() => onShowBcc?.()}
              className="w-[13px] h-[13px] accent-[#0078d4]" />
            Mostrar Bcc
          </label>
          <label className="flex items-center gap-[4px] text-[11px] text-[#323130] cursor-pointer hover:text-[#0078d4]">
            <input type="checkbox" checked={showCc || false} onChange={() => onShowCc?.()}
              className="w-[13px] h-[13px] accent-[#0078d4]" />
            Mostrar CC
          </label>
        </div>
      </RGroup>
      <GSep />

      <RGroup label="Seguimiento">
        <div className="flex flex-col gap-[4px] py-[6px]">
          <label className="flex items-center gap-[4px] text-[11px] text-[#323130] cursor-pointer">
            <input type="checkbox" checked={reqDelivery} onChange={() => { const v = !reqDelivery; setReqDelivery(v); updateTracking(v, reqRead, noReactions); }}
              className="w-[13px] h-[13px] accent-[#0078d4]" />
            Confirmación de entrega
          </label>
          <label className="flex items-center gap-[4px] text-[11px] text-[#323130] cursor-pointer">
            <input type="checkbox" checked={reqRead} onChange={() => { const v = !reqRead; setReqRead(v); updateTracking(reqDelivery, v, noReactions); }}
              className="w-[13px] h-[13px] accent-[#0078d4]" />
            Confirmación de lectura
          </label>
          <label className="flex items-center gap-[4px] text-[11px] text-[#323130] cursor-pointer">
            <input type="checkbox" checked={noReactions} onChange={() => { const v = !noReactions; setNoReactions(v); updateTracking(reqDelivery, reqRead, v); }}
              className="w-[13px] h-[13px] accent-[#0078d4]" />
            No permitir reacciones
          </label>
        </div>
      </RGroup>
      <GSep />

      <RGroup label="Etiquetas">
        <div className="flex items-center gap-[2px]">
          <LargeBtn icon={<ImportHighIcon />} label={"Importancia\nalta"} onClick={() => onImportanceChange?.(importance === 'high' ? 'normal' : 'high')} active={importance === 'high'} />
          <LargeBtn icon={<ImportLowIcon />} label={"Importancia\nbaja"} onClick={() => onImportanceChange?.(importance === 'low' ? 'normal' : 'low')} active={importance === 'low'} />
        </div>
      </RGroup>
      <GSep />

      <RGroup label="Imprimir">
        <LargeBtn icon={<PrintIcon />} label={"Imprimir\nborrador"} onClick={() => window.print()} />
      </RGroup>
      <GSep />

      <RGroup label="Formato">
        <LargeBtn icon={<span className="text-[18px] font-light text-[#323130]">T</span>} label={"Cambiar a texto\nsin formato"} onClick={() => {
          const text = editor.getText();
          editor.commands.setContent(`<p>${text.replace(/\n/g, '<br>')}</p>`);
        }} />
      </RGroup>
      <GSep />

      <RGroup label="Guardar">
        <div className="flex items-center gap-[2px]">
          <LargeBtn icon={<SaveIcon />} label={"Guardar\nborrador"} onClick={() => onSaveDraft?.()} />
          <LargeBtn icon={<DownloadIcon />} label="Descargar" onClick={() => onDownloadDraft?.()} hasDropdown />
        </div>
      </RGroup>
    </>
  );
}

/* ========== EMOJI PICKER ========== */
function EmojiPicker({ editor, onClose, anchorRef }: { editor: Editor; onClose: () => void; anchorRef: { current: HTMLDivElement | null } }) {
  const [pos, setPos] = useState<{ top: number; left: number }>({ top: -9999, left: -9999 });
  useLayoutEffect(() => {
    const r = anchorRef.current?.getBoundingClientRect();
    if (r) setPos({ top: r.bottom + 4, left: r.left });
  }, [anchorRef]);
  const emojis = ['😊','😂','❤️','👍','🎉','🔥','😍','🤔','👏','💪','✨','🙏','😎','🥳','💯','⭐','🚀','💡','📌','✅','❌','⚠️','📎','📧','🗓️','📝','🎯','💼','🤝','👋'];
  return createPortal(
    <>
      <div className="fixed inset-0 z-[190]" onClick={onClose} />
      <div className="fixed grid grid-cols-6 gap-[2px] p-2 bg-white rounded shadow-lg border border-[#edebe9] z-[200] w-[200px]" style={{ top: pos.top, left: pos.left }}>
        {emojis.map(e => (
          <button key={e} onMouseDown={(ev) => ev.preventDefault()} onClick={() => { editor.chain().focus().insertContent(e).run(); onClose(); }}
            className="w-[28px] h-[28px] rounded hover:bg-[#f3f2f1] flex items-center justify-center text-[16px] transition-colors">
            {e}
          </button>
        ))}
      </div>
    </>,
    document.body
  );
}

/* ========== LAYOUT COMPONENTS ========== */
function RGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col h-full shrink-0">
      <div className="flex-1 flex items-center px-[6px]">{children}</div>
      <div className="text-[10px] text-[#605e5c] text-center px-1 pb-[3px] leading-[11px] whitespace-nowrap">{label}</div>
    </div>
  );
}
function GSep() { return <div className="w-px bg-[#e1dfdd] my-[6px] shrink-0" />; }
function CSep() { return <div className="w-px h-[20px] bg-[#e1dfdd] mx-[3px] shrink-0" />; }

function LargeBtn({ icon, label, onClick, disabled, active, hasDropdown }: {
  icon: ReactNode; label: string; onClick: () => void; disabled?: boolean; active?: boolean; hasDropdown?: boolean;
}) {
  const lines = label.split('\n');
  return (
    <button onMouseDown={(e) => e.preventDefault()} onClick={onClick} disabled={disabled} title={lines.join(' ')}
      className={`flex flex-col items-center justify-center min-w-[44px] px-[4px] rounded-[3px] transition-colors h-[62px] ${
        active ? 'bg-[#c7e0f4]' : disabled ? 'opacity-40 cursor-not-allowed' : 'hover:bg-[#e1dfdd]'
      }`}>
      <div className="h-[24px] flex items-center justify-center">{icon}</div>
      <div className="flex items-center gap-[1px] mt-[1px]">
        <span className="text-[10px] leading-[12px] text-[#323130] text-center whitespace-pre-line">{lines.join('\n')}</span>
        {hasDropdown && <svg className="w-[8px] h-[8px] text-[#605e5c] shrink-0 ml-[1px]" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" /></svg>}
      </div>
    </button>
  );
}

function MedBtn({ icon, label, onClick, hasDropdown }: { icon: ReactNode; label: string; onClick: () => void; hasDropdown?: boolean; }) {
  return (
    <button onMouseDown={(e) => e.preventDefault()} onClick={onClick} title={label}
      className="flex items-center gap-[3px] h-[24px] px-[4px] rounded-[2px] hover:bg-[#e1dfdd] transition-colors">
      {icon}
      <span className="text-[10px] text-[#323130] whitespace-nowrap">{label}</span>
      {hasDropdown && <svg className="w-[7px] h-[7px] text-[#605e5c]" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" /></svg>}
    </button>
  );
}

function SmBtn({ a, o, t, icon, children }: { a?: boolean; o: () => void; t: string; icon: ReactNode; children?: ReactNode }) {
  if (children) {
    return (
      <button onMouseDown={(e) => e.preventDefault()} onClick={o} title={t}
        className="flex items-center gap-[3px] h-[20px] px-[3px] rounded-[2px] text-[#323130] hover:bg-[#e1dfdd] transition-colors">
        {icon}<span className="text-[10px]">{children}</span>
      </button>
    );
  }
  return (
    <button onMouseDown={(e) => e.preventDefault()} onClick={o} title={t}
      className={`w-[22px] h-[22px] rounded-[2px] flex items-center justify-center transition-colors ${
        a ? 'bg-[#c7e0f4] text-[#0078d4]' : 'text-[#323130] hover:bg-[#e1dfdd]'
      }`}>
      {icon}
    </button>
  );
}

function CBtn({ icon, label, onClick, active }: { icon: ReactNode; label: string; onClick: () => void; active?: boolean }) {
  return (
    <button onMouseDown={(e) => e.preventDefault()} onClick={onClick} title={label}
      className={`h-[28px] px-[6px] rounded-[3px] flex items-center gap-[4px] transition-colors whitespace-nowrap ${
        active ? 'bg-[#c7e0f4] text-[#0078d4]' : 'text-[#323130] hover:bg-[#e1dfdd]'
      }`}>
      {icon}{label && <span className="text-[11px]">{label}</span>}
    </button>
  );
}

function ColorPicker({ editor, onClose }: { editor: Editor; onClose: () => void }) {
  return (
    <>
      <div className="fixed inset-0 z-[190]" onClick={onClose} />
      <div className="absolute left-0 top-full mt-1 grid grid-cols-5 gap-[3px] p-2 bg-white rounded shadow-lg border border-[#edebe9] z-[200]">
        {['#000000','#323130','#605e5c','#a19f9d','#d2d0ce',
          '#d13438','#ca5010','#986f0b','#498205','#038387',
          '#0078d4','#004e8c','#8764b8','#881798','#c239b3',
          '#a4262c','#8a3707','#6d5c09','#0b6a0b','#005b70',
        ].map(c => (
          <button key={c} onClick={() => { editor.chain().focus().setColor(c).run(); onClose(); }}
            className="w-[22px] h-[22px] rounded-[2px] border border-[#e1dfdd] hover:scale-110 hover:shadow transition-all"
            style={{ backgroundColor: c }} />
        ))}
      </div>
    </>
  );
}

/* ========== SVG ICONS ========== */
function SvgI({ d, s = 16 }: { d: string; s?: number }) {
  return <svg className="shrink-0" style={{width:s,height:s}} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={d} /></svg>;
}
function ClipboardIcon() { return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#0078d4" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>; }
function GridIcon() { return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#0078d4" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /></svg>; }
function MicIcon() { return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#a4262c" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4M12 15a3 3 0 003-3V5a3 3 0 00-6 0v7a3 3 0 003 3z" /></svg>; }
function ImportHighIcon() { return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#d13438" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 19V5M12 5l-4 4M12 5l4 4" /></svg>; }
function ImportLowIcon() { return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#0078d4" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14M12 19l-4-4M12 19l4-4" /></svg>; }
function PrintIcon() { return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#323130" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4H7v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" /></svg>; }
function SaveIcon() { return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#323130" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" /></svg>; }
function DownloadIcon() { return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#323130" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>; }
function EditorIcon() { return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#323130" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>; }
function AccessIcon() { return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#323130" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" d="M12 4a8 8 0 100 16 8 8 0 000-16z" /></svg>; }
function SparkleIcon() { return <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#0078d4" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" /></svg>; }
