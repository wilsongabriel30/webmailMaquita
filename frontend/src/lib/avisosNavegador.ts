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

interface Opciones {
  cuerpo: string;
  tipo?: TipoAviso;
  etiqueta?: string;
  /** A dónde lleva el clic. Si no se dice, a la bandeja de entrada. */
  destino?: string;
  /** Correo concreto que abrir, si se sabe cuál es. */
  uid?: number;
  carpeta?: string;
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
  if (esRepetido((o.etiqueta || o.tipo || 'general') + '|' + titulo + '|' + o.cuerpo)) {
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
