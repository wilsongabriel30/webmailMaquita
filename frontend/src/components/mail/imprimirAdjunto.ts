/**
 * Impresión de adjuntos desde la vista previa (06/11/2026).
 *
 * Antes «Imprimir» del navegador imprimía la página del webmail (el visor deforme). Ahora cada tipo
 * se imprime como documento:
 * - PDF: el propio visor de PDF del navegador (marco de la vista previa).
 * - Imagen / texto: una ventana solo con el contenido, a tamaño de página.
 * - Word/Excel/PowerPoint: el servidor de OnlyOffice genera la salida PDF paginada (lo mismo que
 *   hace su botón Imprimir) y se manda a imprimir desde un marco oculto. El archivo nunca se
 *   convierte para la persona: la descarga entrega el original.
 */
export type TipoAdjunto = 'image' | 'pdf' | 'office' | 'text' | 'email' | 'unsupported';

function imprimirEnMarco(src: string, esBlob = false): Promise<void> {
  return new Promise((resolve, reject) => {
    const marco = document.createElement('iframe');
    marco.style.cssText = 'position:fixed;right:0;bottom:0;width:1px;height:1px;border:0;opacity:0;pointer-events:none';
    marco.src = src;
    marco.onload = () => {
      try {
        // Un pequeño margen: Chromium necesita que el visor de PDF termine de pintar.
        setTimeout(() => {
          try { marco.contentWindow?.focus(); marco.contentWindow?.print(); resolve(); }
          catch (e) { reject(e); }
          finally { setTimeout(() => { marco.remove(); if (esBlob) URL.revokeObjectURL(src); }, 60_000); }
        }, 400);
      } catch (e) { reject(e); }
    };
    marco.onerror = () => reject(new Error('No se pudo cargar el documento'));
    document.body.appendChild(marco);
  });
}

function imprimirHtml(titulo: string, cuerpo: string): void {
  const html = `<!doctype html><html><head><meta charset="utf-8"><title>${titulo.replace(/</g, '&lt;')}</title>
<style>@page{margin:12mm}body{margin:0;font-family:Segoe UI,Arial,sans-serif;color:#000}img{max-width:100%;max-height:95vh;display:block;margin:0 auto}pre{white-space:pre-wrap;word-break:break-word;font:12px/1.4 Consolas,monospace}</style>
</head><body>${cuerpo}</body></html>`;
  const blob = new Blob([html], { type: 'text/html' });
  const src = URL.createObjectURL(blob);
  void imprimirEnMarco(src, true);
}

export async function imprimirAdjunto(args: {
  tipo: TipoAdjunto; url: string; filename: string; folder: string; uid: number; partNumber: string;
  marcoPdf?: HTMLIFrameElement | null; texto?: string;
}): Promise<'ok' | 'no-soportado'> {
  const { tipo, url, filename } = args;
  if (tipo === 'pdf') {
    if (args.marcoPdf?.contentWindow) {
      args.marcoPdf.contentWindow.focus();
      args.marcoPdf.contentWindow.print();
      return 'ok';
    }
    await imprimirEnMarco(url);
    return 'ok';
  }
  if (tipo === 'image') { imprimirHtml(filename, `<img src="${url}" alt="">`); return 'ok'; }
  if (tipo === 'text') {
    const t = (args.texto ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;');
    imprimirHtml(filename, `<pre>${t}</pre>`); return 'ok';
  }
  if (tipo === 'office') {
    const r = await fetch('/api/mail/office-print', {
      method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder: args.folder, uid: args.uid, part_number: args.partNumber, filename }),
    });
    if (!r.ok) throw new Error('No se pudo preparar el documento para imprimir');
    const src = URL.createObjectURL(await r.blob());
    await imprimirEnMarco(src, true);
    return 'ok';
  }
  return 'no-soportado';
}
