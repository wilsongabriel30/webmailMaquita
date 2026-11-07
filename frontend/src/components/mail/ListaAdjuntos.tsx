import { useLayoutEffect, useRef, useState } from 'react';
import { TarjetaAdjunto } from './TarjetaAdjunto';
import { formatSize } from '../../lib/tamanoAdjunto';
import type { AttachmentInfo } from '../../types';

/**
 * Lista de adjuntos de un correo (13/10/2026, sacada de MessageView).
 *
 * Antes la lista se pintaba entera, fuera de la zona que se desplaza: un correo con
 * muchos adjuntos llenaba la pantalla de una laptop y el cuerpo quedaba en una franja
 * mínima, difícil de leer y de usar. Ahora muestra como mucho dos filas y un botón
 * «Ver los N adjuntos» que despliega el resto con su propio desplazamiento.
 */

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
  const altoPlegado = compacto ? 76 : 100;

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
  const total = attachments.filter(a => !a.is_inline).reduce((s, a) => s + (a.size || 0), 0);
  return (
    <div>
      {/* Como Outlook (07/11/2026): «N archivos adjuntos (tamaño)» y «Descargar todo» arriba de las tarjetas */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: fs, color: '#605e5c', marginBottom: 6 }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" style={{ flexShrink: 0 }} aria-hidden="true"><path d="M13.5 7.5l-5 5a3 3 0 01-4.2-4.2l5.6-5.6a2 2 0 012.8 2.8l-5.6 5.6a1 1 0 01-1.4-1.4l5-5" /></svg>
          {visibles === 1 ? '1 archivo adjunto' : `${visibles} archivos adjuntos`} ({formatSize(total)})
        </span>
        {visibles > 1 && (
          <a href={`/api/mail/attachments-zip/${encodeURIComponent(folder)}/${uid}`} download
            title="Descargar todos los adjuntos como ZIP"
            style={{ color: '#0078d4', textDecoration: 'none', fontWeight: 600 }}>Descargar todo (.zip)</a>
        )}
      </div>
      <div
        ref={lista}
        style={{
          display: 'flex', flexWrap: 'wrap', gap: compacto ? 6 : 8, alignItems: 'center',
          maxHeight: abierta ? '40vh' : altoPlegado,
          overflowY: abierta ? 'auto' : 'hidden',
        }}
      >
        {attachments.map((att, i) => att.is_inline ? null : (
          <TarjetaAdjunto key={i} folder={folder} uid={uid} att={att} compacto={compacto} onAbrir={() => onAbrir(i)} />
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
