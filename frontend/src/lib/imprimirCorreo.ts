/**
 * Impresión de un correo en A4 (07/11/2026).
 *
 * Antes se escribía la página y se llamaba a print() en el acto: el navegador imprimía antes de
 * pintar el cuerpo (sobre todo con imágenes incrustadas) y salía solo la cabecera. Ahora la
 * ventana espera a que carguen la página y todas las imágenes (tope de 8 s) y recién entonces
 * imprime. La hoja es A4 con márgenes, el cuerpo ocupa todo el ancho y las imágenes y tablas se
 * ajustan a la página. Incluye la lista de adjuntos.
 */
import { escapeHtml } from './citaRespuesta';

export interface DatosImpresion {
  asunto: string; de: string; para: string; cc?: string; fecha: string;
  /** HTML ya saneado (DOMPurify). */
  cuerpoHtml: string;
  adjuntos?: string[];
}

const ESPERA_MAXIMA_MS = 8000;

export function imprimirCorreo(d: DatosImpresion): boolean {
  const ventana = window.open('', '_blank');
  if (!ventana) return false;
  const asunto = escapeHtml(d.asunto || '(Sin asunto)');
  const adjuntos = (d.adjuntos || []).map(escapeHtml);
  ventana.document.write(`<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data: https: cid:; style-src 'unsafe-inline'; font-src data:">
<meta name="color-scheme" content="only light">
<title>${asunto}</title>
<style>
  @page { size: A4; margin: 15mm 14mm; }
  html, body { background: #fff; }
  body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 16px; color: #323130; font-size: 12.5pt; line-height: 1.5; word-break: break-word; }
  .cabecera { border-bottom: 1px solid #c8c6c4; padding-bottom: 10px; margin-bottom: 14px; }
  .asunto { font-size: 17pt; font-weight: 600; margin: 0 0 8px; }
  .meta { font-size: 10.5pt; color: #444; line-height: 1.6; }
  .adjuntos { font-size: 10.5pt; color: #444; margin-top: 6px; }
  .cuerpo img { max-width: 100% !important; height: auto !important; page-break-inside: avoid; }
  .cuerpo table { max-width: 100% !important; border-collapse: collapse; }
  .cuerpo pre { white-space: pre-wrap; }
  .cuerpo a { color: #0078d4; }
  @media print { body { padding: 0; } .aviso { display: none; } }
  .aviso { font-size: 10pt; color: #605e5c; margin-top: 18px; border-top: 1px dashed #c8c6c4; padding-top: 8px; }
</style>
</head><body>
<div class="cabecera">
  <h1 class="asunto">${asunto}</h1>
  <div class="meta">
    <b>De:</b> ${escapeHtml(d.de || '')}<br>
    <b>Para:</b> ${escapeHtml(d.para || '')}<br>
    ${d.cc ? `<b>CC:</b> ${escapeHtml(d.cc)}<br>` : ''}
    <b>Fecha:</b> ${escapeHtml(d.fecha || '')}
  </div>
  ${adjuntos.length ? `<div class="adjuntos"><b>Adjuntos (${adjuntos.length}):</b> ${adjuntos.join(' · ')}</div>` : ''}
</div>
<div class="cuerpo">${d.cuerpoHtml}</div>
<p class="aviso">Si el cuadro de impresión no aparece, use Ctrl+P (Cmd+P en Mac).</p>
</body></html>`);
  ventana.document.close();

  // Imprimir solo cuando la página y sus imágenes están listas.
  const imprimir = () => { try { ventana.focus(); ventana.print(); } catch { /* ventana cerrada */ } };
  const esperarImagenes = () => {
    const imgs = Array.from(ventana.document.images);
    const pendientes = imgs.filter(i => !i.complete).map(i => new Promise<void>(r => { i.onload = () => r(); i.onerror = () => r(); }));
    const tope = new Promise<void>(r => setTimeout(r, ESPERA_MAXIMA_MS));
    Promise.race([Promise.all(pendientes).then(() => undefined), tope]).then(() => setTimeout(imprimir, 150));
  };
  if (ventana.document.readyState === 'complete') esperarImagenes();
  else ventana.addEventListener('load', esperarImagenes, { once: true });
  return true;
}
