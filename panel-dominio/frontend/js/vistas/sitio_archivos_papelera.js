// Papelera del administrador de archivos: lo borrado se puede recuperar durante 30 días; después se vacía sola.
import { api } from '../api.js';
import { el, aviso } from '../ui.js';
import { confirmar } from './sitio_comun.js';
import { boton, poner } from './sitio_piezas.js';

/** Ventana con lo que hay en la papelera. `alCambiar` vuelve a listar la carpeta abierta. */
export async function papelera(base, msj, alCambiar) {
  const cerrar = () => velo.remove();
  const error = el('div');
  const cuerpo = el('div', null, el('p', { clase: 'cargando' }, 'Cargando…'));
  const caja = el('div', { clase: 'caja' }, el('h1', null, 'Papelera del sitio'), error, cuerpo,
    el('div', { clase: 'pie-form' }, boton('Cerrar', 'boton claro', cerrar)));
  const velo = el('div', { clase: 'velo', role: 'dialog', 'aria-modal': 'true', 'aria-label': 'Papelera del sitio',
    alKeydown: (e) => { if (e.key === 'Escape') cerrar(); } }, caja);
  document.body.append(velo);
  caja.querySelector('button').focus();

  const intentar = async (b, fn) => {
    b.disabled = true;
    error.replaceChildren();
    try { return await fn(); } catch (e) { error.replaceChildren(aviso('error', e.message)); return null; } finally { b.disabled = false; }
  };
  const pintar = (datos) => {
    const elementos = datos.elementos || [];
    poner(cuerpo,
      el('p', { clase: 'ayuda' }, `Se guarda ${datos.dias || 30} días. Al recuperar, vuelve a su sitio (si ya existe algo con ese nombre, avisa).`),
      elementos.length ? el('ul', { clase: 'miembros' }, elementos.map(x => el('li', null,
        el('div', null, el('code', null, x.ruta), el('div', { clase: 'ayuda' }, x.fecha ? 'borrado el ' + x.fecha : '')),
        boton('Recuperar', 'enlace', async (b) => {
          const r = await intentar(b, () => api.post(`${base}/papelera/${encodeURIComponent(x.id)}/recuperar`));
          if (r) { msj.ok(`Recuperado: ${r.ruta || x.ruta}.`); alCambiar(); cargar(); }
        })))) : el('p', { clase: 'vacio' }, 'La papelera está vacía.'),
      elementos.length ? el('div', { clase: 'fila espacio' }, boton('Vaciar la papelera', 'boton peligro', async (b) => {
        if (!await confirmar('Vaciar la papelera', 'Lo que hay en la papelera se borrará para siempre.', 'Vaciar', true)) return;
        if (await intentar(b, () => api.del(`${base}/papelera`))) cargar();
      })) : null);
  };
  const cargar = () => api.get(`${base}/papelera`).then(pintar).catch((e) => poner(cuerpo, aviso('error', e.message)));
  cargar();
}
