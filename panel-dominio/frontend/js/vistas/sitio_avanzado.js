// Pestañas «Archivos» (configuración de la aplicación, con versiones anteriores) y «PHP» (versión
// ya instalada y ajustes del sitio). Antes de cada cambio el servidor guarda la versión anterior.
import { api } from '../api.js';
import { el, campo, lista } from '../ui.js';
import { confirmar, enRutaSitio, hacer, mensajes } from './sitio_comun.js';

const NOMBRES_PHP = {
  memory_limit: 'Memoria por proceso (MB)', upload_max_filesize: 'Tamaño máximo de subida (MB)',
  post_max_size: 'Tamaño máximo del formulario (MB)', max_execution_time: 'Tiempo máximo de ejecución (s)',
  max_input_time: 'Tiempo máximo de recepción (s)', max_input_vars: 'Máximo de campos por formulario',
  max_file_uploads: 'Archivos por subida', 'session.gc_maxlifetime': 'Duración de la sesión inactiva (s)',
  display_errors: 'Mostrar errores en pantalla', allow_url_fopen: 'Abrir direcciones como archivos',
  'opcache.enable': 'OPcache (caché de código)', 'date.timezone': 'Zona horaria', error_reporting: 'Errores que se registran',
  permitir_ejecucion: 'Permitir ejecutar programas (exec…)',
};
const NIVELES = [['', 'De serie'], ['produccion', 'Producción'], ['todos', 'Todos (desarrollo)'], ['solo_errores', 'Solo errores graves']];

export async function pestanaArchivos(ctx) {
  const base = `/sitios/${enRutaSitio(ctx.sitio)}`;
  const est = await api.get(base + '/avanzado');
  const msj = mensajes();
  const editor = el('div');
  const ruta = campo('Otra ruta dentro de la carpeta del sitio', { type: 'text', maxlength: 300, placeholder: 'p. ej. publico/.user.ini' });
  const abrir = async (r, boton) => {
    const d = await hacer(msj, boton, 'Abriendo…', () => api.get(`${base}/archivo?ruta=${encodeURIComponent(r)}`));
    if (!d) return;
    const texto = el('textarea', { clase: 'editor', spellcheck: 'false', 'aria-label': 'Contenido de ' + r, valor: d.contenido || '' });
    const guardar = el('button', { clase: 'boton', type: 'button' }, 'Comprobar y guardar');
    guardar.addEventListener('click', async () => {
      const ok = await hacer(msj, guardar, 'Guardando…', () => api.subirGrande(`${base}/archivo?ruta=${encodeURIComponent(r)}`, new Blob([texto.value], { type: 'text/plain' })));
      if (ok) msj.ok('Archivo guardado. La versión anterior quedó en «Versiones anteriores».');
    });
    editor.replaceChildren(el('p', { clase: 'ayuda' }, 'Editando ', el('code', null, r), d.existe === false ? ' (no existe: se creará al guardar).' : '. En los .php se comprueba la sintaxis antes de guardar.'),
      texto, el('div', { clase: 'pie-form' }, guardar));
  };
  const versiones = (est.versiones || []).filter(v => v.tipo !== 'nginx');
  const TIPO = { php: 'Ajustes de PHP', archivo: 'Archivo' };
  return el('div', null,
    el('h2', null, 'Archivos de configuración'),
    el('p', { clase: 'ayuda' }, 'Para quien sabe lo que hace: wp-config.php, .env, .user.ini… Los archivos de tu sitio en general se suben por FTP.'),
    el('div', { clase: 'fila' }, (est.archivos || []).map(a => { const b = el('button', { clase: 'boton claro', type: 'button' }, a); b.addEventListener('click', () => abrir(a, b)); return b; })),
    el('form', { clase: 'fila', alSubmit: (e) => { e.preventDefault(); if (ruta.entrada.value.trim()) abrir(ruta.entrada.value.trim(), null); } },
      el('div', { clase: 'crece' }, ruta.nodo), el('button', { clase: 'boton claro', type: 'submit' }, 'Abrir')),
    msj.nodo, editor,
    el('h2', null, 'Versiones anteriores'),
    versiones.length ? el('ul', { clase: 'miembros' }, versiones.map(v => {
      const b = el('button', { clase: 'enlace', type: 'button' }, 'Restaurar');
      b.addEventListener('click', async () => {
        if (!await confirmar('Restaurar', `¿Volver a la versión del ${v.fecha}? Lo actual también se guarda antes.`, 'Restaurar')) return;
        if (await hacer(msj, b, 'Restaurando…', () => api.post(base + '/restaurar', { version: v.id }))) msj.ok('Versión restaurada.');
      });
      return el('li', null, el('div', null, el('strong', null, v.fecha), ' ', TIPO[v.tipo] || v.tipo, v.ruta ? el('code', null, ' ' + v.ruta) : null), b);
    })) : el('p', { clase: 'ayuda' }, 'Todavía no hay cambios guardados.'));
}

