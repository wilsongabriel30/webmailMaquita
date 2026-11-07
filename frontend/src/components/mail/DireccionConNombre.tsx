/**
 * Una dirección de De/Para/CC mostrada por el NOMBRE de la persona (06/11/2026).
 *
 * Preferencia: nombre en los contactos propios → directorio de la organización → nombre que
 * trae el correo → la dirección (lib/nombresCorreo.ts). La dirección queda a la vista al
 * pasar el ratón; en «Más detalles» (`completo`) se muestra «Nombre <correo>».
 */
import React from 'react';
import { partirDireccion, useNombreCorreo } from '../../lib/nombresCorreo';

export const DireccionConNombre: React.FC<{ texto: string; completo?: boolean }> = ({ texto, completo }) => {
  const { nombre, correo } = partirDireccion(texto || '');
  const conocido = useNombreCorreo(correo);
  const mostrado = conocido || nombre;
  if (!mostrado) return <span>{correo || texto}</span>;
  if (completo) return <span>{mostrado} &lt;{correo}&gt;</span>;
  return <span title={correo}>{mostrado}</span>;
};
