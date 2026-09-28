import { api, ficha } from '../api.js';
import { el, aviso, campo } from '../ui.js';

export function vistaEntrar(alEntrar) {
  const usuario = campo('Usuario', { type: 'text', autocomplete: 'username', required: true, maxlength: 255 });
  const clave = campo('Contraseña', { type: 'password', autocomplete: 'current-password', required: true, maxlength: 128 });
  const codigo = campo('Código de 6 dígitos', { type: 'text', inputmode: 'numeric', autocomplete: 'one-time-code', maxlength: 7, pattern: '[0-9 ]{6,7}' },
    'El que muestra ahora la aplicación de tu teléfono.');
  codigo.nodo.hidden = true;
  const error = el('div');
  const boton = el('button', { clase: 'boton', type: 'submit' }, 'Entrar');
  return el('div', { clase: 'entrada' },
    el('form', { clase: 'caja', alSubmit: async (e) => {
      e.preventDefault();
      boton.disabled = true;
      error.replaceChildren();
      try {
        const r = await api.post('/acceso/entrar', { username: usuario.entrada.value, password: clave.entrada.value, codigo: codigo.entrada.value });
        if (r.requiere_codigo) {
          codigo.nodo.hidden = false;
          codigo.entrada.required = true;
          codigo.entrada.focus();
          boton.disabled = false;
          return;
        }
        ficha.guardar(r.token);
        alEntrar();
      } catch (err) {
        error.replaceChildren(aviso('error', err.message));
        codigo.entrada.value = '';
        boton.disabled = false;
      }
    } },
      el('h1', null, 'Administración de mi dominio'),
      el('p', { clase: 'sub' }, 'Cuentas, grupos y marca del correo de tu organización.'),
      error, usuario.nodo, clave.nodo, codigo.nodo,
      el('div', { clase: 'pie-form' }, boton)));
}
