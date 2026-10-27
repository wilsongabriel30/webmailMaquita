// Datos iniciales del evento que nace al arrastrar un correo al Calendario, como en Outlook:
// título «RE: asunto», el remitente como asistente, la próxima media hora libre del reloj,
// videollamada activada y el correo completo citado en la descripción.
import type { MessageFull } from "../../types";

/** Lo que se guarda en el arrastre (MessageList) para saber qué correo se soltó. */
export interface CorreoArrastrado {
  subject?: string;
  from?: string;
  date?: string;
  uid?: number;
  folder?: string;
}

export interface EventoInicial {
  fecha: Date;
  /** Hora de inicio con fracción: 15.5 = 15:30 (así la entiende EventModal). */
  hora: number;
  titulo: string;
  asistentes: string[];
  descripcion: string;
}

/** Nombre del evento que dispara el soltado sobre el ícono Calendario (NavRail → EventoDesdeCorreo). */
export const EVENTO_DESDE_CORREO = "evento-desde-correo";

/** Tope de la descripción: un correo enorme no debe volver inmanejable el evento. */
const MAX_DESCRIPCION = 20000;

/** Dirección de «Nombre <correo@dominio>» o de la dirección suelta. */
export function direccionDe(texto: string): string {
  const m = /<([^>]+)>/.exec(texto || "");
  const dir = (m ? m[1] : texto || "").trim();
  return /^[^\s@]+@[^\s@]+$/.test(dir) ? dir : "";
}

/** Próxima media hora en punto (14:10 → 14:30; 14:40 → 15:00), como propone Outlook. */
export function proximaMediaHora(ahora: Date = new Date()): Date {
  const d = new Date(ahora);
  d.setSeconds(0, 0);
  const min = d.getMinutes();
  if (min < 30) d.setMinutes(30);
  else { d.setMinutes(0); d.setHours(d.getHours() + 1); }
  return d;
}

/** Texto del correo: el texto plano si lo trae; si solo trae HTML, su texto visible. */
function textoDelCorreo(msg: MessageFull | null): string {
  if (!msg) return "";
  if (msg.text_body && msg.text_body.trim()) return msg.text_body.trim();
  if (!msg.html_body) return "";
  const doc = new DOMParser().parseFromString(msg.html_body, "text/html");
  doc.querySelectorAll("script, style, head").forEach((n) => n.remove());
  return (doc.body?.innerText || doc.body?.textContent || "").replace(/\n{3,}/g, "\n\n").trim();
}

function fechaLarga(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString("es-EC", { weekday: "long", day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

/** Arma el evento a partir del correo soltado. `msg` puede faltar si no se pudo leer el correo completo. */
export function eventoDesdeCorreo(meta: CorreoArrastrado, msg: MessageFull | null): EventoInicial {
  const inicio = proximaMediaHora();
  const asunto = (msg?.subject ?? meta.subject ?? "").trim();
  const titulo = asunto ? (/^re:/i.test(asunto) ? asunto : `RE: ${asunto}`) : "Evento desde correo";
  const remitente = msg?.from_addr || direccionDe(msg?.from || meta.from || "");

  const cabecera = [
    "________________________________",
    `De: ${msg?.from || meta.from || ""}`,
    `Enviado: ${fechaLarga(msg?.date ?? meta.date)}`,
    msg?.to ? `Para: ${msg.to}` : "",
    msg?.cc ? `CC: ${msg.cc}` : "",
    `Asunto: ${asunto}`,
  ].filter(Boolean).join("\n");
  let descripcion = `\n\n${cabecera}\n\n${textoDelCorreo(msg)}`;
  if (descripcion.length > MAX_DESCRIPCION) descripcion = descripcion.slice(0, MAX_DESCRIPCION) + "\n[…]";

  return {
    fecha: new Date(inicio.getFullYear(), inicio.getMonth(), inicio.getDate()),
    hora: inicio.getHours() + inicio.getMinutes() / 60,
    titulo,
    asistentes: remitente ? [remitente] : [],
    descripcion,
  };
}
