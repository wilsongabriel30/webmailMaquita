/* =============================================================================
   T-53 · Los avisos del navegador, con su icono y con clic que lleva a algún sitio
   -----------------------------------------------------------------------------
   QUE HACE: un único sitio desde el que salen todos los avisos del navegador, con
   el icono que corresponde a cada tipo y con un clic que SIEMPRE lleva a donde
   toca.
   POR QUE:  los avisos salían con el icono genérico del navegador —el «rayo
   morado» que vio dirección— y al pulsarlos no pasaba nada.

   LA CAUSA DEL RAYO: se pasaba `icon: '/webmail/favicon.svg'`, y **Chrome no
   admite SVG** en los avisos de escritorio: al no poder dibujarlo, pone el suyo.
   Con un PNG se ve el nuestro. No era que faltara el icono: es que era un formato
   que ese sitio no acepta.

   DONDE SE USA: useWebSocket.ts y MessageList.tsx. Nadie debería crear una
   Notification por su cuenta: si se hace, vuelve el rayo.
   ============================================================================= */

const ICONOS = {
  correo: '/webmail/icons/icono-correo-192.png',   // sobre sobre azul institucional
  tarea: '/webmail/icons/icon-192.png',
  recordatorio: '/webmail/icons/icon-192.png',
  general: '/webmail/icons/icon-192.png',
} as const;

export type TipoAviso = keyof typeof ICONOS;

/* Cuánto tiempo se considera que dos avisos son «el mismo».
 *
 * Cuatro segundos, no doce. Lo que hay que evitar es que los DOS emisores del MISMO suceso
 * -la conexión en tiempo real y el sondeo de respaldo- avisen por duplicado, y esos dos
 * disparan casi a la vez. Con una ventana larga se silenciaban correos DISTINTOS que
 * llegaban seguidos: se vio en el candado, un correo real que no producía ningún aviso
 * porque otro anterior había pasado por aquí hacía poco. Quedarse sin aviso es peor que
 * recibir dos. */
const VENTANA_MS = 4000;
const ultimos = new Map<string, number>();

/**
 * Del correo nuevo avisan DOS sitios: la conexión en tiempo real y el sondeo de respaldo
 * que mira la bandeja. Los dos hacen falta —si se cae el tiempo real, el sondeo salva el
 * aviso— pero cuando ambos funcionan, la persona recibe el aviso DOS VECES. Se vio en un
 * equipo real: un correo, dos avisos.
 *
 * Se resuelve aquí, en el único sitio por el que pasan todos: si ya salió un aviso igual
 * hace nada, el segundo se calla. Así ninguno de los dos emisores tiene que saber del otro
 * ni se pierde el respaldo.
 */
function esRepetido(clave: string): boolean {
  const ahora = Date.now();
  const previo = ultimos.get(clave);
  // se limpia lo viejo para que el mapa no crezca sin fin
  if (ultimos.size > 40) {
    for (const [k, t] of ultimos) if (ahora - t > VENTANA_MS) ultimos.delete(k);
  }
  if (previo && ahora - previo < VENTANA_MS) return true;
  ultimos.set(clave, ahora);
  return false;
}

/* El tiempo real y el sondeo de respaldo avisan del MISMO correo nuevo, y la ventana de cuatro segundos
 * no basta: el aviso en tiempo real pide recargar la lista y, si esa carga tarda más (IMAP lento, servidor
 * ocupado), el sondeo ve el mismo correo como nuevo y avisa otra vez (candado T-53 intermitente, 05/11/2026).
 * Por eso cada aviso que sale deja un «ya avisado» de su etiqueta para el OTRO emisor, que lo gasta en vez de
 * sonar. Funciona en los dos órdenes: con el servidor cargado, a veces el sondeo llega antes que el tiempo real.
 * Caducan al minuto: si uno de los dos se cae, el otro sigue avisando. */
const VIGENCIA_YA_AVISADO_MS = 60000;
const yaAvisados = { vivo: new Map<string, number[]>(), respaldo: new Map<string, number[]>() };
type Emisor = keyof typeof yaAvisados;

/** ¿El otro emisor ya avisó de esto? Si es así, se gasta su «ya avisado». */
function otroYaAviso(otro: Emisor, etiqueta: string): boolean {
  const ahora = Date.now();
  const vigentes = (yaAvisados[otro].get(etiqueta) || []).filter(t => ahora - t < VIGENCIA_YA_AVISADO_MS);
  const ya = vigentes.length > 0;
  if (ya) vigentes.shift();
  yaAvisados[otro].set(etiqueta, vigentes);
  return ya;
}

function anotarAviso(emisor: Emisor, etiqueta: string): void {
  yaAvisados[emisor].set(etiqueta, [...(yaAvisados[emisor].get(etiqueta) || []), Date.now()]);
}

interface Opciones {
  cuerpo: string;
  tipo?: TipoAviso;
  etiqueta?: string;
  /** A dónde lleva el clic. Si no se dice, a la bandeja de entrada. */
  destino?: string;
  /** Enlace externo (p. ej. la reunión de un recordatorio): el clic lo abre en otra pestaña. */
  enlaceExterno?: string;
  /** Correo concreto que abrir, si se sabe cuál es. */
  uid?: number;
  carpeta?: string;
  /** Aviso del sondeo de respaldo: se calla si el tiempo real ya avisó con la misma etiqueta (y al revés). */
  respaldo?: boolean;
}

/**
 * Saca un aviso del navegador. Devuelve si se pudo.
 *
 * El clic hace dos cosas, y las dos importan: **traer la ventana al frente** (que es lo que
 * la persona espera al pulsar) y **llevar a donde toca**. Antes no hacía ninguna de las dos.
 */
export function avisar(titulo: string, o: Opciones): boolean {
  if (typeof Notification === 'undefined' || Notification.permission !== 'granted') {
    return false;
  }
  // dos emisores para lo mismo no deben dar dos avisos
  // La clave incluye el TEXTO: dos correos distintos dicen cosas distintas y no deben
  // taparse entre sí. La etiqueta sola los hacía indistinguibles.
  const etiqueta = o.etiqueta || o.tipo || 'general';
  const emisor: Emisor = o.respaldo ? 'respaldo' : 'vivo';
  if (otroYaAviso(emisor === 'vivo' ? 'respaldo' : 'vivo', etiqueta)) return false;
  anotarAviso(emisor, etiqueta);
  if (esRepetido(etiqueta + '|' + titulo + '|' + o.cuerpo)) {
    return false;
  }

  try {
    const n = new Notification(titulo, {
      body: o.cuerpo,
      icon: ICONOS[o.tipo || 'general'],
      badge: ICONOS.general,
      tag: o.etiqueta,
    });

    n.onclick = () => {
      if (o.enlaceExterno) {
        window.open(o.enlaceExterno, '_blank', 'noopener,noreferrer');
        n.close();
        return;
      }
      try {
        window.focus();                     // la ventana, al frente
        const destino = o.destino || (
          o.uid
            ? `/webmail/?folder=${encodeURIComponent(o.carpeta || 'INBOX')}&uid=${o.uid}`
            : '/webmail/?folder=INBOX'
        );
        // si ya estamos en el webmail, se navega sin recargar; si no, se abre
        if (location.pathname.startsWith('/webmail')) {
          window.history.pushState({}, '', destino);
          window.dispatchEvent(new PopStateEvent('popstate'));
          window.dispatchEvent(new CustomEvent('refresh-messages'));
        } else {
          window.location.href = destino;
        }
      } catch {
        window.location.href = '/webmail/?folder=INBOX';
      }
      n.close();
    };
    return true;
  } catch {
    return false;
  }
}
