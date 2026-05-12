import { useRef } from 'react';
import { sanitizeHtml } from '../../lib/sanitize';

interface SafeEmailViewerProps {
  htmlBody: string;
  className?: string;
  style?: React.CSSProperties;
}

/**
 * Renders email HTML in a sandboxed iframe with CSP meta tag.
 * Defense-in-depth: DOMPurify + iframe sandbox + CSP.
 */
export default function SafeEmailViewer({ htmlBody, className, style }: SafeEmailViewerProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);

  const sanitized = sanitizeHtml(htmlBody);

  const srcDoc = `<!DOCTYPE html><html><head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src https: data: cid:; style-src 'unsafe-inline'; font-src https:;">
<style>
  body { margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 14px; line-height: 1.6; color: #323130; word-break: break-word; }
  a { color: #0078d4 !important; text-decoration: underline !important; cursor: pointer !important; }
  a:hover { color: #106ebe !important; }
  img { max-width: 100%; height: auto; }
  table { max-width: 100%; }
  pre { white-space: pre-wrap; word-break: break-word; }
</style>
</head><body>${sanitized}</body></html>`;

  return (
    <iframe
      ref={iframeRef}
      sandbox="allow-popups allow-popups-to-escape-sandbox"
      srcDoc={srcDoc}
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
  );
}
