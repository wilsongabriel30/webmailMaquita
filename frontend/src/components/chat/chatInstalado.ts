/**
 * ¿Tiene esta instalación el servicio de chat (y, con él, las videollamadas)? Sin chat no se ofrece la
 * «Videollamada» en el calendario ni se llama a `/api/chat/*`: antes cada evento con invitados dejaba un
 * 404 de `/api/chat/reuniones` en la consola (informe de Andes, 15/11/2026).
 *
 * La respuesta sale de `/api/chat-config` (pública; el servidor ya da el chat por inactivo donde no existe)
 * y se pregunta UNA vez por sesión de navegador. Además, un 404 de una ruta del chat se anota aquí como
 * «no instalado» para no volver a pedirla hasta recargar la página.
 */
import { useSyncExternalStore } from "react";

const URL_POR_OMISION = "/chat/?embed=1";

/** null = todavía no se sabe (o la consulta falló y se reintentará). */
let instalado: boolean | null = null;
let urlIncrustada = URL_POR_OMISION;
/** false cuando `/api/chat/reuniones` respondió 404: hay chat (p. ej. en otra máquina) pero no reuniones aquí. */
let reuniones = true;
let peticion: Promise<boolean | null> | null = null;
const oyentes = new Set<() => void>();

function avisar(): void {
  oyentes.forEach((f) => f());
}

function suscribir(f: () => void): () => void {
  oyentes.add(f);
  return () => { oyentes.delete(f); };
}

/** Pregunta al servidor (una sola vez) si el chat está activo. Devuelve null si no se pudo saber. */
export function consultarChatInstalado(): Promise<boolean | null> {
  if (instalado !== null) return Promise.resolve(instalado);
  if (!peticion) {
    peticion = fetch("/api/chat-config", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { enabled?: unknown; embed_url?: string } | null) => {
        // Si mientras tanto un 404 ya dijo «no instalado», esa respuesta manda.
        if (instalado === null) {
          if (d && typeof d.enabled === "boolean") {
            instalado = d.enabled;
            if (d.embed_url) urlIncrustada = d.embed_url;
          } else if (d) {
            instalado = false;   // respuesta sin el dato: se trata como sin chat, igual que antes
          } else {
            peticion = null;     // fallo pasajero: no se memoriza, se volverá a preguntar
          }
        }
        avisar();
        return instalado;
      })
      .catch(() => { peticion = null; return instalado; });
  }
  return peticion;
}

/** Dirección del chat incrustado que guardó el panel de administración. */
export function urlChatIncrustado(): string {
  return urlIncrustada;
}

/** Una ruta del chat respondió 404 en este mismo origen: el servicio no está instalado. */
export function anotarChatNoInstalado(): void {
  if (instalado === false) return;
  instalado = false;
  avisar();
}

/** `/api/chat/reuniones` respondió 404: no se vuelve a ofrecer ni a pedir la videollamada en esta sesión. */
export function anotarReunionesNoDisponibles(): void {
  if (!reuniones) return;
  reuniones = false;
  avisar();
}

/** ¿Se puede crear la videollamada? Solo es «no» ante una negativa clara; si no se sabe, se intenta. */
export async function videollamadaDisponible(): Promise<boolean> {
  if (!reuniones) return false;
  return (await consultarChatInstalado()) !== false && reuniones;
}

function fotoVideollamada(): boolean {
  return reuniones && instalado !== false;
}

/** Para el formulario del evento: false cuando no debe ofrecerse la «Videollamada». */
export function useVideollamadaDisponible(): boolean {
  const valor = useSyncExternalStore(suscribir, fotoVideollamada);
  if (instalado === null) void consultarChatInstalado();
  return valor;
}

/** ¿El error del cliente de la API corresponde a un 404 (ruta inexistente)? */
export function esErrorNoEncontrado(e: unknown): boolean {
  const texto = e instanceof Error ? e.message : "";
  return /^(HTTP 404|Not Found)$/i.test(texto.trim());
}
