// «Bases de datos» → Usuarios adicionales (v1.11): un usuario por base con permisos a medida, clave nueva que se
// muestra una vez y acceso remoto opcional (solo con TLS, desde las IP o redes elegidas).
import { api } from '../api.js';
import { el, aviso, campo, casilla, lista } from '../ui.js';
import { confirmar, enRutaSitio, hacer, mensajes, unaVez } from './sitio_comun.js';
import { boton, poner } from './sitio_piezas.js';

const MOTOR = { mariadb: 'MariaDB', postgresql: 'PostgreSQL' };
const PERFILES = [
  { valor: 'lectura', texto: 'Lectura (ver datos)' },
  { valor: 'escritura', texto: 'Lectura y escritura (añadir, cambiar y borrar filas)' },
  { valor: 'estructura', texto: 'Estructura (además, crear y cambiar tablas)' },
  { valor: 'todo', texto: 'Todo sobre esa base' },
  { valor: 'medida', texto: 'A medida (elegir permisos)' },
];
const textoPermisos = (p) => !p ? '' : p.perfil === 'medida' ? (p.lista || []).join(', ') : (PERFILES.find(x => x.valor === p.perfil) || {}).texto || p.perfil;

/** Selector de permisos: perfil y, si es «a medida», casillas con los privilegios del motor. */
function selectorPermisos(privilegios, actual) {
  const perfil = lista('Permisos', PERFILES);
  perfil.entrada.value = (actual && actual.perfil) || 'lectura';
  const casillas = (privilegios || []).map(p => ({ p, c: casilla(p, actual && actual.perfil === 'medida' && (actual.lista || []).includes(p)) }));
  const caja = el('div', { clase: 'rejilla' }, casillas.map(x => x.c.nodo));
  const mostrar = () => { caja.hidden = perfil.entrada.value !== 'medida'; };
  perfil.entrada.addEventListener('change', mostrar);
  mostrar();
  return {
    nodo: el('div', null, perfil.nodo, caja),
    valor: () => perfil.entrada.value === 'medida'
      ? { perfil: 'medida', lista: casillas.filter(x => x.c.entrada.checked).map(x => x.p) } : { perfil: perfil.entrada.value },
  };
}

function mostrarClave(r, titulo) {
  const c = r && r.creado;
  if (!c || !c.clave) return;
  unaVez(titulo, [
    { etiqueta: 'Servidor', valor: `${c.servidor}${c.puerto ? ':' + c.puerto : ''}` },
    c.servidor_remoto ? { etiqueta: 'Servidor desde fuera (con TLS)', valor: `${c.servidor_remoto}:${c.puerto}` } : { valor: '' },
    { etiqueta: 'Base', valor: c.base }, { etiqueta: 'Usuario', valor: c.usuario },
    { etiqueta: 'Contraseña', valor: c.clave, secreto: true },
  ], 'La contraseña no se vuelve a mostrar: si se pierde, genera otra.');
}

