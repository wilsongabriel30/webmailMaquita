/**
 * «+» junto al remitente o destinatario de un correo: lo agrega a Contactos (12/11/2026).
 *
 * Antes vivía dentro de MessageView y, si la dirección ya estaba en Contactos, solo mostraba un visto:
 * no decía con qué nombre estaba guardada ni dejaba corregirlo. Muchos contactos nacen solos del
 * historial de enviados, sin nombre o con el de quien usaba antes esa dirección. Ahora:
 *   - si no existía, lo crea;
 *   - si existía sin nombre, le pone el del correo;
 *   - si existía con OTRO nombre, pregunta antes de cambiarlo;
 * y siempre dice en una frase qué hizo.
 */
import React from 'react';
import { api } from '../../api/client';

interface Respuesta { status: 'created' | 'updated' | 'different' | 'exists'; id: number; nombre?: string; nombre_guardado?: string; nombre_anterior?: string; }
type Estado = { fase: 'libre' | 'guardando' } | { fase: 'hecho'; texto: string; detalle: string };

export const BotonAgregarContacto: React.FC<{ name: string; email: string }> = ({ name, email }) => {
  const [estado, setEstado] = React.useState<Estado>({ fase: 'libre' });

  const agregar = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (estado.fase !== 'libre') return;
    setEstado({ fase: 'guardando' });
    try {
      let r = await api.post<Respuesta>('/contacts/from-email', { name, email });
      if (r.status === 'different') {
        const cambiar = window.confirm(
          `${email} ya está en sus contactos como «${r.nombre_guardado}».\n\n¿Cambiar el nombre a «${r.nombre}»?\n\nAceptar: se cambia. Cancelar: se deja como está.`,
        );
        if (!cambiar) {
          setEstado({ fase: 'hecho', texto: `Ya está como «${r.nombre_guardado}»`, detalle: 'No se cambió el nombre. Puede editarlo en Contactos buscando por el correo.' });
          return;
        }
        r = await api.post<Respuesta>('/contacts/from-email', { name, email, actualizar: true });
      }
      if (r.status === 'created') setEstado({ fase: 'hecho', texto: 'Agregado a contactos', detalle: `Guardado como «${r.nombre}».` });
      else if (r.status === 'updated') setEstado({ fase: 'hecho', texto: 'Nombre guardado', detalle: r.nombre_anterior && !r.nombre_anterior.includes('@') ? `Antes figuraba como «${r.nombre_anterior}»; ahora es «${r.nombre}».` : `Ya estaba en contactos sin nombre; ahora es «${r.nombre}».` });
      else setEstado({ fase: 'hecho', texto: 'Ya está en contactos', detalle: r.nombre ? `Guardado como «${r.nombre}».` : 'Ya estaba guardado.' });
    } catch {
      setEstado({ fase: 'libre' });
    }
  };

  if (estado.fase === 'hecho') {
    return <span role="status" title={estado.detalle} style={{ fontSize: 11, color: '#498205', marginLeft: 4, whiteSpace: 'nowrap' }}>✓ {estado.texto}</span>;
  }
  return (
    <button onClick={agregar} disabled={estado.fase === 'guardando'} title="Agregar a contactos" aria-label={`Agregar ${email} a contactos`}
      style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '0 4px', fontSize: 13, color: '#0078d4', fontWeight: 600, marginLeft: 2 }}>
      {estado.fase === 'guardando' ? '...' : '+'}
    </button>
  );
};
