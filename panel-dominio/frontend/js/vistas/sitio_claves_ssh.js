// «FTP» → Claves SSH (v1.11): entrar por SFTP con clave en vez de contraseña, en la cuenta principal o en una
// adicional. Cada cuenta sigue encerrada en su carpeta. Solo claves públicas ed25519, ECDSA o RSA de 3072 bits o más.
import { api } from '../api.js';
import { el, aviso, lista } from '../ui.js';
import { confirmar, enRutaSitio, hacer, mensajes } from './sitio_comun.js';
import { boton, poner } from './sitio_piezas.js';

const nombreCuenta = (c) => (c.cuenta === 'principal' ? 'Cuenta principal' : c.cuenta) + (c.usuario ? ` (${c.usuario})` : '');

export function seccionClavesSsh(ctx) {
  const ruta = `/sitios/${enRutaSitio(ctx.sitio)}/ssh/claves`;
  const caja = el('div', null, el('h2', null, 'Claves SSH'), el('p', { clase: 'cargando' }, 'Cargando…'));
  const msj = mensajes();
  const pintar = (datos) => {
    const claves = datos.claves || [];
    const cuentas = datos.cuentas || [];
    const cuenta = lista('Cuenta', cuentas.map(c => ({ valor: c.cuenta, texto: nombreCuenta(c) + (c.activa ? '' : ' — acceso apagado') })));
    const texto = el('textarea', { rows: '3', maxlength: '5000', spellcheck: 'false', required: true, 'aria-label': 'Clave pública',
      placeholder: 'ssh-ed25519 AAAA… nombre@equipo' });
    const anadir = boton('Añadir la clave', 'boton', null, 'submit');
    poner(caja, el('h2', null, 'Claves SSH'),
      el('p', { clase: 'ayuda' }, 'Para entrar por SFTP (puerto 22) con una clave en vez de la contraseña. Pega la clave PÚBLICA (el contenido del archivo .pub): ',
        'ed25519 (recomendada), ECDSA o RSA de 3072 bits o más. La de la cuenta principal solo vale mientras el acceso FTP/SFTP está activado.'),
      claves.length ? el('ul', { clase: 'miembros' }, claves.map(c => el('li', null,
        el('div', null, el('strong', null, nombreCuenta(c)), ' ',
          el('span', { clase: 'ayuda' }, [c.tipo, c.bits ? c.bits + ' bits' : null, c.comentario, c.creada].filter(Boolean).join(' · ')),
          el('div', null, el('code', null, c.huella)),
          c.activa ? null : el('span', { clase: 'marca no' }, 'sin efecto: acceso apagado')),
        boton('Borrar', 'enlace peligro', async (b) => {
          if (!await confirmar('Borrar la clave', `La clave ${c.huella} dejará de servir para entrar.`, 'Borrar', true)) return;
          const r = await hacer(msj, b, 'Borrando…', () => api.del(`${ruta}/${encodeURIComponent(c.id)}`));
          if (r) { pintar(r); msj.ok('Clave borrada.'); }
        })))) : el('p', { clase: 'ayuda' }, 'Ninguna.'),
      el('form', { alSubmit: async (e) => {
        e.preventDefault();
        const clave = texto.value.trim();
        if (!clave || /[\r\n]/.test(clave)) { msj.error('Pega una sola clave pública, en una línea.'); return; }
        const r = await hacer(msj, anadir, 'Comprobando la clave…', () => api.post(ruta, { cuenta: cuenta.entrada.value, clave }));
        if (r) { pintar(r); msj.ok(r.agregada ? `Clave añadida: ${r.agregada.huella}.` : 'Clave añadida.'); }
      } }, cuenta.nodo, texto, el('div', { clase: 'pie-form' }, anadir)),
      msj.nodo);
  };
  api.get(ruta).then(pintar).catch((e) => poner(caja, el('h2', null, 'Claves SSH'), aviso('error', e.message)));
  return caja;
}
