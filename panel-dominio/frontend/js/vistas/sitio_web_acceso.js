// Partes de la pestaña «Web» que tratan del acceso y la velocidad: carpetas con contraseña, hotlinking y
// optimización para conexiones lentas (ADSL rural, satélite). Las monta sitio_web.js.
import { api } from '../api.js';
import { el, campo, casilla, lista } from '../ui.js';
import { confirmar, unaVez } from './sitio_comun.js';
import { bloque, boton } from './sitio_piezas.js';

const separar = (texto) => texto.split(/[\s,]+/).map(x => x.trim()).filter(Boolean);

export function seccionPrivacidad(w) {
  const carpetas = w.estado.privacidad.carpetas || [];
  const quitar = (b, consulta, texto) => w.guardar(b, 'Quitando…', () => api.del(`${w.base}/privacidad?${new URLSearchParams(consulta)}`), texto);
  const carpeta = campo('Carpeta', { type: 'text', maxlength: 150, placeholder: '/privado', required: true });
  const usuario = campo('Usuario', { type: 'text', maxlength: 32, autocomplete: 'off', required: true });
  const clave = campo('Contraseña (opcional)', { type: 'password', maxlength: 128, autocomplete: 'new-password' }, 'Vacía: el servidor genera una y te la muestra una sola vez.');
  const agregar = boton('Dar acceso', 'boton', null, 'submit');
  const filas = carpetas.map(c => el('li', null,
    el('div', null, el('code', null, c.ruta), ' ',
      el('span', { clase: 'ayuda' }, (c.usuarios || []).length ? 'Usuarios: ' : 'Sin usuarios'),
      (c.usuarios || []).map(u => el('span', null, el('code', null, u), boton('quitar', 'enlace peligro', (b) => quitar(b, { carpeta: c.ruta, usuario: u }, `${u} ya no entra a ${c.ruta}.`)), ' '))),
    boton('Quitar la protección', 'enlace peligro', async (b) => {
      if (await confirmar('Quitar la protección', `${c.ruta} volverá a ser pública para todo el mundo.`, 'Quitar', true)) quitar(b, { carpeta: c.ruta }, 'La carpeta ya no pide contraseña.');
    })));
  return bloque(`Carpetas con contraseña (${carpetas.length})`,
    'El navegador pide usuario y contraseña para entrar a esa carpeta y a todo lo que tiene dentro. Usa HTTPS: si no, la contraseña viaja sin cifrar.',
    filas.length ? el('ul', { clase: 'miembros' }, filas) : el('p', { clase: 'ayuda' }, 'Ninguna carpeta protegida.'),
    el('form', { alSubmit: async (e) => {
      e.preventDefault();
      const datos = { carpeta: carpeta.entrada.value.trim(), usuario: usuario.entrada.value.trim(), clave: clave.entrada.value || null };
      const r = await w.guardar(agregar, 'Guardando…', () => api.post(w.base + '/privacidad', datos), `${datos.usuario} ya puede entrar a ${datos.carpeta}.`);
      if (r && r.clave) {
        unaVez('Acceso a la carpeta', [{ etiqueta: 'Carpeta', valor: `https://${w.sitio}${r.carpeta || datos.carpeta}` },
          { etiqueta: 'Usuario', valor: r.usuario || datos.usuario }, { etiqueta: 'Contraseña', valor: r.clave, secreto: true }]);
      }
    } }, el('div', { clase: 'rejilla' }, carpeta.nodo, usuario.nodo, clave.nodo), el('div', { clase: 'pie-form' }, agregar)));
}

export function seccionHotlink(w) {
  const h = w.estado.hotlink || {};
  const activo = casilla('Impedir que otras páginas muestren mis archivos', !!h.activo);
  const extensiones = campo('Extensiones protegidas', { type: 'text', maxlength: 300, valor: (h.extensiones || []).join(', ') }, 'Separadas por comas; vacío: las de serie (imágenes, vídeos, PDF…).');
  const permitidos = campo('Dominios que sí pueden mostrarlos', { type: 'text', maxlength: 2000, valor: (h.permitidos || []).join(', '), placeholder: 'example.com, tienda.example.com' });
  const buscadores = casilla('Permitir a los buscadores (Google, Bing…)', h.buscadores !== false);
  const guardar = boton('Guardar', 'boton', null, 'submit');
  return bloque('Hotlinking ' + (h.activo ? '(protegido)' : '(sin proteger)'),
    'El hotlinking es que otra página muestre tus imágenes o vídeos cargándolos desde aquí: gasta tu tráfico sin visitar tu sitio.',
    el('form', { alSubmit: (e) => {
      e.preventDefault();
      w.guardar(guardar, 'Guardando…', () => api.put(w.base + '/hotlink', { activo: activo.entrada.checked,
        extensiones: separar(extensiones.entrada.value), permitidos: separar(permitidos.entrada.value), buscadores: buscadores.entrada.checked }), 'Protección contra hotlinking guardada.');
    } }, activo.nodo, el('div', { clase: 'rejilla' }, extensiones.nodo, permitidos.nodo), buscadores.nodo, el('div', { clase: 'pie-form' }, guardar)));
}

const CADUCIDAD = { off: 'Sin caché', '1h': 'Una hora', '1d': 'Un día', '7d': 'Una semana', '30d': 'Un mes', '180d': 'Seis meses', '365d': 'Un año' };

export function seccionOptimizacion(w) {
  const o = w.estado.optimizacion || {};
  const compresion = casilla('Comprimir lo que se envía' + (o.brotli ? ' (gzip y brotli)' : ' (gzip)'), o.compresion !== false);
  const estaticos = lista('Caché del navegador para imágenes, CSS y JS', (o.caducidades || Object.keys(CADUCIDAD)).map(c => ({ valor: c, texto: CADUCIDAD[c] || c })));
  estaticos.entrada.value = o.estaticos || '30d';
  const cache = casilla('Caché de página (sin sesión iniciada y fuera de la administración)', !!o.cache_pagina);
  const minutos = campo('Minutos que se guarda cada página (1–1440)', { type: 'number', min: '1', max: '1440', valor: String(o.cache_minutos || 10) });
  const guardar = boton('Guardar', 'boton', null, 'submit');
  const purgar = boton('Vaciar la caché de página', 'boton claro', async (b) => {
    const r = await w.guardar(b, 'Vaciando…', () => api.post(w.base + '/purgar'));
    if (r) w.msj.ok(`Caché vaciada (${r.purgados || 0} páginas).`);
  });
  return bloque('Velocidad para conexiones lentas',
    'Pensado para quien entra desde el campo por ADSL o satélite: comprimir y guardar en caché reduce mucho lo que viaja.',
    el('form', { alSubmit: (e) => {
      e.preventDefault();
      w.guardar(guardar, 'Aplicando…', () => api.put(w.base + '/optimizacion', { compresion: compresion.entrada.checked, estaticos: estaticos.entrada.value,
        cache_pagina: o.php ? cache.entrada.checked : false, cache_minutos: Number(minutos.entrada.value) || 10 }), 'Optimización aplicada.');
    } }, compresion.nodo, estaticos.nodo,
    o.php ? el('div', null, cache.nodo, minutos.nodo) : el('p', { clase: 'ayuda' }, 'La caché de página es solo para sitios con PHP (WordPress, Joomla…).'),
    el('div', { clase: 'pie-form' }, o.php && o.cache_pagina ? purgar : null, guardar)));
}
