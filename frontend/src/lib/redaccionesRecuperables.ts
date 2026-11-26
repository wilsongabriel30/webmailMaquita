/**
 * Correos a medio escribir que sobreviven a una recarga de la página (13/10/2026).
 *
 * La copia de estadoRedaccion.ts vive en memoria: aguanta minimizar o cambiar de carpeta,
 * pero una recarga (versión nueva del webmail, cambio de cuenta, un fallo de carga, F5) la
 * borraba y lo escrito quedaba solo en Borradores, a veces sin lo último ni los adjuntos.
 *
 * Aquí se guarda en sessionStorage —es de la pestaña, sobrevive a la recarga y no se cruza
 * con otras pestañas— lo mínimo para reabrir cada ventana: destinatarios, asunto, texto y el
 * UID del borrador del servidor (que tiene los adjuntos). Se anota al escribir, al guardar el
 * borrador y justo antes de salir de la página. Al volver a cargar, RecuperarRedacciones.tsx
 * reabre las ventanas como «Editar borrador», con el texto más reciente.
 *
 * La clave lleva la persona y la cuenta activa: cada cuenta recupera solo lo suyo.
 */
import { cuentaActiva } from './cuentaActiva';

export interface RedaccionGuardada {
  id: string;
  draftUid: number | null;
  to: string;
  cc: string;
  bcc: string;
  subject: string;
  /** Cuerpo + cita, sin firma (igual que el borrador del servidor). */
  html: string;
  inReplyTo: string;
  references: string;
  actualizado: number;
}

function duenio(): string {
  let persona = '';
  try {
    persona = (JSON.parse(localStorage.getItem('ultima_sesion') || 'null')?.username || '').toLowerCase();
  } catch {
    /* sin almacenamiento: clave sin persona */
  }
  return `${persona}:${cuentaActiva() || 'propia'}`;
}

function clave(): string {
  return `maquita_redacciones:${duenio()}`;
}

/*
 * Copia de reserva fuera de la pestaña (13/11/2026). sessionStorage se pierde si la sesión vence
 * y se vuelve a entrar desde otra ventana, si se cierra la pestaña o si la aplicación de
 * escritorio abre una ventana nueva: la persona perdía lo escrito. La misma lista se guarda
 * además en localStorage, con la pestaña que la escribió y la hora del último latido. Otra
 * pestaña solo la recoge cuando su dueña ya no está: se despidió (cerró o salió de la página)
 * hace unos segundos, o dejó de latir (se colgó o la cerraron de golpe).
 */
export const PREFIJO_RESERVA = 'maquita_redacciones_reserva:';
const ESPERA_DESPEDIDA_MS = 15_000;
const ESPERA_SIN_LATIDO_MS = 90_000;
const CADUCA_RESERVA_MS = 3 * 24 * 3600 * 1000;

interface Reserva {
  latido: number;
  despedida: boolean;
  todas: Record<string, RedaccionGuardada>;
}

function idPestana(): string {
  try {
    let id = sessionStorage.getItem('maquita_pestana');
    if (!id) {
      id = Math.random().toString(36).slice(2) + Date.now().toString(36);
      sessionStorage.setItem('maquita_pestana', id);
    }
    return id;
  } catch {
    return 'sin-pestana';
  }
}

/*
 * Señal de vida de la pestaña (15/11/2026). El latido depende de temporizadores, y el navegador los
 * frena o congela en las pestañas de fondo (ahorro de memoria, «pestañas en suspensión»): una
 * pestaña abierta parecía abandonada, otra recogía su correo y quedaban dos ventanas con el mismo
 * correo (borradores y envíos repetidos). Un candado del navegador dura mientras la pestaña
 * exista, aunque esté congelada, y se suelta solo cuando se cierra o sale de la página.
 */
const PREFIJO_CANDADO = 'maquita-pestana-viva:';
let senalPuesta = false;

export function sostenerSenalDeVida(): void {
  if (senalPuesta) return;
  senalPuesta = true;
  try {
    navigator.locks?.request(PREFIJO_CANDADO + idPestana(), () => new Promise<void>(() => { /* hasta que la pestaña se cierre */ }))
      ?.catch(() => { /* sin candados: queda el latido */ });
  } catch {
    /* navegador sin candados: queda el latido */
  }
}

/** Pestañas de este navegador que siguen abiertas; null si el navegador no lo sabe decir. */
export async function pestanasVivas(): Promise<Set<string> | null> {
  try {
    if (!navigator.locks?.query) return null;
    const estado = await navigator.locks.query();
    const vivas = new Set<string>();
    for (const c of estado.held || []) {
      if (c.name?.startsWith(PREFIJO_CANDADO)) vivas.add(c.name.slice(PREFIJO_CANDADO.length));
    }
    return vivas;
  } catch {
    return null;
  }
}

function claveReserva(): string {
  return `${PREFIJO_RESERVA}${duenio()}:${idPestana()}`;
}

function escribirReserva(todas: Record<string, RedaccionGuardada>, despedida = false): void {
  try {
    if (Object.keys(todas).length) {
      const reserva: Reserva = { latido: Date.now(), despedida, todas };
      localStorage.setItem(claveReserva(), JSON.stringify(reserva));
    } else {
      localStorage.removeItem(claveReserva());
    }
  } catch {
    /* almacenamiento lleno o bloqueado: queda la copia de la pestaña */
  }
}

