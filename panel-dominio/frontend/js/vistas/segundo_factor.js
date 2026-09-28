import { api } from '../api.js';
import { el, aviso, campo } from '../ui.js';

/** Activación del segundo factor. `alTerminar` se llama cuando queda activo. */
export async function vistaSegundoFactor(obligatorio, alTerminar) {
  const estado = await api.get('/acceso/totp/estado');
  if (estado.activo) {
    return el('div', { clase: 'caja' }, el('h1', null, 'Segundo factor'),
      aviso('ok', 'Activo. Al entrar se te pide el código de tu teléfono.'),
      el('p', { clase: 'ayuda' }, 'Si cambias de teléfono o lo pierdes, pide al administrador general que lo restablezca.'));
  }
  const caja = el('div', { clase: 'caja' });
  const mensaje = el('div');
  const empezar = el('button', { clase: 'boton', alClick: async () => {
    empezar.disabled = true;
    mensaje.replaceChildren();
    try {
      const r = await api.post('/acceso/totp/iniciar');
      const codigo = campo('Código que muestra la aplicación', { type: 'text', inputmode: 'numeric', autocomplete: 'one-time-code', required: true, maxlength: 7, pattern: '[0-9 ]{6,7}' });
      const confirmar = el('button', { clase: 'boton', type: 'submit' }, 'Activar');
      caja.replaceChildren(
        el('h1', null, 'Segundo factor'),
        el('ol', { clase: 'pasos' },
          el('li', null, 'Abre en tu teléfono una aplicación de códigos (Google Authenticator, Microsoft Authenticator, Aegis…).'),
          el('li', null, 'Escanea este código. Si no puedes, escribe la clave a mano.'),
          el('li', null, 'Escribe aquí el código de 6 dígitos que aparece.')),
        el('img', { clase: 'qr', src: r.qr, alt: 'Código QR para dar de alta el segundo factor', width: '220', height: '220' }),
        el('p', { clase: 'ayuda' }, 'Clave para escribirla a mano: ', el('code', null, r.secreto.replace(/(.{4})/g, '$1 ').trim())),
        el('form', { alSubmit: async (e) => {
          e.preventDefault();
          confirmar.disabled = true;
          try { await api.post('/acceso/totp/activar', { codigo: codigo.entrada.value }); alTerminar(); }
          catch (err) { mensaje.replaceChildren(aviso('error', err.message)); confirmar.disabled = false; codigo.entrada.value = ''; }
        } }, mensaje, codigo.nodo, el('div', { clase: 'pie-form' }, confirmar)));
      codigo.entrada.focus();
    } catch (err) { mensaje.replaceChildren(aviso('error', err.message)); empezar.disabled = false; }
  } }, 'Configurar ahora');
  caja.append(
    el('h1', null, 'Segundo factor'),
    obligatorio ? aviso('nota', 'Para proteger las cuentas de tu organización, este portal exige un segundo factor: además de la contraseña, un código que cambia cada 30 segundos en tu teléfono.') : el('span'),
    mensaje, el('div', { clase: 'pie-form' }, empezar));
  return caja;
}
