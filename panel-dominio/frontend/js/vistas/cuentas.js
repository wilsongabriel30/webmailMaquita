import { api } from '../api.js';
import { el, aviso, enGB } from '../ui.js';
import { formularioNueva, formularioEditar, formularioClave, confirmarActiva } from './formularios_cuenta.js';

export async function vistaCuentas(sesion, mensaje) {
  const cuentas = await api.get('/cuentas');
  const cuerpo = el('tbody');
  const contador = el('span', { clase: 'ayuda' });
  const raiz = el('div');
  const recargar = async (texto) => raiz.replaceWith(await vistaCuentas(sesion, texto));

  const pintar = (filtro) => {
    const f = filtro.trim().toLowerCase();
    const visibles = cuentas.filter(c => !f || c.username.includes(f) || (c.name || '').toLowerCase().includes(f));
    contador.textContent = `${visibles.length} de ${cuentas.length}`;
    cuerpo.replaceChildren(...(visibles.length ? visibles.map(c => el('tr', null,
      el('td', null, el('strong', null, c.username), el('div', { clase: 'ayuda' }, c.name || '')),
      el('td', null, enGB(c.quota)),
      el('td', null, el('span', { clase: 'marca ' + (c.active ? 'si' : 'no') }, c.active ? 'Activa' : 'Desactivada')),
      el('td', { clase: 'acciones' },
        el('button', { clase: 'enlace', alClick: () => formularioEditar(c, recargar) }, 'Editar'),
        el('button', { clase: 'enlace', alClick: () => formularioClave(c, recargar) }, 'Contraseña'),
        el('button', { clase: 'enlace' + (c.active ? ' peligro' : ''), alClick: () => confirmarActiva(c, recargar) }, c.active ? 'Desactivar' : 'Activar'))))
      : [el('tr', null, el('td', { colspan: '4', clase: 'vacio' }, 'No hay cuentas que coincidan.'))]));
  };

  const buscar = el('input', { type: 'search', placeholder: 'Buscar por dirección o nombre', 'aria-label': 'Buscar cuentas', alInput: (e) => pintar(e.target.value) });
  raiz.append(
    el('h1', null, 'Cuentas de correo'),
    el('p', { clase: 'sub' }, sesion.dominios.join(', ')),
    mensaje ? aviso('ok', mensaje) : null,
    el('div', { clase: 'fila' }, el('div', { clase: 'crece' }, buscar), contador,
      el('button', { clase: 'boton', alClick: () => formularioNueva(sesion.dominios, recargar) }, 'Nueva cuenta')),
    el('div', { clase: 'caja tabla-marco' }, el('table', null,
      el('thead', null, el('tr', null, el('th', null, 'Cuenta'), el('th', null, 'Cuota'), el('th', null, 'Estado'), el('th', null, ''))),
      cuerpo)));
  pintar('');
  return raiz;
}
