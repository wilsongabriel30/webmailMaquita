import { api, enRuta } from '../api.js';
import { el, campo, ventana, generarClave, GIB } from '../ui.js';

function campoClave(etiqueta) {
  const c = campo(etiqueta, { type: 'text', autocomplete: 'off', required: true, minlength: 10, maxlength: 128, spellcheck: 'false' },
    'Mínimo 10 caracteres, combinando mayúsculas, minúsculas, números o símbolos. Entrégala a la persona por un medio seguro.');
  c.nodo.append(el('button', { clase: 'enlace', type: 'button', alClick: () => { c.entrada.value = generarClave(); } }, 'Generar una contraseña'));
  return c;
}

export function formularioNueva(dominios, alTerminar) {
  const local = campo('Nombre de la cuenta', { type: 'text', required: true, maxlength: 64, pattern: '[A-Za-z0-9][A-Za-z0-9._\\-]*', autocomplete: 'off' }, 'La parte antes de la arroba. Ejemplo: ana.perez');
  const dominio = el('select', null, dominios.map(d => el('option', { value: d }, '@' + d)));
  const nombre = campo('Nombre de la persona', { type: 'text', required: true, maxlength: 255 });
  const clave = campoClave('Contraseña inicial');
  ventana('Nueva cuenta', el('div', null, local.nodo, el('label', null, 'Dominio'), dominio, nombre.nodo, clave.nodo), 'Crear cuenta', async () => {
    await api.post('/cuentas', { username: `${local.entrada.value.trim()}@${dominio.value}`, name: nombre.entrada.value, password: clave.entrada.value });
    alTerminar(`Cuenta ${local.entrada.value.trim()}@${dominio.value} creada.`);
  });
}

export function formularioEditar(cuenta, alTerminar) {
  const nombre = campo('Nombre de la persona', { type: 'text', maxlength: 255, valor: cuenta.name || '' });
  const telefono = campo('Teléfono', { type: 'text', maxlength: 50, valor: cuenta.phone || '' });
  const otro = campo('Correo alterno', { type: 'email', maxlength: 255, valor: cuenta.email_other || '' });
  const cuota = campo('Cuota (GB)', { type: 'number', min: '0.1', step: '0.1', valor: cuenta.quota > 0 ? (cuenta.quota / GIB).toFixed(1).replace(/\.0$/, '') : '' },
    'Se puede bajar libremente; subirla está limitado al máximo del dominio.');
  ventana('Editar ' + cuenta.username, el('div', null, nombre.nodo, telefono.nodo, otro.nodo, cuota.nodo), 'Guardar', async () => {
    const cambios = { name: nombre.entrada.value, phone: telefono.entrada.value, email_other: otro.entrada.value };
    const gb = parseFloat(cuota.entrada.value);
    if (gb > 0 && Math.round(gb * GIB) !== cuenta.quota) cambios.quota = Math.round(gb * GIB);
    await api.put('/cuentas/' + enRuta(cuenta.username), cambios);
    alTerminar('Cambios guardados.');
  });
}

export function formularioClave(cuenta, alTerminar) {
  const clave = campoClave('Contraseña nueva');
  ventana('Cambiar contraseña de ' + cuenta.username, clave.nodo, 'Cambiar contraseña', async () => {
    await api.post(`/cuentas/${enRuta(cuenta.username)}/clave`, { password: clave.entrada.value });
    alTerminar('Contraseña cambiada. La anterior dejó de funcionar.');
  });
}

export function confirmarActiva(cuenta, alTerminar) {
  const activar = !cuenta.active;
  ventana((activar ? 'Activar ' : 'Desactivar ') + cuenta.username,
    el('p', null, activar ? 'La cuenta volverá a recibir y enviar correo.' : 'La persona no podrá entrar ni recibir correo hasta que la actives de nuevo. No se borra nada.'),
    activar ? 'Activar' : 'Desactivar', async () => {
      await api.post(`/cuentas/${enRuta(cuenta.username)}/activa`, { active: activar });
      alTerminar(activar ? 'Cuenta activada.' : 'Cuenta desactivada.');
    }, !activar);
}