export function seccionUsuariosBases(ctx) {
  const ruta = `/sitios/${enRutaSitio(ctx.sitio)}/bases/usuarios`;
  const caja = el('div', null, el('h2', null, 'Usuarios de las bases'), el('p', { clase: 'cargando' }, 'Cargando…'));
  const msj = mensajes();
  const deUsuario = (u) => `${ruta}/${encodeURIComponent(u.usuario)}`;

  const editarPermisos = (datos, u, b) => {
    const sel = selectorPermisos(datos.privilegios[u.motor], u.permisos);
    const guardar = boton('Guardar los permisos', 'boton', async (g) => {
      const r = await hacer(msj, g, 'Guardando…', () => api.put(`${deUsuario(u)}/permisos`, { permisos: sel.valor() }));
      if (r) { pintar(r); msj.ok('Permisos cambiados.'); }
    });
    b.closest('li').after(el('li', null, el('div', { clase: 'crece' }, sel.nodo, el('div', { clase: 'pie-form' }, guardar))));
  };

  const editarRemoto = (datos, u, b) => {
    const servidor = (datos.remoto || {})[u.motor] || {};
    const texto = el('textarea', { rows: '3', maxlength: '1100', 'aria-label': 'IP o redes con acceso remoto', valor: (u.remoto || []).join('\n') });
    const guardar = boton('Guardar el acceso remoto', 'boton', async (g) => {
      const redes = texto.value.split(/[\s,]+/).map(x => x.trim()).filter(Boolean);
      const r = await hacer(msj, g, 'Aplicando (cuentas, reglas y cortafuegos)…', () => api.put(`${deUsuario(u)}/remoto`, { redes }));
      if (r) { pintar(r); msj.ok(redes.length ? `Acceso remoto guardado. Cortafuegos: ${r.cortafuegos || 'sin cambios'}.` : 'Ya solo se entra desde este servidor.'); }
    });
    b.closest('li').after(el('li', null, el('div', { clase: 'crece' },
      servidor.activo ? null : aviso('nota', `El acceso remoto a ${MOTOR[u.motor]} no está preparado en este servidor: pídeselo al administrador general.`),
      el('p', { clase: 'ayuda' }, 'Una IP o red por línea (p. ej. 192.0.2.10 o 192.0.2.0/24). Como mucho /16 en IPv4 y /48 en IPv6; ',
        'nunca todo Internet. La conexión exige TLS', datos.remoto && datos.remoto.host ? ` con el servidor ${datos.remoto.host}` : '', '. Vacío: solo desde este servidor.'),
      texto, el('div', { clase: 'pie-form' }, guardar))));
  };

  const pintar = (datos) => {
    const usuarios = datos.usuarios || [];
    const bases = datos.bases || [];
    const base = lista('Base', bases.map(b => ({ valor: b.nombre, texto: `${b.nombre} (${MOTOR[b.motor] || b.motor})` })));
    const sufijo = campo('Nombre', { type: 'text', maxlength: 10, pattern: '[a-z][a-z0-9]{1,9}', required: true, autocomplete: 'off' },
      'De 2 a 10 minúsculas o números, empezando por una letra. El servidor le pone delante el prefijo del sitio.');
    const motorDe = () => (bases.find(b => b.nombre === base.entrada.value) || {}).motor || 'mariadb';
    const hueco = el('div');
    let sel = null;
    const rehacer = () => { sel = selectorPermisos(datos.privilegios[motorDe()], null); poner(hueco, sel.nodo); };
    base.entrada.addEventListener('change', rehacer);
    if (bases.length) rehacer();
    const crear = boton('Crear el usuario', 'boton', null, 'submit');
    poner(caja, el('h2', null, `Usuarios de las bases (${usuarios.length} de ${datos.maximo || 20})`),
      el('p', { clase: 'ayuda' }, 'Otros usuarios para una base del sitio, cada uno con sus permisos. Por defecto solo entran desde este servidor.'),
      usuarios.length ? el('ul', { clase: 'miembros' }, usuarios.map(u => el('li', null,
        el('div', null, el('code', null, u.usuario), ' ', el('span', { clase: 'ayuda' }, `${u.base} · ${MOTOR[u.motor] || u.motor} · ${textoPermisos(u.permisos)}`),
          (u.remoto || []).length ? el('div', { clase: 'ayuda' }, 'Remoto con TLS desde: ', u.remoto.join(', ')) : null),
        el('span', null,
          boton('Permisos', 'enlace', (b) => editarPermisos(datos, u, b)),
          boton('Acceso remoto', 'enlace', (b) => editarRemoto(datos, u, b)),
          boton('Nueva clave', 'enlace', async (b) => mostrarClave(await hacer(msj, b, 'Generando la clave…', () => api.post(`${deUsuario(u)}/clave`)), 'Clave nueva')),
          boton('Borrar', 'enlace peligro', async (b) => {
            if (!await confirmar('Borrar el usuario', `${u.usuario} dejará de poder entrar a ${u.base}. Los datos de la base no se tocan.`, 'Borrar', true)) return;
            const r = await hacer(msj, b, 'Borrando…', () => api.del(deUsuario(u)));
            if (r) { pintar(r); msj.ok('Usuario borrado.'); }
          }))))) : el('p', { clase: 'ayuda' }, 'Ninguno.'),
      bases.length ? el('form', { alSubmit: async (e) => {
        e.preventDefault();
        const r = await hacer(msj, crear, 'Creando el usuario…', () => api.post(ruta, { base: base.entrada.value, sufijo: sufijo.entrada.value.trim(), permisos: sel.valor() }));
        if (r) { pintar(r); mostrarClave(r, 'Usuario creado'); }
      } }, el('div', { clase: 'rejilla' }, base.nodo, sufijo.nodo), hueco, el('div', { clase: 'pie-form' }, crear))
        : el('p', { clase: 'ayuda' }, 'El sitio no tiene bases todavía.'),
      msj.nodo);
  };
  api.get(ruta).then(pintar).catch((e) => poner(caja, el('h2', null, 'Usuarios de las bases'), aviso('error', e.message)));
  return caja;
}
