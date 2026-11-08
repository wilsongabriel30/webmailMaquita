import { useEffect, useRef, useState } from 'react';
import { BotonGuardarEnAlmacen } from '../files/GuardarEnAlmacen';
import type { AttachmentInfo } from '../../types';
import { formatSize } from '../../lib/tamanoAdjunto';

/**
 * Tarjeta de un adjunto con menú «▾», como en Outlook (07/11/2026).
 * Clic en la tarjeta: vista previa. «▾»: Vista previa, Descargar y Guardar en Archivos.
 */

// Insignia de tipo por extensión (color + etiqueta). Ejecutables y comprimidos se resaltan.
const EXT_BADGE: Record<string, { bg: string; label: string }> = {
  pdf: { bg: '#d13438', label: 'PDF' },
  doc: { bg: '#2b579a', label: 'DOC' }, docx: { bg: '#2b579a', label: 'DOC' }, rtf: { bg: '#2b579a', label: 'RTF' }, odt: { bg: '#2b579a', label: 'ODT' },
  xls: { bg: '#217346', label: 'XLS' }, xlsx: { bg: '#217346', label: 'XLS' }, csv: { bg: '#217346', label: 'CSV' }, ods: { bg: '#217346', label: 'ODS' },
  ppt: { bg: '#d24726', label: 'PPT' }, pptx: { bg: '#d24726', label: 'PPT' }, odp: { bg: '#d24726', label: 'ODP' },
  zip: { bg: '#8661c5', label: 'ZIP' }, rar: { bg: '#8661c5', label: 'RAR' }, '7z': { bg: '#8661c5', label: '7Z' }, gz: { bg: '#8661c5', label: 'GZ' }, tar: { bg: '#8661c5', label: 'TAR' },
  txt: { bg: '#605e5c', label: 'TXT' }, log: { bg: '#605e5c', label: 'LOG' }, xml: { bg: '#605e5c', label: 'XML' },
  jpg: { bg: '#0b6a0b', label: 'IMG' }, jpeg: { bg: '#0b6a0b', label: 'IMG' }, png: { bg: '#0b6a0b', label: 'PNG' }, gif: { bg: '#0b6a0b', label: 'GIF' }, webp: { bg: '#0b6a0b', label: 'IMG' }, svg: { bg: '#0b6a0b', label: 'SVG' },
  exe: { bg: '#a80000', label: 'EXE' }, msi: { bg: '#a80000', label: 'MSI' }, bat: { bg: '#a80000', label: 'BAT' }, cmd: { bg: '#a80000', label: 'CMD' }, scr: { bg: '#a80000', label: 'SCR' }, vbs: { bg: '#a80000', label: 'VBS' }, js: { bg: '#a80000', label: 'JS' },
};
function attBadge(filename: string): { bg: string; label: string } {
  const ext = (filename.split('.').pop() || '').toLowerCase();
  return EXT_BADGE[ext] || { bg: '#605e5c', label: (ext || '?').toUpperCase().slice(0, 4) };
}

const estiloOpcion: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 10, width: '100%', textAlign: 'left', padding: '8px 14px',
  border: 'none', fontSize: 13, cursor: 'pointer', whiteSpace: 'nowrap', textDecoration: 'none',
};
const svg = (d: string) => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#605e5c" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={d} /></svg>
);

interface Props {
  folder: string; uid: number; att: AttachmentInfo;
  onAbrir: () => void;
  compacto?: boolean;
}

