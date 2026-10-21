// Pestaña «Pedir la baja»: la baja de un sitio se pide aquí y la confirma el administrador general.
import { api } from '../api.js';
import { el, aviso } from '../ui.js';
import { confirmar, enRutaSitio, hacer, mensajes } from './sitio_comun.js';

export function pestanaBaja(ctx) {
  const { sitio, estado } = ctx;
  if (estado.baja_pendiente) {
    return aviso('nota', 'Ya pediste la baja de este sitio. Sigue publicado hasta que el administrador general la confirme.');
  }
  const msj = mensajes();
  const motivo = el('textarea', { id: 'baja-motivo', maxlength: '500', rows: '3' });
  const boton = el('button', { clase: 'boton peligro', type: 'submit' }, 'Pedir la baja');
  return el('form', { alSubmit: async (e) => {
    e.preventDefault();
    if (!await confirmar('Pedir la baja', `¿Pedir la baja de ${sitio}? Cuando el administrador general la confirme, el sitio deja de publicarse y se retiran su usuario, su FTP y sus bases de datos.`, 'Pedir la baja', true)) return;
    if (await hacer(msj, boton, 'Enviando la solicitud…', () => api.post(`/sitios/${enRutaSitio(sitio)}/baja`, { motivo: motivo.value.trim() }))) ctx.recargar();
  } },
    el('h2', null, 'Pedir la baja del sitio'),
    el('p', null, 'Dar de baja un sitio no tiene vuelta atrás para quien lo visita, así que no se hace al momento: lo confirma el administrador general. Mientras tanto el sitio sigue funcionando y no se borra nada.'),
    el('p', { clase: 'ayuda' }, 'Los archivos y una copia de la base de datos se guardan un tiempo en la papelera del servidor.'),
    el('label', { for: motivo.id }, 'Motivo (opcional)'), motivo,
    msj.nodo, el('div', { clase: 'pie-form' }, boton));
}
