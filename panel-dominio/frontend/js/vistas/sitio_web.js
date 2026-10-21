// Pestaña «Web»: redirecciones, carpetas con contraseña, páginas de error, hotlinking, IP bloqueadas y
// optimización para conexiones lentas. Cada parte se guarda por separado y afecta solo a este sitio.
// Las partes de acceso y velocidad están en sitio_web_acceso.js.
import { api } from '../api.js';
import { el, campo, casilla, lista } from '../ui.js';
import { confirmar, enRutaSitio, hacer, mensajes } from './sitio_comun.js';
import { bloque, boton, poner } from './sitio_piezas.js';
import { seccionHotlink, seccionOptimizacion, seccionPrivacidad } from './sitio_web_acceso.js';

export async function pestanaWeb(ctx) {
  const base = `/sitios/${enRutaSitio(ctx.sitio)}/web`;
  const msj = mensajes();
  const raiz = el('div');
  let estado = await api.get(base);
  const w = {
    base, msj, sitio: ctx.sitio,
    get estado() { return estado; },
    // Ejecuta la llamada; si sale bien, aplica el estado nuevo que devuelve el servidor y repinta.
    guardar: async (b, espera, fn, bien) => {
      const r = await hacer(msj, b, espera, fn);
      if (!r) return null;
      if (r.redirecciones && r.optimizacion) estado = r;
      pintar();
      if (bien) msj.ok(bien);
      return r;
    },
  };
  const pintar = () => poner(raiz,
    el('p', { clase: 'ayuda' }, 'Cada cambio afecta solo a este sitio. Antes de aplicarlo, el servidor guarda lo anterior y comprueba la configuración; si algo no cuadra, todo queda como estaba y verás el motivo.'),
    msj.nodo,
    seccionRedirecciones(w), seccionPrivacidad(w), seccionErrores(w), seccionHotlink(w), seccionBloqueo(w), seccionOptimizacion(w));
  pintar();
  return raiz;
}

function seccionRedirecciones(w) {
  const actuales = w.estado.redirecciones.lista || [];
  const guardar = (b, nueva, bien) => w.guardar(b, 'Guardando…', () => api.put(w.base + '/redirecciones', { redirecciones: nueva }), bien);
  const que = lista('Qué se redirige', [{ valor: 'ruta', texto: 'Una ruta del sitio' }, { valor: 'todo', texto: 'Todo el dominio' }]);
  const origen = campo('Desde (ruta)', { type: 'text', maxlength: 500, placeholder: '/pagina-vieja' });
  const destino = campo('Hacia', { type: 'text', maxlength: 2000, placeholder: 'https://example.com/pagina-nueva', required: true });
  const codigo = lista('Tipo', [{ valor: '301', texto: '301 permanente' }, { valor: '302', texto: '302 temporal' }]);
  const debajo = casilla('También lo que hay debajo (/blog/entrada → destino/entrada)', false);
  const conservar = casilla('Conservar la ruta (/contacto → destino/contacto)', true);
  const ajustar = () => { const todo = que.entrada.value === 'todo'; origen.nodo.hidden = todo; debajo.nodo.hidden = todo; conservar.nodo.hidden = !todo; };
  que.entrada.addEventListener('change', ajustar);
  ajustar();
  const agregar = boton('Agregar', 'boton', null, 'submit');
  const filas = actuales.map(r => el('tr', null,
    el('td', null, el('code', null, r.origen === '*' ? 'todo el dominio' : r.origen), r.subrutas ? el('span', { clase: 'ayuda' }, ' y debajo') : null),
    el('td', null, el('code', null, r.destino + (r.origen === '*' && r.conservar_ruta ? '/…' : ''))),
    el('td', null, String(r.codigo)),
    el('td', { clase: 'acciones' }, boton('Quitar', 'enlace peligro', async (b) => {
      if (await confirmar('Quitar la redirección', `¿Quitar la redirección de ${r.origen === '*' ? 'todo el dominio' : r.origen}?`, 'Quitar', true)) {
        guardar(b, actuales.filter(x => x.origen !== r.origen), 'Redirección quitada.');
      }
    }))));
  return bloque(`Redirecciones (${actuales.length})`,
    'Usa 301 cuando el cambio es definitivo (los buscadores pasan la posición a la dirección nueva) y 302 si es pasajero. La renovación del certificado nunca se redirige.',
    el('div', { clase: 'tabla-marco' }, el('table', null,
      el('thead', null, el('tr', null, ['Desde', 'Hacia', 'Tipo', ''].map(t => el('th', null, t)))),
      el('tbody', null, filas.length ? filas : el('tr', null, el('td', { colspan: '4', clase: 'vacio' }, 'Sin redirecciones.'))))),
    el('form', { alSubmit: (e) => {
      e.preventDefault();
      const todo = que.entrada.value === 'todo';
      const r = todo ? { origen: '*', destino: destino.entrada.value.trim(), codigo: Number(codigo.entrada.value), conservar_ruta: conservar.entrada.checked }
        : { origen: origen.entrada.value.trim(), destino: destino.entrada.value.trim(), codigo: Number(codigo.entrada.value), subrutas: debajo.entrada.checked };
      if (!r.origen || !r.destino) { w.msj.error('Escribe de dónde y hacia dónde.'); return; }
      guardar(agregar, [...actuales.filter(x => x.origen !== r.origen), r], 'Redirección guardada.');
    } }, el('div', { clase: 'rejilla' }, que.nodo, origen.nodo, destino.nodo, codigo.nodo), debajo.nodo, conservar.nodo,
    el('div', { clase: 'pie-form' }, agregar)));
}

