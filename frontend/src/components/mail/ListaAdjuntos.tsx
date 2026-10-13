import { useLayoutEffect, useRef, useState } from 'react';
import { BotonGuardarEnAlmacen } from '../files/GuardarEnAlmacen';
import type { AttachmentInfo } from '../../types';

/**
 * Lista de adjuntos de un correo (13/10/2026, sacada de MessageView).
 *
 * Antes la lista se pintaba entera, fuera de la zona que se desplaza: un correo con
 * muchos adjuntos llenaba la pantalla de una laptop y el cuerpo quedaba en una franja
 * mínima, difícil de leer y de usar. Ahora muestra como mucho dos filas y un botón
 * «Ver los N adjuntos» que despliega el resto con su propio desplazamiento.
 */

// Badge de tipo de archivo por extensión (color + etiqueta). Los ejecutables y
// comprimidos se resaltan para que el usuario note extensiones peligrosas/raras.
const EXT_BADGE: Record<string, { bg: string; label: string }> = {
  pdf: { bg: '#d13438', label: 'PDF' },
  doc: { bg: '#2b579a', label: 'DOC' }, docx: { bg: '#2b579a', label: 'DOC' }, rtf: { bg: '#2b579a', label: 'RTF' }, odt: { bg: '#2b579a', label: 'ODT' },
  xls: { bg: '#217346', label: 'XLS' }, xlsx: { bg: '#217346', label: 'XLS' }, csv: { bg: '#217346', label: 'CSV' }, ods: { bg: '#217346', label: 'ODS' },
  ppt: { bg: '#d24726', label: 'PPT' }, pptx: { bg: '#d24726', label: 'PPT' }, odp: { bg: '#d24726', label: 'ODP' },
  zip: { bg: '#8661c5', label: 'ZIP' }, rar: { bg: '#8661c5', label: 'RAR' }, '7z': { bg: '#8661c5', label: '7Z' }, gz: { bg: '#8661c5', label: 'GZ' }, tar: { bg: '#8661c5', label: 'TAR' },
  txt: { bg: '#605e5c', label: 'TXT' }, log: { bg: '#605e5c', label: 'LOG' },
  jpg: { bg: '#0b6a0b', label: 'IMG' }, jpeg: { bg: '#0b6a0b', label: 'IMG' }, png: { bg: '#0b6a0b', label: 'PNG' }, gif: { bg: '#0b6a0b', label: 'GIF' }, webp: { bg: '#0b6a0b', label: 'IMG' }, svg: { bg: '#0b6a0b', label: 'SVG' },
  exe: { bg: '#a80000', label: 'EXE' }, msi: { bg: '#a80000', label: 'MSI' }, bat: { bg: '#a80000', label: 'BAT' }, cmd: { bg: '#a80000', label: 'CMD' }, scr: { bg: '#a80000', label: 'SCR' }, vbs: { bg: '#a80000', label: 'VBS' }, js: { bg: '#a80000', label: 'JS' },
};
function attBadge(filename: string): { bg: string; label: string } {
  const ext = (filename.split('.').pop() || '').toLowerCase();
  return EXT_BADGE[ext] || { bg: '#605e5c', label: (ext || '?').toUpperCase().slice(0, 4) };
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface Props {
  folder: string;
  uid: number;
  attachments: AttachmentInfo[];
  /** Índice dentro de `attachments` (incluidos los inline), como espera la vista previa. */
  onAbrir: (index: number) => void;
  /** Tarjeta de un hilo: botones más pequeños y sin tamaño. */
  compacto?: boolean;
}

export default function ListaAdjuntos({ folder, uid, attachments, onAbrir, compacto = false }: Props) {
  const lista = useRef<HTMLDivElement>(null);
  // Desplegada solo para el correo en que se pidió: al cambiar de correo vuelve a plegarse.
  const [abiertaEn, setAbiertaEn] = useState('');
  const abierta = abiertaEn === `${folder}/${uid}`;
  const [desborda, setDesborda] = useState(false);
  const visibles = attachments.filter(a => !a.is_inline).length;
  // Dos filas de botones (los nombres largos ocupan hasta dos líneas).
  const altoPlegado = compacto ? 68 : 96;

  useLayoutEffect(() => {
    const el = lista.current;
    if (!el) return;
    // El observador avisa al empezar y en cada cambio de tamaño (ventana, panel, fuentes).
    const ro = new ResizeObserver(() => setDesborda(el.scrollHeight > altoPlegado + 4));
    ro.observe(el);
    return () => ro.disconnect();
  }, [attachments, altoPlegado]);

  if (visibles === 0) return null;

  const fs = compacto ? 11 : 12;
  return (
    <div>
      <div
        ref={lista}
        style={{
          display: 'flex', flexWrap: 'wrap', gap: compacto ? 6 : 8, alignItems: 'center',
          maxHeight: abierta ? '40vh' : altoPlegado,
          overflowY: abierta ? 'auto' : 'hidden',
        }}
      >
        {visibles > 1 && (
          <a
            href={`/api/mail/attachments-zip/${encodeURIComponent(folder)}/${uid}`}
            download
            style={compacto ? {
              display: 'inline-flex', alignItems: 'center', gap: 4,
              padding: '4px 10px', border: '1px solid #0078d4', borderRadius: 4,
              textDecoration: 'none', color: '#0078d4', fontSize: 11,
              background: '#f0f6ff', cursor: 'pointer', fontWeight: 600,
            } : {
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '6px 12px', border: '1px solid #0078d4', borderRadius: 4,
              textDecoration: 'none', color: 'white', fontSize: 12,
              background: '#0078d4', cursor: 'pointer', fontWeight: 600,
            }}
            title="Descargar todos los adjuntos como ZIP"
          >
            <svg width={compacto ? 12 : 14} height={compacto ? 12 : 14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            Descargar todo (.zip)
          </a>
        )}
        {attachments.map((att, i) => att.is_inline ? null : (
          <span key={i} style={{ display: 'inline-flex', gap: 2, alignItems: 'stretch' }}>
            <button
              onClick={() => onAbrir(i)}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: compacto ? 4 : 6,
                padding: compacto ? '4px 8px' : '6px 10px', border: '1px solid #d2d0ce', borderRadius: 4,
                textDecoration: 'none', color: '#323130', fontSize: fs,
                background: '#faf9f8', cursor: 'pointer',
              }}
              title={`${att.filename} (${formatSize(att.size)})`}
            >
              {(() => { const b = attBadge(att.filename); return (
                <span style={{ background: b.bg, color: '#fff', fontSize: compacto ? 9 : 10, fontWeight: 700, padding: compacto ? '2px 4px' : '2px 5px', borderRadius: 3, flexShrink: 0, letterSpacing: 0.3 }}>{b.label}</span>
              ); })()}
              <span style={{ maxWidth: compacto ? 150 : 200, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', wordBreak: 'break-all', lineHeight: compacto ? 1.2 : 1.25, textAlign: 'left' }}>
                {att.filename}
              </span>
              {!compacto && <span style={{ color: '#a19f9d' }}>({formatSize(att.size)})</span>}
            </button>
            <BotonGuardarEnAlmacen folder={folder} uid={uid} att={att} />
          </span>
        ))}
      </div>
      {(desborda || abierta) && (
        <button
          onClick={() => setAbiertaEn(abierta ? '' : `${folder}/${uid}`)}
          style={{
            marginTop: 6, padding: '2px 0', border: 'none', background: 'none',
            color: '#0078d4', fontSize: fs, fontWeight: 600, cursor: 'pointer',
          }}
          aria-expanded={abierta}
        >
          {abierta ? 'Mostrar menos ▴' : `Ver los ${visibles} adjuntos ▾`}
        </button>
      )}
    </div>
  );
}
