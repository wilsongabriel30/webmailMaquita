import { api } from '../api.js';
import { el, aviso, enGB } from '../ui.js';

export async function vistaResumen() {
  const r = await api.get('/resumen');
  if (!r.dominios.length) return aviso('nota', 'Tu cuenta aún no tiene dominios asignados. Pide al administrador general que te asigne uno.');
  return el('div', null,
    el('h1', null, 'Resumen'),
    el('p', { clase: 'sub' }, r.dominios.length === 1 ? 'Tu dominio' : 'Tus dominios'),
    el('div', { clase: 'tarjetas' }, r.dominios.map(d => el('div', { clase: 'caja' },
      el('strong', null, d.domain), ' ',
      el('span', { clase: 'marca ' + (d.active ? 'si' : 'no') }, d.active ? 'Activo' : 'Desactivado'),
      el('div', { clase: 'cifra' }, d.cuentas_activas, el('span', { clase: 'ayuda' }, ` de ${d.cuentas} cuentas activas`)),
      el('p', { clase: 'ayuda' }, `${d.alias} alias · límite de cuentas: ${d.max_cuentas > 0 ? d.max_cuentas : 'sin límite'}`),
      el('p', { clase: 'ayuda' }, `Cuota máxima por cuenta: ${enGB(d.cuota_maxima > 0 ? d.cuota_maxima : r.cuota_por_defecto)}`)))),
    el('p', { clase: 'aviso nota' }, 'Desde aquí puedes crear cuentas, cambiar contraseñas, activar o desactivar cuentas y gestionar alias. Para eliminar una cuenta o reenviar correo fuera de tu dominio, escribe al administrador general.'));
}
