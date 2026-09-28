import { api, ficha } from '../api.js';
import { el, aviso, campo } from '../ui.js';

export function vistaMiClave(obligatorio) {
  // Tras el cambio se cierran todas las sesiones y hay que volver a entrar.
  const actual = campo('Contraseña actual', { type: 'password', autocomplete: 'current-password', required: true, maxlength: 128 });
  const nueva = campo('Contraseña nueva', { type: 'password', autocomplete: 'new-password', required: true, minlength: 10, maxlength: 128 }, 'Mínimo 10 caracteres, combinando mayúsculas, minúsculas, números o símbolos.');
  const repetir = campo('Repite la contraseña nueva', { type: 'password', autocomplete: 'new-password', required: true, maxlength: 128 });
  const estado = el('div');
  const boton = el('button', { clase: 'boton', type: 'submit' }, 'Cambiar mi contraseña');
  return el('form', { clase: 'caja', alSubmit: async (e) => {
    e.preventDefault();
    estado.replaceChildren();
    if (nueva.entrada.value !== repetir.entrada.value) { estado.replaceChildren(aviso('error', 'Las contraseñas nuevas no coinciden.')); return; }
    boton.disabled = true;
    try {
      await api.post('/acceso/clave', { actual: actual.entrada.value, nueva: nueva.entrada.value });
      ficha.borrar();
      estado.replaceChildren(aviso('ok', 'Contraseña cambiada. Vuelve a entrar con la nueva.'));
      setTimeout(() => window.dispatchEvent(new Event('pd-sin-sesion')), 1500);
    } catch (err) { estado.replaceChildren(aviso('error', err.message)); boton.disabled = false; }
  } },
    el('h1', null, 'Mi contraseña'),
    obligatorio ? aviso('nota', 'Es tu primera entrada: cambia la contraseña que te entregaron antes de continuar.') : null,
    estado, actual.nodo, nueva.nodo, repetir.nodo, el('div', { clase: 'pie-form' }, boton));
}
