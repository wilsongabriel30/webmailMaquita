import { api, enRuta } from '../api.js';
import { el, agregar, aviso, campo, lista, ventana } from '../ui.js';

const AYUDA_DESTINOS = 'Una o varias cuentas de tus dominios, separadas por comas. Deben existir.';

function formulario(dominios, actual, alTerminar) {
  const local = campo('Nombre del alias', { type: 'text', required: true, maxlength: 64, pattern: '[A-Za-z0-9][A-Za-z0-9._\\-]*', autocomplete: 'off' }, 'Ejemplo: info, ventas, contacto');
  const dominio = lista('Dominio', dominios.map(d => ({ valor: d, texto: '@' + d })));
  const destinos = campo('Entrega en', { type: 'text', required: true, maxlength: 4000, valor: actual ? actual.goto.split(',').join(', ') : '' }, AYUDA_DESTINOS);
  if (actual) {
    ventana('Editar ' + actual.address, destinos.nodo, 'Guardar', async () => {
      await api.put('/alias/' + enRuta(actual.address), { goto: destinos.entrada.value });
      alTerminar('Alias actualizado.');
    });
    return;
  }
  ventana('Nuevo alias', el('div', null, local.nodo, dominio.nodo, destinos.nodo), 'Crear alias', async () => {
    const direccion = `${local.entrada.value.trim()}@${dominio.entrada.value}`;
    await api.post('/alias', { address: direccion, goto: destinos.entrada.value });
    alTerminar(`Alias ${direccion} creado.`);
  });
}

export async function vistaAlias(sesion, mensaje) {
  const lista = await api.get('/alias');
  const raiz = el('div');
  const recargar = async (texto) => raiz.replaceWith(await vistaAlias(sesion, texto));
  // agregar() descarta los huecos; append() a secas escribiría la palabra «null».
  agregar(raiz,
    el('h1', null, 'Alias'),
    el('p', { clase: 'sub' }, 'Direcciones que entregan el correo en una o varias cuentas de tu dominio.'),
    mensaje ? aviso('ok', mensaje) : null,
    el('div', { clase: 'fila' }, el('span', { clase: 'crece ayuda' }, `${lista.length} alias`),
      el('button', { clase: 'boton', alClick: () => formulario(sesion.dominios, null, recargar) }, 'Nuevo alias')),
    el('div', { clase: 'caja tabla-marco' }, el('table', null,
      el('thead', null, el('tr', null, el('th', null, 'Alias'), el('th', null, 'Entrega en'), el('th', null, 'Estado'), el('th', null, ''))),
      el('tbody', null, lista.length ? lista.map(a => el('tr', null,
        el('td', null, el('strong', null, a.address)),
        el('td', null, a.goto.split(',').map(d => el('div', null, d))),
        el('td', null, el('span', { clase: 'marca ' + (a.active ? 'si' : 'no') }, a.active ? 'Activo' : 'Pausado')),
        el('td', { clase: 'acciones' },
          el('button', { clase: 'enlace', alClick: () => formulario(sesion.dominios, a, recargar) }, 'Editar'),
          el('button', { clase: 'enlace', alClick: async () => { await api.put('/alias/' + enRuta(a.address), { active: !a.active }); recargar(a.active ? 'Alias pausado.' : 'Alias activado.'); } }, a.active ? 'Pausar' : 'Activar'),
          el('button', { clase: 'enlace peligro', alClick: () => ventana('Eliminar ' + a.address, el('p', null, 'El correo enviado a esta dirección dejará de entregarse. Las cuentas de destino no se tocan.'), 'Eliminar', async () => { await api.del('/alias/' + enRuta(a.address)); recargar('Alias eliminado.'); }, true) }, 'Eliminar'))))
        : el('tr', null, el('td', { colspan: '4', clase: 'vacio' }, 'Todavía no hay alias.'))))));
  return raiz;
}
