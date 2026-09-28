import { api, ficha } from '../api.js';
import { el, aviso, campo } from '../ui.js';

export function vistaEntrar(alEntrar) {
  const usuario = campo('Usuario', { type: 'text', autocomplete: 'username', required: true, maxlength: 255 });
  const clave = campo('Contraseña', { type: 'password', autocomplete: 'current-password', required: true, maxlength: 128 });
  const error = el('div');
  const boton = el('button', { clase: 'boton', type: 'submit' }, 'Entrar');
  return el('div', { clase: 'entrada' },
    el('form', { clase: 'caja', alSubmit: async (e) => {
      e.preventDefault();
      boton.disabled = true;
      error.replaceChildren();
      try {
        const r = await api.post('/acceso/entrar', { username: usuario.entrada.value, password: clave.entrada.value });
        ficha.guardar(r.token);
        alEntrar(r.debe_cambiar_clave);
      } catch (err) {
        error.replaceChildren(aviso('error', err.message));
        boton.disabled = false;
      }
    } },
      el('h1', null, 'Administración de mi dominio'),
      el('p', { clase: 'sub' }, 'Cuentas de correo y alias de tu organización.'),
      error, usuario.nodo, clave.nodo,
      el('div', { clase: 'pie-form' }, boton)));
}
