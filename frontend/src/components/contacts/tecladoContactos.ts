import type React from 'react';

/* Ayudas de teclado para la sección Contactos. Equipo de Tecnología Maquita. */

/* Enter o Espacio activan un elemento con role="button". */
export function teclaActiva(accion: () => void) {
  return (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault(); e.stopPropagation(); accion();
    }
  };
}

/* Los atajos globales del correo capturan Enter en el documento y cancelan la pulsación,
   así que Enter no activaba los botones de Contactos. Si Enter cae en un botón o enlace,
   no se deja subir hasta esos atajos y el navegador lo activa con normalidad. */
export function protegerEnter(e: React.KeyboardEvent) {
  if (e.key !== 'Enter') return;
  const t = e.target as HTMLElement;
  if (t.closest('button, a[href], [role="button"], [role="menuitem"], [role="tab"]')) e.stopPropagation();
}