function control(clave, tipo, valor, limites) {
  const etiqueta = (NOMBRES_PHP[clave] || clave) + (limites && tipo !== 'b' ? ` (${limites[0]}–${limites[1]})` : '');
  const limpio = String(valor || '').replace(/M$/, '').replace(/^on$/, '1').replace(/^off$/, '0');
  if (tipo === 'b' || tipo === 'o') {
    const opciones = tipo === 'b' ? [['', 'De serie'], ['1', 'Sí'], ['0', 'No']] : NIVELES;
    const c = lista(etiqueta, opciones.map(([v, t]) => ({ valor: v, texto: t })));
    c.entrada.value = tipo === 'b' ? limpio : String(valor || '');
    return c;
  }
  return campo(etiqueta, { type: 'text', maxlength: 100, valor: tipo === 'z' ? String(valor || '') : limpio });
}

export async function pestanaPhp(ctx) {
  const base = `/sitios/${enRutaSitio(ctx.sitio)}`;
  const [est, php] = await Promise.all([api.get(base + '/avanzado'), api.get(base + '/php')]);
  const msj = mensajes();
  const version = est.php_version || ctx.s.php;
  const instaladas = php.instaladas || [version];
  const destino = lista('Pasar a', instaladas.map(v => ({ valor: v, texto: `PHP ${v}` + (php.notas && php.notas[v] ? ' — ' + php.notas[v] : '') })));
  destino.entrada.value = version;
  const cambiar = el('button', { clase: 'boton', type: 'button' }, 'Cambiar versión');
  cambiar.addEventListener('click', async () => {
    const v = destino.entrada.value;
    if (v === version) return;
    if (!await confirmar('Cambiar la versión de PHP', `¿Pasar ${ctx.sitio} a PHP ${v}? Comprueba antes que tu aplicación lo admite.`, 'Cambiar')) return;
    if (await hacer(msj, cambiar, 'Cambiando…', () => api.put(base + '/php/version', { version: v }))) ctx.recargar();
  });
  const controles = Object.keys(est.php_tipos || {}).map(k => [k, control(k, est.php_tipos[k], (est.php || {})[k], (est.php_limites || {})[k])]);
  const guardar = el('button', { clase: 'boton', type: 'submit' }, 'Comprobar y guardar');
  return el('div', null,
    el('h2', null, `PHP ${version}`),
    php.notas && php.notas[version] ? el('p', { clase: 'aviso nota' }, `PHP ${version}: ${php.notas[version]}. Conviene pasar a una versión con soporte.`) : null,
    el('div', { clase: 'fila' }, el('div', { clase: 'crece' }, destino.nodo), cambiar),
    el('p', { clase: 'ayuda' }, 'Solo las versiones ya instaladas en el servidor. Para otra versión o una extensión, pídela al administrador general: afecta a todo el servidor.'),
    el('form', { alSubmit: async (e) => {
      e.preventDefault();
      const ajustes = Object.fromEntries(controles.map(([k, c]) => [k, c.entrada.value.trim()]));
      if (await hacer(msj, guardar, 'Comprobando con PHP-FPM…', () => api.put(base + '/php', { ajustes }))) msj.ok('Ajustes de PHP aplicados.');
    } }, el('h2', null, 'Ajustes de este sitio'), el('p', { clase: 'ayuda' }, 'Vacío = valor de serie. Se comprueban antes de aplicarse.'),
      el('div', { clase: 'rejilla' }, controles.map(([, c]) => c.nodo)), el('div', { clase: 'pie-form' }, guardar)),
    msj.nodo);
}