function seccionErrores(w) {
  const e = w.estado.errores || {};
  if (!w.estado.raiz_web) {
    return bloque('Páginas de error', null, el('p', null, 'Este sitio es una aplicación propia: sus páginas de error las genera la propia aplicación.'));
  }
  const idLista = 'paginas-error-candidatas';
  const campos = (e.codigos || []).map(c => [c, campo(`Error ${c}`, { type: 'text', maxlength: 300, list: idLista, placeholder: '/errores/' + c + '.html', valor: (e.paginas || {})[c] || '' })]);
  const guardar = boton('Guardar', 'boton', null, 'submit');
  return bloque('Páginas de error', 'Un archivo .html de la carpeta pública por código. Vacío: la página de serie del servidor.',
    el('datalist', { id: idLista }, (e.candidatos || []).map(c => el('option', { value: c }))),
    el('form', { alSubmit: (ev) => {
      ev.preventDefault();
      const paginas = Object.fromEntries(campos.map(([c, x]) => [c, x.entrada.value.trim()]).filter(([, v]) => v));
      w.guardar(guardar, 'Guardando…', () => api.put(w.base + '/errores', { paginas }), 'Páginas de error guardadas.');
    } }, el('div', { clase: 'rejilla' }, campos.map(([, x]) => x.nodo)),
    (e.candidatos || []).length ? null : el('p', { clase: 'ayuda' }, 'Todavía no hay archivos .html en la carpeta pública.'),
    el('div', { clase: 'pie-form' }, guardar)));
}

function seccionBloqueo(w) {
  const actuales = w.estado.bloqueo.lista || [];
  const texto = el('textarea', { rows: '5', spellcheck: 'false', 'aria-label': 'IP o redes bloqueadas, una por línea', placeholder: '203.0.113.7\n198.51.100.0/24', valor: actuales.join('\n') });
  const guardar = boton('Guardar', 'boton', null, 'submit');
  return bloque(`IP bloqueadas (${actuales.length})`,
    `Direcciones o redes (IPv4 o IPv6) que no pueden entrar a este sitio: reciben «prohibido» (403). Una por línea, hasta ${w.estado.bloqueo.maximo || 500}.`,
    el('form', { alSubmit: (e) => {
      e.preventDefault();
      const redes = texto.value.split(/[\s,]+/).map(x => x.trim()).filter(Boolean);
      w.guardar(guardar, 'Guardando…', () => api.put(w.base + '/bloqueo', { redes }), redes.length ? 'Lista de IP bloqueadas guardada.' : 'Ya no hay IP bloqueadas.');
    } }, texto, el('div', { clase: 'pie-form' }, guardar)));
}
