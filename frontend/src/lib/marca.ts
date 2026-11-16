// El nombre del producto, tal y como lo configuró quien administra.
//
// El servidor lo sirve en /api/branding (`app_name`), pero la interfaz lo llevaba escrito a mano
// como el nombre de nuestra instalación en la cabecera y en el título accesible de la página. En otra instalación
// eso enseña nuestro nombre en la barra superior aunque hayan puesto el suyo: lo reportó el
// equipo de Andes al rodar la suya.
//
// Se pide una sola vez por sesión de navegador y se reparte a quien lo necesite. Si el servidor
// no responde o no tiene nada configurado, queda el valor de reserva: la cabecera nunca se ve
// vacía.

import { useEffect, useState } from 'react';

// Reserva NEUTRA: una instalación sin marca configurada no debe enseñar el nombre de otra.
const RESERVA = 'Correo';
const RESERVA_ORG = 'la organización';

let nombre = RESERVA;
let organizacion = RESERVA_ORG;
let peticion: Promise<string> | null = null;
// ¿Hay app móvil publicada? null = el servidor no lo dice (versión anterior): se pregunta como antes.
let appMovil: boolean | null = null;
// A quién escribir sobre el servicio: lo define cada organización (ver correoDeContacto).
let contacto = '';
const oyentes = new Set<(n: string) => void>();

/** El nombre que se conozca ahora mismo. Sirve fuera de React (título del documento, avisos). */
export function nombreApp(): string {
  return nombre;
}

/** El nombre de la organización (`org_name`), para textos como el pie de una firma. */
export function nombreOrg(): string {
  return organizacion;
}

/** La primera dirección válida de las candidatas, o '' si no hay ninguna. */
export function elegirContacto(...candidatas: (string | undefined | null)[]): string {
  for (const c of candidatas) {
    const v = (c || '').trim();
    if (/^[^\s@<>,;]+@[^\s@<>,;]+\.[^\s@<>,;]+$/.test(v)) return v;
  }
  return '';
}

/**
 * Dirección a la que van los «Comentarios» de la cinta Ayuda. No hay una fija en el programa: es la
 * de quien administra el dominio por el que se entra (`contacto_admin`: el correo de contacto de la
 * empresa o su administrador de dominio) y, si no hay, el correo de la organización (`org_email`,
 * panel de administración → Marca). Vacía si la instalación no tiene ninguna: el botón no se muestra.
 */
export function correoDeContacto(): string {
  return contacto;
}

/** Pide la marca al servidor una sola vez, aunque la llamen varios componentes a la vez. */
export function cargarMarca(): Promise<string> {
  if (!peticion) {
    peticion = fetch('/api/branding')
      .then((r) => (r.ok ? r.json() : {}))
      .then((b: { app_name?: string; org_name?: string; app_movil?: boolean; contacto_admin?: string; org_email?: string }) => {
        if (typeof b.app_movil === 'boolean') appMovil = b.app_movil;
        contacto = elegirContacto(b.contacto_admin, b.org_email);
        // «Tu organización» es el valor de relleno del servidor cuando no hay nada configurado.
        if (b.org_name && b.org_name !== 'Tu organización') organizacion = b.org_name;
        if (b.app_name) {
          nombre = b.app_name;
          oyentes.forEach((f) => f(nombre));
        }
        return nombre;
      })
      .catch(() => nombre);
  }
  return peticion;
}

/** Falso solo si el servidor dijo que no hay app móvil publicada (así no se pide su manifiesto en vano). */
export function hayAppMovil(): Promise<boolean> {
  return cargarMarca().then(() => appMovil !== false);
}

/** El nombre del producto para pintarlo. Se actualiza solo cuando llega la respuesta. */
export function useNombreApp(): string {
  const [valor, setValor] = useState(nombre);
  useEffect(() => {
    oyentes.add(setValor);
    cargarMarca().then(setValor);
    return () => { oyentes.delete(setValor); };
  }, []);
  return valor;
}

/** La dirección de contacto para pintarla (o esconder lo que dependa de ella). Llega con la marca. */
export function useCorreoContacto(): string {
  const [valor, setValor] = useState(contacto);
  useEffect(() => {
    let vivo = true;
    cargarMarca().then(() => { if (vivo) setValor(contacto); });
    return () => { vivo = false; };
  }, []);
  return valor;
}
