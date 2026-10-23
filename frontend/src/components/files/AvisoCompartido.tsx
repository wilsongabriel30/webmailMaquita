import { useState } from 'react';
import { espacioDeRuta } from './rutasEspacio';
import { useNombreDrive } from './marcaDrive';

/* Aviso sutil al entrar en una carpeta COMPARTIDA: lo que se mueve, renombra o borra
   ahí lo ven también los demás, porque es una sola carpeta real (no una copia).

   En este Drive las carpetas que se trabajan entre varias personas son las unidades
   de equipo (/unidades/<id>/…): lo que otra persona comparte a tu correo llega como
   enlace a un archivo («Conmigo»), no como carpeta navegable. Por eso el aviso sale
   dentro de una unidad. Se oculta con la ✕ y queda oculto el resto de la sesión. */

const CLAVE_OCULTO = 'almacen_aviso_compartido_oculto';

function leerOculto(): boolean {
  try { return sessionStorage.getItem(CLAVE_OCULTO) === '1'; } catch { return false; }
}

export function AvisoCompartido({ ruta }: { ruta: string }) {
  const [oculto, setOculto] = useState(leerOculto);
  const nombreDrive = useNombreDrive();
  if (oculto || espacioDeRuta(ruta).tipo !== 'unidad') return null;

  const ocultar = () => {
    setOculto(true);
    try { sessionStorage.setItem(CLAVE_OCULTO, '1'); } catch { /* sin almacenamiento: solo esta vez */ }
  };
  const destino = nombreDrive ? `a tus archivos de ${nombreDrive}` : 'a tus archivos';

  return (
    <div role="note" aria-label="Aviso de carpeta compartida"
      className="flex items-start gap-2 mx-4 mb-2 px-3 py-2 rounded-lg border text-xs
        bg-[#fff4e5] border-[#fde0b2] text-[#8a5300] dark:bg-[#3a2a10] dark:border-[#6b4a12] dark:text-[#f5c26b]">
      <span aria-hidden="true" className="text-base leading-none">👥</span>
      <span className="flex-1">
        Estás en una <b>carpeta compartida</b>. Es una sola carpeta real: lo que <b>muevas, renombres o borres</b> aquí
        también lo verán los demás miembros de la unidad. Para llevarte algo {destino}, <b>cópialo</b> (así no se borra el original).
      </span>
      <button type="button" onClick={ocultar} aria-label="Ocultar el aviso" title="Ocultar el aviso"
        className="shrink-0 w-6 h-6 -my-0.5 rounded-full hover:bg-[#fde0b2] dark:hover:bg-[#6b4a12] focus:outline focus:outline-2 focus:outline-[#8a5300]">✕</button>
    </div>
  );
}
