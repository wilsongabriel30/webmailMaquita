/**
 * Enlace directo a un correo: /webmail/?folder=INBOX&uid=241 (lo usa el Drive «Archivos del correo» y la app).
 * Selecciona la carpeta y abre el mensaje al cargar. Sin parámetros no hace nada.
 */
import { useEffect } from "react";
import { api } from "../api/client";
import { useMailStore } from "../store/mailStore";
import type { MessageFull } from "../types";

/** Selecciona la carpeta y abre el correo indicado. Devuelve false si no se pudo abrir.
 *  También lo usan las fuentes del panel del asistente (27/10/2026). */
export async function abrirCorreoPorUid(folder: string, uid: string): Promise<boolean> {
  if (!folder || !/^\d+$/.test(uid)) return false;
  try { useMailStore.getState().setCurrentFolder(folder); } catch { /* carpeta inválida */ }
  try {
    const msg = await api.get<MessageFull>(`/mail/message/${encodeURIComponent(folder)}/${uid}`);
    if (!msg || !msg.uid) return false;
    useMailStore.getState().setSelectedMessage(msg);
    return true;
  } catch {
    return false;
  }
}

export function useDeepLinkCorreo() {
  useEffect(() => {
    let params: URLSearchParams;
    try { params = new URLSearchParams(window.location.search); } catch { return; }
    const folder = params.get("folder");
    const uid = params.get("uid");
    if (folder && uid) abrirCorreoPorUid(folder, uid);
  }, []);
}

/** Texto único de advertencia al eliminar definitivamente correos (también quita sus adjuntos de «Archivos del correo»). */
export const AVISO_ELIMINAR_CORREO =
  "Esta acción no es reversible: el correo y sus archivos adjuntos se eliminarán permanentemente (también de «Archivos del correo» en tu Drive). ¿Deseas continuar?";
