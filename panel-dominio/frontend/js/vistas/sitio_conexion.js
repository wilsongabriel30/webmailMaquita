// Pestañas «HTTPS» (certificado gratuito de Let's Encrypt) y «FTP» (FTPS o SFTP, encerrado en el sitio).
import { api } from '../api.js';
import { el, campo } from '../ui.js';
import { confirmar, enRutaSitio, hacer, mensajes, unaVez } from './sitio_comun.js';

export function pestanaHttps(ctx) {
  const { s, sitio } = ctx;
  if (s.ssl) {
    return el('div', null, el('h2', null, 'HTTPS activo'),
      el('p', null, `El sitio se sirve cifrado en https://${sitio}${s.www ? ` y https://www.${sitio}` : ''}. El certificado se renueva solo.`));
  }
  const msj = mensajes();
  const correo = campo('Correo para los avisos del certificado', { type: 'email', required: true, autocomplete: 'email' },
    'Let\'s Encrypt escribe aquí solo si hay un problema con la renovación.');
  const boton = el('button', { clase: 'boton', type: 'submit' }, 'Pedir el certificado');
  return el('form', { alSubmit: async (e) => {
    e.preventDefault();
    const r = await hacer(msj, boton, 'Pidiendo el certificado (puede tardar un minuto)…',
      () => api.post(`/sitios/${enRutaSitio(sitio)}/https`, { correo: correo.entrada.value.trim() }));
    if (r) ctx.recargar();
  } },
    el('h2', null, 'Activar HTTPS'),
    el('p', null, `Antes: ${sitio}${s.www ? ` y www.${sitio}` : ''} deben apuntar en el DNS a la dirección de este servidor. Si no, el certificado no se puede emitir.`),
    correo.nodo, msj.nodo, el('div', { clase: 'pie-form' }, boton));
}

export function pestanaFtp(ctx) {
  const { s, sitio } = ctx;
  const msj = mensajes();
  const ftp = async (boton, accion) => {
    const r = await hacer(msj, boton, accion === 'activar' ? 'Generando la clave…' : 'Desactivando…',
      () => api.post(`/sitios/${enRutaSitio(sitio)}/ftp`, { accion }));
    if (!r) return;
    if (accion === 'activar' && r.clave) {
      unaVez('Acceso a los archivos del sitio', [
        { etiqueta: 'Servidor', valor: location.hostname },
        { etiqueta: 'Usuario', valor: r.usuario || s.usuario_ftp },
        { etiqueta: 'Contraseña', valor: r.clave, secreto: true },
        { etiqueta: 'Carpeta del sitio', valor: 'publico' },
      ], 'Usa FTP con cifrado (FTPS explícito, puerto 21) o SFTP (puerto 22); el FTP sin cifrar no se acepta. La contraseña no se vuelve a mostrar: si se pierde, genera otra.');
    }
    ctx.recargar();
  };
  const boton = (texto, accion, clase) => { const b = el('button', { clase, type: 'button' }, texto); b.addEventListener('click', () => ftp(b, accion)); return b; };
  return el('div', null,
    el('h2', null, s.ftp ? 'FTP activo' : 'FTP apagado'),
    el('p', null, 'Para subir y bajar los archivos del sitio con un programa como FileZilla. El acceso queda encerrado en la carpeta del sitio.'),
    s.ftp ? el('div', { clase: 'fila' }, boton('Nueva clave', 'activar', 'boton'), (() => {
      const b = el('button', { clase: 'boton peligro', type: 'button' }, 'Desactivar');
      b.addEventListener('click', async () => { if (await confirmar('Desactivar el FTP', 'Nadie podrá entrar a los archivos por FTP hasta que lo vuelvas a activar.', 'Desactivar', true)) ftp(b, 'desactivar'); });
      return b;
    })()) : el('div', { clase: 'fila' }, boton('Activar y generar la clave', 'activar', 'boton')),
    s.ftp && s.usuario_ftp ? el('p', { clase: 'ayuda' }, 'Usuario: ', el('code', null, s.usuario_ftp), '. «Nueva clave» invalida la anterior.') : null,
    msj.nodo);
}
