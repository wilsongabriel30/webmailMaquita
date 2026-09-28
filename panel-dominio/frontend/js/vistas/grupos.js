import { api } from '../api.js';
import { el, agregar, aviso, campo, lista, casilla, ventana } from '../ui.js';

function nuevoGrupo(dominios, alTerminar) {
  const local = campo('Dirección del grupo', { type: 'text', required: true, maxlength: 64, pattern: '[A-Za-z0-9][A-Za-z0-9._\\-]*', autocomplete: 'off' }, 'Ejemplo: todos, ventas, directiva');
  const dominio = lista('Dominio', dominios.map(d => ({ valor: d, texto: '@' + d })));
  const nombre = campo('Nombre', { type: 'text', required: true, maxlength: 255 });
  const externos = casilla('Admitir miembros de fuera de la organización');
  ventana('Nuevo grupo', el('div', null, local.nodo, dominio.nodo, nombre.nodo, externos.nodo), 'Crear grupo', async () => {
    const direccion = `${local.entrada.value.trim()}@${dominio.entrada.value}`;
    await api.post('/grupos', { address: direccion, name: nombre.entrada.value, allow_external: externos.entrada.checked });
    alTerminar(`Grupo ${direccion} creado. Agrega ahora sus miembros.`);
  });
}

function editarGrupo(g, alTerminar) {
  const nombre = campo('Nombre', { type: 'text', maxlength: 255, valor: g.name || '' });
  const externos = casilla('Admitir miembros de fuera de la organización', g.allow_external);
  const activo = casilla('Grupo activo (si se desmarca, el correo que le escriban se rechaza)', g.active);
  ventana('Editar ' + g.address, el('div', null, nombre.nodo, externos.nodo, activo.nodo), 'Guardar', async () => {
    await api.put('/grupos/' + g.id, { name: nombre.entrada.value, allow_external: externos.entrada.checked, active: activo.entrada.checked });
    alTerminar('Grupo actualizado.');
  });
}

function agregarMiembro(g, alTerminar) {
  const correo = campo('Correo del miembro', { type: 'email', required: true, maxlength: 255, autocomplete: 'off' },
    g.allow_external ? 'Una cuenta de tu dominio o una dirección de fuera.' : 'Una cuenta de tu dominio. Este grupo no admite direcciones de fuera.');
  ventana('Agregar a ' + g.address, correo.nodo, 'Agregar', async () => {
    await api.post(`/grupos/${g.id}/miembros`, { email: correo.entrada.value });
    alTerminar('Miembro agregado.');
  });
}

export async function vistaGrupos(sesion, mensaje) {
  const grupos = await api.get('/grupos');
  const raiz = el('div');
  const recargar = async (texto) => raiz.replaceWith(await vistaGrupos(sesion, texto));
  agregar(raiz,
    el('h1', null, 'Grupos de distribución'),
    el('p', { clase: 'sub' }, 'Una dirección que reparte el correo entre varias personas.'),
    mensaje ? aviso('ok', mensaje) : null,
    el('div', { clase: 'fila' }, el('span', { clase: 'crece ayuda' }, grupos.length === 1 ? '1 grupo' : `${grupos.length} grupos`),
      el('button', { clase: 'boton', alClick: () => nuevoGrupo(sesion.dominios, recargar) }, 'Nuevo grupo')),
    grupos.length ? grupos.map(g => el('section', { clase: 'caja', 'aria-label': g.address },
      el('div', { clase: 'fila' },
        el('div', { clase: 'crece' }, el('strong', null, g.address), ' ',
          el('span', { clase: 'marca ' + (g.active ? 'si' : 'no') }, g.active ? 'Activo' : 'Pausado'),
          g.allow_external ? el('span', { clase: 'marca aviso-marca' }, 'Admite externos') : null,
          el('div', { clase: 'ayuda' }, g.name || '')),
        el('button', { clase: 'enlace', alClick: () => agregarMiembro(g, recargar) }, 'Agregar miembro'),
        el('button', { clase: 'enlace', alClick: () => editarGrupo(g, recargar) }, 'Editar'),
        el('button', { clase: 'enlace peligro', alClick: () => ventana('Eliminar ' + g.address,
          el('p', null, 'El grupo desaparece y el correo que le escriban se rechaza. Las cuentas de sus miembros no se tocan.'),
          'Eliminar', async () => { await api.del('/grupos/' + g.id); recargar('Grupo eliminado.'); }, true) }, 'Eliminar')),
      g.miembros.length ? el('ul', { clase: 'miembros' }, g.miembros.map(m => el('li', null,
        el('span', null, m.email, m.nombre ? el('span', { clase: 'ayuda' }, ' · ' + m.nombre) : null,
          m.externo ? el('span', { clase: 'marca aviso-marca' }, 'Externo') : null),
        el('button', { clase: 'enlace peligro', 'aria-label': `Quitar a ${m.email} de ${g.address}`, alClick: async () => {
          try { await api.del(`/grupos/${g.id}/miembros/${m.id}`); recargar('Miembro quitado.'); } catch (e) { recargar(e.message); }
        } }, 'Quitar'))))
        : el('p', { clase: 'vacio' }, 'Sin miembros todavía: el correo que le escriban se rechaza.')))
      : el('p', { clase: 'caja vacio' }, 'Todavía no hay grupos.'));
  return raiz;
}
