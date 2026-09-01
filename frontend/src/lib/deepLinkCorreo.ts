/**
 * Enlace directo a un correo: /webmail/?folder=INBOX&uid=241 (lo usa el Drive «Archivos del correo» y la app).
 * Selecciona la carpeta y abre el mensaje al cargar. Sin parámetros no hace nada.
 */
import { useEffect } from "react";
import { api } from "../api/client";
import { useMailStore } from "../store/mailStore";

export function useDeepLinkCorreo() {
  useEffect(() => {
    let params: URLSearchParams;
    try { params = new URLSearchParams(window.location.search); } catch { return; }
    const folder = params.get("folder");
    const uid = params.get("uid");
    if (!folder || !uid || !/^\d+$/.test(uid)) return;
    const st = useMailStore.getState();
    try { st.setCurrentFolder(folder); } catch {}
    api.get(`/mail/message/${encodeURIComponent(folder)}/${uid}`)
      .then((msg: any) => { if (msg && msg.uid) useMailStore.getState().setSelectedMessage(msg); })
      .catch(() => {});
  }, []);
}

/** Texto único de advertencia al eliminar definitivamente correos (también quita sus adjuntos de «Archivos del correo»). */
export const AVISO_ELIMINAR_CORREO =
  "Esta acción no es reversible: el correo y sus archivos adjuntos se eliminarán permanentemente (también de «Archivos del correo» en tu Drive). ¿Deseas continuar?";
