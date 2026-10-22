import { api, ficha } from './api.js';
import { el, aviso } from './ui.js';
import { vistaEntrar } from './vistas/entrar.js';
import { vistaResumen } from './vistas/resumen.js';
import { vistaCuentas } from './vistas/cuentas.js';
import { vistaAlias } from './vistas/alias.js';
import { vistaGrupos } from './vistas/grupos.js';
import { vistaAsignaciones } from './vistas/asignaciones.js';
import { vistaMarca } from './vistas/marca.js';
import { vistaDns } from './vistas/dns.js';
import { vistaMiClave } from './vistas/mi_clave.js';
import { vistaMiCuenta } from './vistas/mi_cuenta.js';
import { vistaSegundoFactor } from './vistas/segundo_factor.js';
import { canjearVale, franjaSoporte, avisoVale } from './soporte.js';

const raiz = document.getElementById('app');
const SECCIONES = [['resumen', 'Resumen'], ['cuentas', 'Cuentas'], ['alias', 'Alias'], ['grupos', 'Grupos'], ['asignadas', 'Cuentas asignadas'], ['marca', 'Marca'], ['dns', 'DNS'], ['sitios', 'Mi sitio web'], ['cuenta', 'Mi cuenta']];
let sesion = null;
let errorVale = null;  // si el enlace de soporte no sirvió, se dice en la pantalla de entrada

// «#sitios/uno.example/https»: la sección es lo que va antes de la primera barra.
const seccionActual = () => { const s = location.hash.slice(1).split('/')[0]; return SECCIONES.some(([x]) => x === s) ? s : 'resumen'; };
const refrescar = () => { sesion = null; pintar(); };

async function pintar() {
  if (!ficha.leer()) {
    sesion = null;
    const entrada = vistaEntrar(pintar);
    if (errorVale) { entrada.prepend(avisoVale(errorVale)); errorVale = null; }
    raiz.replaceChildren(entrada);
    return;
  }
  try {
    if (!sesion) sesion = await api.get('/acceso/yo');
    // Primero la contraseña inicial, después el segundo factor; hasta entonces no hay menú.
    const paso = sesion.debe_cambiar_clave ? 'clave' : sesion.debe_activar_segundo_factor ? 'factor' : null;
    // En una sesión de soporte no hay «Mi cuenta»: la clave y el segundo factor son del cliente.
    const secciones = sesion.soporte ? SECCIONES.filter(([s]) => s !== 'cuenta') : SECCIONES;
    const pedida = seccionActual();
    const seccion = paso || (secciones.some(([s]) => s === pedida) ? pedida : 'resumen');
    const cuerpo = el('main', null, el('p', { clase: 'cargando' }, 'Cargando…'));
    raiz.replaceChildren(
      el('header', { clase: 'barra' },
        el('strong', null, 'Administración de mi dominio'),
        paso ? null : el('nav', { 'aria-label': 'Secciones' }, secciones.map(([s, t]) => el('a', { href: '#' + s, clase: s === seccion ? 'activa' : '', 'aria-current': s === seccion ? 'page' : null }, t))),
        el('span', { clase: 'quien' }, sesion.display_name || sesion.username),
        el('button', { alClick: async () => { await api.post('/acceso/salir').catch(() => {}); ficha.borrar(); pintar(); } }, 'Salir')),
      ...[franjaSoporte(sesion.soporte)].filter(Boolean),
      cuerpo);
    const vista = seccion === 'clave' ? vistaMiClave(true)
      : seccion === 'factor' ? await vistaSegundoFactor(true, refrescar)
      : seccion === 'cuentas' ? await vistaCuentas(sesion)
      : seccion === 'alias' ? await vistaAlias(sesion)
      : seccion === 'grupos' ? await vistaGrupos(sesion)
      : seccion === 'asignadas' ? await vistaAsignaciones(sesion)
      : seccion === 'marca' ? await vistaMarca(sesion)
      : seccion === 'dns' ? await vistaDns(sesion)
      // «Mi sitio web» se descarga solo al abrirla: quien no la usa no paga sus kilobytes.
      : seccion === 'sitios' ? await (await import('./vistas/sitios.js')).vistaSitios(sesion)
      : seccion === 'cuenta' ? await vistaMiCuenta(refrescar)
      : await vistaResumen();
    cuerpo.replaceChildren(vista);
  } catch (err) {
    // El error ocupa el sitio del contenido: nada de dejar «Cargando…» colgado encima.
    if (!ficha.leer()) return;
    const cuerpo = raiz.querySelector('main') || raiz.appendChild(el('main'));
    cuerpo.replaceChildren(aviso('error', err.message || 'No se pudo cargar esta sección.'),
      el('button', { clase: 'boton claro', alClick: pintar }, 'Reintentar'));
  }
}

window.addEventListener('hashchange', pintar);
window.addEventListener('pd-sin-sesion', () => { sesion = null; pintar(); });
canjearVale().then((error) => { errorVale = error; pintar(); });
