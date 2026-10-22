// DNS dinámico de la zona: una ficha por nombre (casa.tu-dominio) con su usuario y su contraseña propios, para el
// router o el programa que mantiene al día la IP (protocolo dyndns2, el de ddclient, inadyn y casi todos los routers).
import { api } from '../api.js';
import { el, agregar, campo } from '../ui.js';
import { confirmar, hacer, mensajes, unaVez } from './sitio_comun.js';

function mostrarDatos(r, dominio) {
  const f = r.creada, nombre = `${f.nombre}.${dominio}`, url = `https://${location.hostname}${r.ruta || '/nic/update'}`;
  unaVez(`DNS dinámico de ${nombre}`, [
    { etiqueta: 'Servidor (proveedor «dyndns2» o «personalizado»)', valor: location.hostname },
    { etiqueta: 'Nombre', valor: nombre },
    { etiqueta: 'Usuario', valor: f.usuario },
    { etiqueta: 'Contraseña', valor: r.clave, secreto: true },
    { etiqueta: 'Dirección para actualizar a mano', valor: `${url}?hostname=${nombre}&myip=<la IP>` },
  ], 'Sin «myip», se pone la IP desde la que llega la petición. Hasta 10 actualizaciones cada 10 minutos. La contraseña no se vuelve a mostrar.');
}

export async function seccionDdns(dominio) {
  const ruta = `/sitios/dns/${encodeURIComponent(dominio)}/dinamico`;
  const raiz = el('section', { clase: 'caja', 'aria-label': 'DNS dinámico' });
  const msj = mensajes();
  let r;
  try { r = await api.get(ruta); } catch (e) { return agregar(raiz, el('h2', null, 'DNS dinámico'), el('p', { clase: 'aviso error' }, e.message)); }
  const recargar = async () => raiz.replaceWith(await seccionDdns(dominio));
  const filas = (r.fichas || []).map(f => {
    const clave = el('button', { clase: 'enlace', type: 'button' }, 'Contraseña nueva');
    clave.addEventListener('click', async () => {
      if (!await confirmar('Contraseña nueva', `La de ${f.nombre}.${dominio} deja de valer: habrá que cambiarla en el router.`, 'Generar')) return;
      const d = await hacer(msj, clave, 'Generando…', () => api.post(`${ruta}/${f.id}/clave`));
      if (d) mostrarDatos(d, dominio);
    });
    const quitar = el('button', { clase: 'enlace peligro', type: 'button' }, 'Quitar');
    quitar.addEventListener('click', async () => {
      if (!await confirmar('Quitar el DNS dinámico', `¿Quitar la ficha de ${f.nombre}.${dominio}? Su registro se queda en la zona (puedes borrarlo arriba).`, 'Quitar', true)) return;
      if (await hacer(msj, quitar, 'Quitando…', () => api.del(`${ruta}/${f.id}`))) recargar();
    });
    return el('tr', null, el('td', null, el('strong', null, `${f.nombre}.${dominio}`)), el('td', null, el('code', null, f.usuario)),
      el('td', null, [f.ip4, f.ip6].filter(Boolean).join(' · ') || 'sin actualizar'), el('td', null, f.actualizado || '—'),
      el('td', { clase: 'acciones' }, clave, quitar));
  });
  const nombre = campo('Nombre dentro de ' + dominio, { type: 'text', maxlength: 120, placeholder: 'p. ej. casa u oficina', autocomplete: 'off' });
  const crear = el('button', { clase: 'boton', type: 'submit' }, 'Crear ficha');
  return agregar(raiz,
    el('h2', null, 'DNS dinámico'),
    el('p', { clase: 'ayuda' }, 'Para un equipo con IP que cambia (oficina, cámara, servidor en casa): su router actualiza el registro A o AAAA del nombre. Cada ficha tiene su propio usuario y contraseña, que solo valen para ese nombre.'),
    el('form', { clase: 'fila', alSubmit: async (e) => {
      e.preventDefault();
      const d = await hacer(msj, crear, 'Creando…', () => api.post(ruta, { nombre: nombre.entrada.value.trim() }));
      if (d) { mostrarDatos(d, dominio); recargar(); }
    } }, el('div', { clase: 'crece' }, nombre.nodo), crear),
    msj.nodo,
    filas.length ? el('div', { clase: 'tabla-marco' }, el('table', null,
      el('thead', null, el('tr', null, ['Nombre', 'Usuario', 'IP', 'Última actualización', ''].map(t => el('th', null, t)))),
      el('tbody', null, filas))) : el('p', { clase: 'ayuda' }, 'Sin fichas de DNS dinámico.'));
}
