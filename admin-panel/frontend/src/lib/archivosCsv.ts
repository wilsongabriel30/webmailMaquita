/**
 * Leer y descargar archivos CSV en el navegador (importación de cuentas).
 * El contenido de los CSV descargados ya viene escapado del servidor contra fórmulas (=, +, -, @).
 */

/** Texto del archivo: UTF-8 (con o sin BOM) y, si no lo es, Windows-1252, que es lo que guarda Excel por defecto. */
export async function leerTextoCsv(archivo: File): Promise<string> {
  const bytes = await archivo.arrayBuffer();
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    return new TextDecoder("windows-1252").decode(bytes);
  }
}

/** Descarga un CSV con BOM, para que Excel reconozca las tildes. */
export function descargarCsv(nombre: string, contenido: string) {
  const url = URL.createObjectURL(new Blob(["﻿" + contenido], { type: "text/csv;charset=utf-8" }));
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = nombre;
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const PLANTILLA_CSV = "correo,nombre,clave,cuota_mb,alias\r\nana.perez@example.org,Ana Pérez,,1024,ventas@example.org;info@example.org\r\n";