export function TarjetaAdjunto({ folder, uid, att, onAbrir, compacto = false }: Props) {
  // Posición del menú en pantalla: la lista de adjuntos recorta lo que sobresale, así que el menú va «fixed».
  const [menu, setMenu] = useState<{ top: number; right: number } | null>(null);
  const [guardar, setGuardar] = useState(false);
  const caja = useRef<HTMLSpanElement>(null);
  const url = `/api/mail/attachment/${encodeURIComponent(folder)}/${uid}/${att.part_number}/${encodeURIComponent(att.filename)}`;
  const b = attBadge(att.filename);

  useEffect(() => {
    if (!menu) return;
    const fuera = (e: MouseEvent) => { if (caja.current && !caja.current.contains(e.target as Node)) setMenu(null); };
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setMenu(null); };
    const cerrar = () => setMenu(null);
    document.addEventListener('mousedown', fuera);
    document.addEventListener('keydown', esc);
    window.addEventListener('resize', cerrar);
    document.addEventListener('scroll', cerrar, true);
    return () => { document.removeEventListener('mousedown', fuera); document.removeEventListener('keydown', esc); window.removeEventListener('resize', cerrar); document.removeEventListener('scroll', cerrar, true); };
  }, [menu]);

  return (
    <span ref={caja} className="hover:!bg-[#f3f2f1] bg-white border border-[#e1dfdd]" style={{
      position: 'relative', display: 'inline-flex', alignItems: 'stretch', width: compacto ? 190 : 230,
      borderRadius: 6, overflow: 'visible',
    }}>
      <button type="button" onClick={onAbrir}
        title={`${att.filename} (${formatSize(att.size ?? 0)})${att.dentro_de ? ` — viene dentro del correo adjunto «${att.dentro_de}»` : ''}`}
        style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: 8, padding: compacto ? '4px 6px' : '6px 8px', border: 'none', background: 'transparent', cursor: 'pointer', textAlign: 'left' }}>
        <span style={{ background: b.bg, color: '#fff', fontSize: compacto ? 9 : 10, fontWeight: 700, width: compacto ? 26 : 32, height: compacto ? 26 : 32, borderRadius: 4, flexShrink: 0, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', letterSpacing: 0.3 }}>{b.label}</span>
        <span style={{ minWidth: 0, display: 'flex', flexDirection: 'column' }}>
          <span className="text-[#323130]" style={{ fontSize: compacto ? 12 : 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{att.filename}</span>
          <span className="text-[#605e5c]" style={{ fontSize: 11 }}>{formatSize(att.size ?? 0)}</span>
        </span>
      </button>
      <button type="button" onClick={() => { if (menu) { setMenu(null); return; } const r = caja.current!.getBoundingClientRect(); setMenu({ top: r.bottom + 4, right: Math.max(8, window.innerWidth - r.right) }); }} aria-label={`Más acciones para ${att.filename}`} aria-haspopup="menu" aria-expanded={!!menu}
        className="hover:!bg-[#edebe9] text-[#605e5c]" style={{ width: 26, border: 'none', borderLeft: '1px solid transparent', background: 'transparent', cursor: 'pointer', borderRadius: '0 6px 6px 0', flexShrink: 0 }}>
        <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor" aria-hidden="true"><path d="M1.5 3.2L5 6.8l3.5-3.6z" /></svg>
      </button>
      {menu && (
        <div role="menu" className="bg-white border border-[#e1dfdd]" style={{ position: 'fixed', top: menu.top, right: menu.right, zIndex: 60, minWidth: 200, borderRadius: 6, boxShadow: '0 6px 20px rgba(0,0,0,0.14)', padding: '4px 0' }}>
          <button type="button" role="menuitem" className="bg-transparent hover:bg-[#f3f2f1] text-[#323130]" style={estiloOpcion} onClick={() => { setMenu(null); onAbrir(); }}>{svg('M1.5 8s2.4-4.5 6.5-4.5S14.5 8 14.5 8 12.1 12.5 8 12.5 1.5 8 1.5 8zM8 10a2 2 0 100-4 2 2 0 000 4z')}Vista previa</button>
          <a role="menuitem" href={url} download={att.filename} className="bg-transparent hover:bg-[#f3f2f1] text-[#323130]" style={estiloOpcion} onClick={() => setMenu(null)}>{svg('M8 2v8.5M4.8 7.5L8 10.7l3.2-3.2M2.5 12.5v1.5h11v-1.5')}Descargar</a>
          <button type="button" role="menuitem" className="bg-transparent hover:bg-[#f3f2f1] text-[#323130]" style={estiloOpcion} onClick={() => { setMenu(null); setGuardar(true); }}>{svg('M4.5 12.5h7.2a2.8 2.8 0 00.4-5.6A4 4 0 004.3 6a3.2 3.2 0 00.2 6.5z')}Guardar en Archivos</button>
        </div>
      )}
      {guardar && <BotonGuardarEnAlmacen folder={folder} uid={uid} att={att} abiertoDesdeFuera onCerrar={() => setGuardar(false)} />}
    </span>
  );
}