/** La pestaña sigue viva: renueva la hora de su copia de reserva (si tiene alguna). */
export function latirReserva(): void {
  try {
    const cruda = localStorage.getItem(claveReserva());
    if (!cruda) return;
    const reserva = JSON.parse(cruda) as Reserva;
    reserva.latido = Date.now();
    reserva.despedida = false;
    localStorage.setItem(claveReserva(), JSON.stringify(reserva));
  } catch {
    /* nada */
  }
}

/**
 * Redacciones de la misma persona y cuenta que quedaron sin pestaña. Se retiran al leerlas.
 * `yaAbiertas`: UID de borrador que esta pestaña ya tiene en pantalla (no se repiten).
 * `vivas`: pestañas que siguen abiertas (pestanasVivas); lo suyo no se toca aunque no latan.
 */
export function tomarRedaccionesHuerfanas(yaAbiertas: Array<number | null> = [], vivas: Set<string> | null = null): RedaccionGuardada[] {
  const halladas: RedaccionGuardada[] = [];
  try {
    const prefijo = `${PREFIJO_RESERVA}${duenio()}:`;
    const propia = claveReserva();
    const ahora = Date.now();
    const claves: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.startsWith(prefijo) && k !== propia) claves.push(k);
    }
    for (const k of claves) {
      if (vivas?.has(k.slice(prefijo.length))) continue;   // su pestaña sigue abierta
      let reserva: Reserva | null = null;
      try { reserva = JSON.parse(localStorage.getItem(k) || 'null') as Reserva | null; } catch { reserva = null; }
      if (!reserva || typeof reserva.latido !== 'number' || !reserva.todas) { localStorage.removeItem(k); continue; }
      const edad = ahora - reserva.latido;
      if (edad > CADUCA_RESERVA_MS) { localStorage.removeItem(k); continue; }
      // Si los candados del navegador confirman que la pestaña ya no existe (vivas != null y no la
      // incluye), se recupera YA. El margen de espera solo hace falta cuando NO se puede saber si la
      // pestaña sigue viva pero congelada (navegador sin candados): así un webview caído/reconstruido
      // devuelve de inmediato lo que se estaba escribiendo, en vez de esperar 90 s (25/11/2026).
      if (vivas === null && edad < (reserva.despedida ? ESPERA_DESPEDIDA_MS : ESPERA_SIN_LATIDO_MS)) continue;
      localStorage.removeItem(k);
      for (const r of Object.values(reserva.todas)) {
        if (vacia(r)) continue;
        if (r.draftUid && yaAbiertas.includes(r.draftUid)) continue;
        halladas.push(r);
      }
    }
  } catch {
    /* sin almacenamiento: no hay nada que recoger */
  }
  return halladas.sort((a, b) => a.actualizado - b.actualizado);
}

function leerTodas(): Record<string, RedaccionGuardada> {
  try {
    return JSON.parse(sessionStorage.getItem(clave()) || '{}') || {};
  } catch {
    return {};
  }
}

function escribirTodas(todas: Record<string, RedaccionGuardada>): void {
  try {
    if (Object.keys(todas).length) sessionStorage.setItem(clave(), JSON.stringify(todas));
    else sessionStorage.removeItem(clave());
  } catch {
    /* almacenamiento lleno o bloqueado: queda el borrador del servidor */
  }
  escribirReserva(todas);
}

/** Sin destinatarios, asunto ni texto: no hay nada que recuperar. */
function vacia(r: RedaccionGuardada): boolean {
  const texto = r.html.replace(/<img\b/gi, 'x<').replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').trim();
  return !r.to.trim() && !r.cc.trim() && !r.bcc.trim() && !r.subject.trim() && !texto && !r.draftUid;
}

export function anotarRedaccion(r: RedaccionGuardada): void {
  const todas = leerTodas();
  if (vacia(r)) delete todas[r.id];
  else todas[r.id] = { ...r, actualizado: Date.now() };
  escribirTodas(todas);
}

/** La ventana se cerró o se envió: ya no hay nada que recuperar. */
export function olvidarRedaccion(id: string): void {
  const todas = leerTodas();
  if (!(id in todas)) return;
  delete todas[id];
  escribirTodas(todas);
}

/** Lo que había abierto en esta pestaña y cuenta; se vacía al leerlo (las ventanas nuevas se vuelven a anotar). */
export function tomarRedaccionesGuardadas(): RedaccionGuardada[] {
  const todas = Object.values(leerTodas()).filter(r => !vacia(r));
  try {
    sessionStorage.removeItem(clave());
    localStorage.removeItem(claveReserva());
  } catch {
    /* nada */
  }
  return todas.sort((a, b) => a.actualizado - b.actualizado);
}

// Ventanas abiertas en pantalla: cada una deja aquí cómo sacar su foto al momento.
const fuentes = new Map<string, () => RedaccionGuardada | null>();

export function registrarFuente(id: string, foto: () => RedaccionGuardada | null): () => void {
  fuentes.set(id, foto);
  return () => {
    if (fuentes.get(id) === foto) fuentes.delete(id);
  };
}

/** Anota ya lo que hay en pantalla en todas las ventanas (antes de salir de la página). */
export function volcarRedacciones(): void {
  for (const foto of fuentes.values()) {
    try {
      const r = foto();
      if (r) anotarRedaccion(r);
    } catch {
      /* una ventana a medio desmontar no impide guardar las demás */
    }
  }
  // La pestaña se va: su copia de reserva queda libre para la próxima ventana de la persona.
  escribirReserva(leerTodas(), true);
}
