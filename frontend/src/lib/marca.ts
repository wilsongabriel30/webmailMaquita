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
const oyentes = new Set<(n: string) => void>();

/** El nombre que se conozca ahora mismo. Sirve fuera de React (título del documento, avisos). */
export function nombreApp(): string {
  return nombre;
}

/** El nombre de la organización (`org_name`), para textos como el pie de una firma. */
export function nombreOrg(): string {
  return organizacion;
}

/** Pide la marca al servidor una sola vez, aunque la llamen varios componentes a la vez. */
export function cargarMarca(): Promise<string> {
  if (!peticion) {
    peticion = fetch('/api/branding')
      .then((r) => (r.ok ? r.json() : {}))
      .then((b: { app_name?: string; org_name?: string }) => {
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
