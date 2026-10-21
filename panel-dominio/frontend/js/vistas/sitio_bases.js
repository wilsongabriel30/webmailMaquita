// Pestaña «Bases de datos»: la base de la aplicación, bases adicionales y entrada a phpMyAdmin o
// Adminer ya conectados (usuario temporal), sin escribir contraseñas.
import { api } from '../api.js';
import { el } from '../ui.js';
import { abrirFuera, confirmar, enRutaSitio, hacer, mensajes, unaVez } from './sitio_comun.js';

const MOTOR = { mariadb: 'MariaDB', postgresql: 'PostgreSQL' };

export async function pestanaBases(ctx) {
  const ruta = `/sitios/${enRutaSitio(ctx.sitio)}/bases`;
  const datos = await api.get(ruta);
  const msj = mensajes();
  const boton = (texto, clase, fn) => { const b = el('button', { clase, type: 'button' }, texto); b.addEventListener('click', () => fn(b)); return b; };
  const entrar = (base, herramienta) => boton(herramienta === 'phpmyadmin' ? 'phpMyAdmin' : 'Adminer', 'enlace', async (b) => {
    const r = await hacer(msj, b, 'Abriendo la herramienta…', () => abrirFuera(() => api.post(`${ruta}/${encodeURIComponent(base)}/entrar`, { herramienta })));
    if (r) msj.ok(`Entrada abierta en otra pestaña con un usuario temporal${r.vence ? ' que vence a las ' + r.vence : ''}.`);
  });
  const herramientas = (base, motor) => el('span', null, motor === 'mariadb' ? entrar(base, 'phpmyadmin') : null, entrar(base, 'adminer'));
  const crear = (motor) => boton('Nueva base ' + MOTOR[motor], motor === 'mariadb' ? 'boton' : 'boton claro', async (b) => {
    const r = await hacer(msj, b, 'Creando la base…', () => api.post(ruta, { motor }));
    if (!r) return;
    unaVez(`Base ${MOTOR[r.motor] || ''} creada`, [
      { etiqueta: 'Servidor', valor: `${r.servidor}${r.puerto ? ':' + r.puerto : ''}` },
      { etiqueta: 'Base y usuario', valor: r.base }, { etiqueta: 'Contraseña', valor: r.clave, secreto: true },
    ], 'Solo se puede usar desde este servidor; cada usuario entra únicamente a su base. La contraseña no se vuelve a mostrar.');
    ctx.recargar();
  });
  return el('div', null,
    el('h2', null, 'Bases de datos'),
    datos.principal ? el('ul', { clase: 'miembros' }, el('li', null,
      el('div', null, el('strong', null, 'Base de la aplicación'), el('div', null, el('code', null, datos.principal))),
      herramientas(datos.principal, 'mariadb'))) : null,
    el('h2', null, 'Bases adicionales'),
    el('p', { clase: 'ayuda' }, 'Para aplicaciones propias. Cuentan para la cuota de bases de datos del dominio.'),
    (datos.bases || []).length ? el('ul', { clase: 'miembros' }, datos.bases.map(b => el('li', null,
      el('div', null, el('code', null, b.nombre), ' ', el('span', { clase: 'ayuda' }, MOTOR[b.motor] || b.motor)),
      el('span', null, herramientas(b.nombre, b.motor), boton('Borrar', 'enlace peligro', async (x) => {
        if (!await confirmar('Borrar la base', `Se borrará ${b.nombre}. Antes se guarda una copia (.sql) en la carpeta privada del sitio.`, 'Borrar', true)) return;
        const r = await hacer(msj, x, 'Borrando (primero se copia)…', () => api.del(`${ruta}/${encodeURIComponent(b.nombre)}`));
        if (r) { x.closest('li').remove(); msj.ok('Base borrada.' + (r.copia ? ' Copia guardada en ' + r.copia + '.' : '')); }
      }))))) : el('p', { clase: 'ayuda' }, 'Ninguna.'),
    el('div', { clase: 'fila espacio' }, crear('mariadb'), crear('postgresql')),
    msj.nodo,
    el('p', { clase: 'ayuda' }, 'Las herramientas se abren ya conectadas a esa base con un usuario temporal que vence en dos horas.'));
}
