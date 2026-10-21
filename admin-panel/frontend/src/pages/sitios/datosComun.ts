/* Utilidades de la ventana «Archivos y datos» del sitio. */

/* Enlace de un solo uso que da el panel (válido 10 minutos): el navegador descarga directamente. */
export function abrirEnlace(enlace: string, nuevaPestana = false) {
  if (nuevaPestana) {
    window.open(enlace, "_blank", "noopener");
    return;
  }
  const a = document.createElement("a");
  a.href = enlace;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export function tamano(bytes: number | null | undefined): string {
  if (bytes == null) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1073741824) return `${(bytes / 1048576).toFixed(1)} MB`;
  return `${(bytes / 1073741824).toFixed(2)} GB`;
}

export const campo = "px-2 py-1.5 border border-ms-gray-40 rounded text-sm focus:outline-none focus:border-ms-blue";
