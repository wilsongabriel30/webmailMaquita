// «FTP» → Cuentas adicionales: otra persona (un diseñador, un proveedor) entra por FTPS o SFTP solo a una
// subcarpeta de la carpeta pública. La contraseña la genera el servidor y se muestra una sola vez.
import { api } from '../api.js';
import { el, aviso, campo } from '../ui.js';
import { confirmar, enRutaSitio, hacer, mensajes, unaVez } from './sitio_comun.js';
import { boton, poner } from './sitio_piezas.js';

export function seccionCuentasFtp(ctx) {
  const ruta = `/sitios/${enRutaSitio(ctx.sitio)}/ftp/cuentas`;
  const caja = el('div', null, el('h2', null, 'Cuentas adicionales'), el('p', { clase: 'cargando' }, 'Cargando…'));
  const msj = mensajes();
  const mostrar = (r, carpeta) => {
    if (!r || !r.clave) return;
    unaVez('Cuenta FTP adicional', [
      { etiqueta: 'Servidor', valor: location.hostname }, { etiqueta: 'Usuario', valor: r.usuario },
      { etiqueta: 'Contraseña', valor: r.clave, secreto: true }, { etiqueta: 'Carpeta al entrar', valor: r.carpeta_web || 'archivos' },
    ], `Entra solo a publico/${carpeta}, por FTPS (puerto 21) o SFTP (puerto 22). La contraseña no se vuelve a mostrar: si se pierde, genera otra.`);
  };
  const pintar = (datos) => {
    const cuentas = datos.cuentas || [];
    const nombre = campo('Nombre de la cuenta', { type: 'text', maxlength: 11, pattern: '[a-z][a-z0-9]{1,10}', required: true, autocomplete: 'off' },
      'De 2 a 11 minúsculas o números, empezando por una letra.');
    const carpeta = campo('Subcarpeta de la carpeta pública', { type: 'text', maxlength: 200, required: true, placeholder: 'imagenes' }, 'Tiene que existir ya.');
    const crear = boton('Crear la cuenta', 'boton', null, 'submit');
    poner(caja, el('h2', null, `Cuentas adicionales (${cuentas.length} de ${datos.maximo || 10})`),
      el('p', { clase: 'ayuda' }, 'Cada cuenta queda encerrada en su subcarpeta: no ve el resto del sitio. Lo que sube es del sitio, como si lo subieras tú.'),
      cuentas.length ? el('ul', { clase: 'miembros' }, cuentas.map(c => el('li', null,
        el('div', null, el('code', null, c.usuario), ' ', el('span', { clase: 'ayuda' }, `publico/${c.carpeta}`),
          c.montada === false ? el('span', { clase: 'marca no' }, 'sin montar') : null),
        el('span', null,
          boton('Nueva clave', 'enlace', async (b) => mostrar(await hacer(msj, b, 'Generando la clave…', () => api.post(`${ruta}/${encodeURIComponent(c.nombre)}/clave`)), c.carpeta)),
          boton('Quitar', 'enlace peligro', async (b) => {
            if (!await confirmar('Quitar la cuenta', `${c.usuario} dejará de poder entrar. Los archivos de la carpeta se quedan.`, 'Quitar', true)) return;
            const r = await hacer(msj, b, 'Quitando…', () => api.del(`${ruta}/${encodeURIComponent(c.nombre)}`));
            if (r) { pintar(r); msj.ok('Cuenta quitada.'); }
          }))))) : el('p', { clase: 'ayuda' }, 'Ninguna.'),
      el('form', { alSubmit: async (e) => {
        e.preventDefault();
        const sub = carpeta.entrada.value.trim().replace(/^\/+|\/+$/g, '');
        const r = await hacer(msj, crear, 'Creando la cuenta…', () => api.post(ruta, { nombre: nombre.entrada.value.trim(), carpeta: sub }));
        if (r) { pintar(r); mostrar(r, sub); }
      } }, el('div', { clase: 'rejilla' }, nombre.nodo, carpeta.nodo), el('div', { clase: 'pie-form' }, crear)),
      msj.nodo);
  };
  api.get(ruta).then(pintar).catch((e) => poner(caja, el('h2', null, 'Cuentas adicionales'), aviso('error', e.message)));
  return caja;
}
