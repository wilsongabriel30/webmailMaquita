import { api, ficha } from './api.js';
import { el, aviso } from './ui.js';
import { vistaEntrar } from './vistas/entrar.js';
import { vistaResumen } from './vistas/resumen.js';
import { vistaCuentas } from './vistas/cuentas.js';
import { vistaAlias } from './vistas/alias.js';
import { vistaMiClave } from './vistas/mi_clave.js';

const raiz = document.getElementById('app');
const SECCIONES = [['resumen', 'Resumen'], ['cuentas', 'Cuentas'], ['alias', 'Alias'], ['clave', 'Mi contraseña']];
let sesion = null;
let debeCambiarClave = false;

const seccionActual = () => (SECCIONES.some(([s]) => '#' + s === location.hash) ? location.hash.slice(1) : 'resumen');

async function pintar() {
  if (!ficha.leer()) { sesion = null; raiz.replaceChildren(vistaEntrar((debe) => { debeCambiarClave = debe; pintar(); })); return; }
  try {
    if (!sesion) sesion = await api.get('/acceso/yo');
    const seccion = debeCambiarClave ? 'clave' : seccionActual();
    const cuerpo = el('main', null, el('p', { clase: 'cargando' }, 'Cargando…'));
    raiz.replaceChildren(
      el('header', { clase: 'barra' },
        el('strong', null, 'Administración de mi dominio'),
        debeCambiarClave ? null : el('nav', null, SECCIONES.map(([s, t]) => el('a', { href: '#' + s, clase: s === seccion ? 'activa' : '' }, t))),
        el('span', { clase: 'quien' }, sesion.display_name || sesion.username),
        el('button', { alClick: async () => { await api.post('/acceso/salir').catch(() => {}); ficha.borrar(); pintar(); } }, 'Salir')),
      cuerpo);
    const vista = seccion === 'cuentas' ? await vistaCuentas(sesion)
      : seccion === 'alias' ? await vistaAlias(sesion)
      : seccion === 'clave' ? vistaMiClave(debeCambiarClave)
      : await vistaResumen();
    cuerpo.replaceChildren(vista);
  } catch (err) {
    if (ficha.leer()) raiz.append(el('main', null, aviso('error', err.message)));
  }
}

window.addEventListener('hashchange', pintar);
window.addEventListener('pd-sin-sesion', () => { sesion = null; debeCambiarClave = false; pintar(); });
pintar();
