import { useCallback, useRef, useState } from 'react';
import { sanitizeHtml } from '../../lib/sanitize';
import VisorImagenCuerpo, { type ImagenCuerpo } from './VisorImagenCuerpo';

interface SafeEmailViewerProps {
  htmlBody: string;
  className?: string;
  style?: React.CSSProperties;
}

// Las imágenes más pequeñas que esto (iconos, píxeles de seguimiento, firmas) no se abren en grande.
const LADO_MINIMO = 80;

/**
 * Renders email HTML in a sandboxed iframe with CSP meta tag.
 * Defense-in-depth: DOMPurify + iframe sandbox + CSP.
 *
 * Clic en una imagen → visor en grande (08/10/2026). Para escuchar el clic desde fuera, el iframe lleva
 * `allow-same-origin`; sigue SIN `allow-scripts`, así que el HTML del correo no puede ejecutar nada
 * (la CSP del documento además prohíbe scripts). Solo cambia que el padre puede leer su DOM.
 */
export default function SafeEmailViewer({ htmlBody, className, style }: SafeEmailViewerProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [imagenes, setImagenes] = useState<ImagenCuerpo[]>([]);
  const [indice, setIndice] = useState<number | null>(null);

  const sanitized = sanitizeHtml(htmlBody);

  const srcDoc = `<!DOCTYPE html><html><head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src https: data: cid:; style-src 'unsafe-inline'; font-src https:;">
<style>
  body { margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 14px; line-height: 1.6; color: #323130; word-break: break-word; }
  a { color: #0078d4 !important; text-decoration: underline !important; cursor: pointer !important; }
  a:hover { color: #106ebe !important; }
  img { max-width: 100%; height: auto; }
  img[data-ampliable] { cursor: zoom-in; }
  table { max-width: 100%; }
  pre { white-space: pre-wrap; word-break: break-word; }
</style>
</head><body>${sanitized}</body></html>`;

  // Al cargar el iframe: marcar las imágenes ampliables y escuchar el clic sobre ellas.
  const alCargar = useCallback(() => {
    const doc = iframeRef.current?.contentDocument;
    if (!doc) return;
    const marcar = () => {
      doc.querySelectorAll('img').forEach(img => {
        const grande = (img.naturalWidth || img.width) >= LADO_MINIMO && (img.naturalHeight || img.height) >= LADO_MINIMO;
        if (grande && img.src) img.setAttribute('data-ampliable', '1'); else img.removeAttribute('data-ampliable');
      });
    };
    marcar();
    doc.querySelectorAll('img').forEach(img => img.addEventListener('load', marcar));
    doc.addEventListener('click', (e) => {
      const el = e.target as HTMLElement | null;
      if (!el || el.tagName !== 'IMG' || !el.hasAttribute('data-ampliable')) return;
      e.preventDefault();
      const lista = Array.from(doc.querySelectorAll('img[data-ampliable]')).map(i => ({
        src: (i as HTMLImageElement).src, alt: (i as HTMLImageElement).alt || '',
      }));
      const pos = Array.from(doc.querySelectorAll('img[data-ampliable]')).indexOf(el);
      setImagenes(lista);
      setIndice(pos >= 0 ? pos : 0);
    });
  }, []);

  return (
    <>
      <iframe
        ref={iframeRef}
        sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"
        srcDoc={srcDoc}
        onLoad={alCargar}
        className={className}
        style={{
          width: '100%',
          height: Math.min(Math.max(300, sanitized.length / 3), 2000),
          border: 'none',
          overflow: 'auto',
          ...style,
        }}
        title="Email content"
      />
      {indice !== null && imagenes.length > 0 && (
        <VisorImagenCuerpo imagenes={imagenes} indice={indice} onCerrar={() => setIndice(null)} onIr={setIndice} />
      )}
    </>
  );
}
